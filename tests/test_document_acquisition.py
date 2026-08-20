"""Mock-network tests for OA source discovery and acquisition outcomes."""

import json
import uuid
import unittest
from unittest.mock import patch

import httpx

from backend.models.project import Paper
from backend.services.documents.acquisition import DocumentAcquisitionService
from backend.services.documents.http_client import (
    RemoteAccessError,
    fetch_bytes,
    validate_public_url,
)
from backend.services.documents.parsers import DocumentParseError, ParsedDocument


def _paper(source: str = "pubmed", *, doi: str | None = None) -> Paper:
    return Paper(
        id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        source=source,
        external_id="12345" if source == "pubmed" else "W12345",
        title="Saved paper",
        authors=[],
        doi=doi,
    )


def _json_response(request: httpx.Request, data: object, status: int = 200) -> httpx.Response:
    return httpx.Response(
        status,
        headers={"Content-Type": "application/json"},
        content=json.dumps(data).encode(),
        request=request,
    )


class DocumentAcquisitionTests(unittest.IsolatedAsyncioTestCase):
    async def _acquire(self, paper: Paper, handler) -> object:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await DocumentAcquisitionService(
                client, validate_hosts=False
            ).acquire(paper)

    async def test_pmc_jats_success(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            self.assertIn("ai-research-platform", request.headers["user-agent"])
            if "elink.fcgi" in request.url.path:
                return _json_response(
                    request,
                    {"linksets": [{"linksetdbs": [{"dbto": "pmc", "links": ["999"]}]}]},
                )
            return httpx.Response(
                200,
                headers={"Content-Type": "application/xml"},
                content=(
                    b"<article><article-title>PMC title</article-title>"
                    b"<body><p>Full text.</p></body></article>"
                ),
                request=request,
            )

        outcome = await self._acquire(_paper(), handler)

        self.assertEqual(outcome.retrieval_status, "available")
        self.assertEqual(outcome.source, "pmc")
        self.assertEqual(outcome.content_type, "xml")
        self.assertIn("Full text.", outcome.text or "")

    @patch("backend.services.documents.acquisition.parse_document")
    async def test_openalex_oa_pdf_success(self, parse_document) -> None:
        parse_document.return_value = (
            "pdf",
            ParsedDocument(title="OA PDF", text="Extracted PDF text"),
        )

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.host == "api.openalex.org":
                return _json_response(
                    request,
                    {
                        "open_access": {"is_oa": True},
                        "best_oa_location": {"pdf_url": "https://oa.example/article.pdf"},
                    },
                )
            return httpx.Response(
                200,
                headers={"Content-Type": "application/pdf"},
                content=b"%PDF-mocked",
                request=request,
            )

        outcome = await self._acquire(_paper("openalex"), handler)

        self.assertEqual(outcome.retrieval_status, "available")
        self.assertEqual(outcome.source, "openalex")
        self.assertEqual(outcome.content_type, "pdf")

    async def test_pubmed_metadata_can_use_openalex_document_provider(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            if "elink.fcgi" in request.url.path:
                return _json_response(request, {"linksets": [{"linksetdbs": []}]})
            if request.url.host == "api.openalex.org":
                return _json_response(
                    request,
                    {
                        "open_access": {"is_oa": True},
                        "best_oa_location": {
                            "landing_page_url": "https://oa.example/article"
                        },
                    },
                )
            return httpx.Response(
                200,
                headers={"Content-Type": "text/html"},
                content=b"<article><p>Cross-provider full text.</p></article>",
                request=request,
            )

        outcome = await self._acquire(
            _paper("pubmed", doi="10.1000/cross-provider"), handler
        )

        self.assertEqual(outcome.retrieval_status, "available")
        self.assertEqual(outcome.source, "openalex")
        self.assertEqual(outcome.content_type, "html")
        self.assertIn("Cross-provider full text", outcome.text or "")

    async def test_structured_candidate_ranks_ahead_of_html_and_pdf(self) -> None:
        downloaded_candidates: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            if "elink.fcgi" in request.url.path:
                return _json_response(
                    request,
                    {"linksets": [{"linksetdbs": [{"dbto": "pmc", "links": ["999"]}]}]},
                )
            if request.url.host == "api.openalex.org":
                return _json_response(
                    request,
                    {
                        "open_access": {"is_oa": True},
                        "best_oa_location": {
                            "landing_page_url": "https://oa.example/article",
                            "pdf_url": "https://oa.example/article.pdf",
                        },
                    },
                )
            downloaded_candidates.append(str(request.url))
            if "efetch.fcgi" in request.url.path:
                return httpx.Response(
                    200,
                    headers={"Content-Type": "application/xml"},
                    content=b"<article><body><p>Structured text.</p></body></article>",
                    request=request,
                )
            self.fail(f"Lower-priority candidate was fetched: {request.url}")

        outcome = await self._acquire(
            _paper("pubmed", doi="10.1000/ranked"), handler
        )

        self.assertEqual(outcome.source, "pmc")
        self.assertEqual(outcome.content_type, "xml")
        self.assertEqual(len(downloaded_candidates), 1)

    async def test_failed_structured_candidate_falls_back_to_ranked_html(self) -> None:
        downloaded_candidates: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            if "elink.fcgi" in request.url.path:
                return _json_response(
                    request,
                    {"linksets": [{"linksetdbs": [{"dbto": "pmc", "links": ["999"]}]}]},
                )
            if request.url.host == "api.openalex.org":
                return _json_response(
                    request,
                    {
                        "open_access": {"is_oa": True},
                        "best_oa_location": {
                            "landing_page_url": "https://oa.example/article",
                            "pdf_url": "https://oa.example/article.pdf",
                        },
                    },
                )
            downloaded_candidates.append(str(request.url))
            if "efetch.fcgi" in request.url.path:
                return httpx.Response(500, request=request)
            if request.url.path == "/article":
                return httpx.Response(
                    200,
                    headers={"Content-Type": "text/html"},
                    content=b"<article><p>HTML fallback text.</p></article>",
                    request=request,
                )
            self.fail(f"PDF should not be reached after HTML succeeds: {request.url}")

        outcome = await self._acquire(
            _paper("pubmed", doi="10.1000/fallback"), handler
        )

        self.assertEqual(outcome.retrieval_status, "available")
        self.assertEqual(outcome.source, "openalex")
        self.assertEqual(outcome.content_type, "html")
        self.assertEqual(len(downloaded_candidates), 2)

    async def test_404_becomes_failed_status(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(404, request=request)

        outcome = await self._acquire(_paper(), handler)

        self.assertEqual(outcome.retrieval_status, "failed")
        self.assertIn("HTTP 404", outcome.error_message or "")

    async def test_timeout_becomes_failed_status(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ReadTimeout("slow", request=request)

        outcome = await self._acquire(_paper(), handler)

        self.assertEqual(outcome.retrieval_status, "failed")
        self.assertIn("timed out", outcome.error_message or "")

    async def test_no_oa_source_is_unavailable(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return _json_response(request, {"linksets": [{"linksetdbs": []}]})

        outcome = await self._acquire(_paper(), handler)

        self.assertEqual(outcome.retrieval_status, "unavailable")
        self.assertEqual(outcome.error_message, "No open-access full text source found")

    async def test_unsupported_content_type_is_failed(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.host == "api.openalex.org":
                return _json_response(
                    request,
                    {
                        "open_access": {"is_oa": True},
                        "best_oa_location": {"landing_page_url": "https://oa.example/archive"},
                    },
                )
            return httpx.Response(
                200,
                headers={"Content-Type": "application/zip"},
                content=b"not an article",
                request=request,
            )

        outcome = await self._acquire(_paper("openalex"), handler)

        self.assertEqual(outcome.retrieval_status, "failed")
        self.assertIn("Unsupported document content type", outcome.error_message or "")

    @patch("backend.services.documents.acquisition.parse_document")
    async def test_parse_failure_is_structured(self, parse_document) -> None:
        parse_document.side_effect = DocumentParseError("PDF contains no extractable text layer")

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.host == "api.openalex.org":
                return _json_response(
                    request,
                    {
                        "open_access": {"is_oa": True},
                        "best_oa_location": {"pdf_url": "https://oa.example/article.pdf"},
                    },
                )
            return httpx.Response(200, content=b"%PDF-empty", request=request)

        outcome = await self._acquire(_paper("openalex"), handler)

        self.assertEqual(outcome.retrieval_status, "failed")
        self.assertIn("no extractable text", outcome.error_message or "")

    async def test_download_limit_is_enforced_while_streaming(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=b"too large", request=request)

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            with self.assertRaisesRegex(RemoteAccessError, "download limit"):
                await fetch_bytes(
                    client,
                    "https://oa.example/article",
                    max_bytes=4,
                    validate_hosts=False,
                )

    async def test_private_literal_address_is_rejected(self) -> None:
        with self.assertRaisesRegex(RemoteAccessError, "publicly routable"):
            await validate_public_url("http://127.0.0.1/article.pdf")


if __name__ == "__main__":
    unittest.main()
