"""Regression and request-validation tests for the FastAPI application."""

import unittest

import httpx

from backend.main import app


class ApiValidationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        transport = httpx.ASGITransport(app=app)
        self.client = httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        )

    async def asyncTearDown(self) -> None:
        await self.client.aclose()

    async def test_day_one_endpoints(self) -> None:
        self.assertEqual(
            (await self.client.get("/")).json(),
            {"message": "AI Research Platform is running"},
        )
        self.assertEqual(
            (await self.client.get("/health")).json(),
            {"status": "ok"},
        )

    async def test_empty_query_is_rejected(self) -> None:
        response = await self.client.get(
            "/api/literature/search", params={"q": "", "source": "pubmed"}
        )
        self.assertEqual(response.status_code, 422)

    async def test_whitespace_query_is_rejected(self) -> None:
        response = await self.client.get(
            "/api/literature/search", params={"q": "   ", "source": "pubmed"}
        )
        self.assertEqual(response.status_code, 422)

    async def test_invalid_source_is_rejected(self) -> None:
        response = await self.client.get(
            "/api/literature/search", params={"q": "CRISPR", "source": "google"}
        )
        self.assertEqual(response.status_code, 422)

    async def test_limit_range_is_enforced(self) -> None:
        low = await self.client.get(
            "/api/literature/search",
            params={"q": "CRISPR", "source": "pubmed", "limit": 0},
        )
        high = await self.client.get(
            "/api/literature/search",
            params={"q": "CRISPR", "source": "pubmed", "limit": 21},
        )
        self.assertEqual(low.status_code, 422)
        self.assertEqual(high.status_code, 422)


if __name__ == "__main__":
    unittest.main()
