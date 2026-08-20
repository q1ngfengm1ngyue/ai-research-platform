"""Bounded HTTP reads with redirect and SSRF protections."""

import asyncio
from dataclasses import dataclass
import ipaddress
import socket
from typing import Any
from urllib.parse import urljoin

import httpx


DOCUMENT_MAX_BYTES = 25 * 1024 * 1024
METADATA_MAX_BYTES = 2 * 1024 * 1024
MAX_REDIRECTS = 3
REQUEST_TIMEOUT = httpx.Timeout(20.0, connect=8.0, read=15.0)
USER_AGENT = "ai-research-platform/0.5 (open-access-document-retrieval)"


class RemoteAccessError(RuntimeError):
    """A safe error describing a rejected or failed remote read."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True)
class HttpPayload:
    url: str
    media_type: str
    body: bytes


async def fetch_bytes(
    client: httpx.AsyncClient,
    url: str,
    *,
    params: dict[str, Any] | None = None,
    max_bytes: int = DOCUMENT_MAX_BYTES,
    validate_hosts: bool = True,
) -> HttpPayload:
    """Fetch a bounded response, validating every redirect target."""

    try:
        current_url = httpx.URL(url)
        if params:
            current_url = current_url.copy_merge_params(params)
    except (httpx.InvalidURL, TypeError, ValueError) as exc:
        raise RemoteAccessError("Remote document URL is invalid") from exc

    for redirect_count in range(MAX_REDIRECTS + 1):
        if validate_hosts:
            await validate_public_url(str(current_url))
        try:
            async with client.stream(
                "GET",
                current_url,
                headers={"User-Agent": USER_AGENT},
                follow_redirects=False,
            ) as response:
                if response.is_redirect:
                    if redirect_count == MAX_REDIRECTS:
                        raise RemoteAccessError("Remote source redirected too many times")
                    location = response.headers.get("location")
                    if not location:
                        raise RemoteAccessError("Remote source returned an invalid redirect")
                    try:
                        current_url = httpx.URL(urljoin(str(current_url), location))
                    except (httpx.InvalidURL, TypeError, ValueError) as exc:
                        raise RemoteAccessError(
                            "Remote source returned an invalid redirect"
                        ) from exc
                    continue

                if response.status_code >= 400:
                    raise RemoteAccessError(
                        f"Remote source returned HTTP {response.status_code}",
                        status_code=response.status_code,
                    )

                declared_length = response.headers.get("content-length")
                if declared_length:
                    try:
                        if int(declared_length) > max_bytes:
                            raise RemoteAccessError(
                                "Remote document exceeds the download limit"
                            )
                    except ValueError:
                        pass

                body = bytearray()
                async for chunk in response.aiter_bytes():
                    body.extend(chunk)
                    if len(body) > max_bytes:
                        raise RemoteAccessError("Remote document exceeds the download limit")
                if not body:
                    raise RemoteAccessError("Remote source returned an empty response")
                return HttpPayload(
                    url=str(response.url),
                    media_type=response.headers.get("content-type", ""),
                    body=bytes(body),
                )
        except httpx.TimeoutException as exc:
            raise RemoteAccessError("Remote source timed out") from exc
        except httpx.RequestError as exc:
            raise RemoteAccessError("Remote source could not be reached") from exc

    raise RemoteAccessError("Remote source redirected too many times")


async def fetch_json(
    client: httpx.AsyncClient,
    url: str,
    *,
    params: dict[str, Any] | None = None,
    validate_hosts: bool = True,
) -> Any:
    payload = await fetch_bytes(
        client,
        url,
        params=params,
        max_bytes=METADATA_MAX_BYTES,
        validate_hosts=validate_hosts,
    )
    media_type = payload.media_type.partition(";")[0].strip().lower()
    if media_type != "application/json" and not media_type.endswith("+json"):
        raise RemoteAccessError("Metadata provider returned an unsupported content type")
    try:
        return httpx.Response(200, content=payload.body).json()
    except ValueError as exc:
        raise RemoteAccessError("Metadata provider returned invalid JSON") from exc


async def validate_public_url(url: str) -> None:
    """Reject non-HTTP URLs and hosts resolving to non-public addresses."""

    try:
        parsed = httpx.URL(url)
        parsed_port = parsed.port
    except (httpx.InvalidURL, TypeError, ValueError) as exc:
        raise RemoteAccessError("Remote document URL is invalid") from exc
    if parsed.scheme not in {"http", "https"} or not parsed.host:
        raise RemoteAccessError("Remote document URL is not a valid HTTP address")
    if parsed_port not in {None, 80, 443}:
        raise RemoteAccessError("Remote document URL uses a disallowed port")

    hostname = parsed.host.decode() if isinstance(parsed.host, bytes) else parsed.host
    if hostname.lower() == "localhost" or hostname.lower().endswith(".localhost"):
        raise RemoteAccessError("Remote document URL is not publicly routable")

    try:
        literal_ip = ipaddress.ip_address(hostname.strip("[]"))
    except ValueError:
        literal_ip = None
    if literal_ip is not None:
        if not literal_ip.is_global:
            raise RemoteAccessError("Remote document URL is not publicly routable")
        return

    try:
        addresses = await asyncio.to_thread(
            socket.getaddrinfo,
            hostname,
            parsed_port or (443 if parsed.scheme == "https" else 80),
            type=socket.SOCK_STREAM,
        )
    except OSError as exc:
        raise RemoteAccessError("Remote document host could not be resolved") from exc

    resolved = {entry[4][0] for entry in addresses}
    if not resolved or any(
        not ipaddress.ip_address(address).is_global for address in resolved
    ):
        raise RemoteAccessError("Remote document URL is not publicly routable")
