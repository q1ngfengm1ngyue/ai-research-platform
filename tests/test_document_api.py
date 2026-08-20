"""API tests for project-scoped document retrieval and persistence."""

import unittest
from unittest.mock import AsyncMock, patch

import httpx
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.api.dependencies import get_database_session
from backend.database import Base
from backend.main import app
from backend.models.document import PaperDocument
from backend.services.documents.acquisition import AcquisitionOutcome


AVAILABLE = AcquisitionOutcome(
    source="pmc",
    source_url="https://eutils.ncbi.nlm.nih.gov/article.xml",
    content_type="xml",
    title="Retrieved title",
    text="Full article text for testing.",
    retrieval_status="available",
    error_message=None,
)
UNAVAILABLE = AcquisitionOutcome(
    source="unknown",
    source_url=None,
    content_type=None,
    title="Saved paper",
    text=None,
    retrieval_status="unavailable",
    error_message="No open-access full text source found",
)


class DocumentApiTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        cls.session_factory = sessionmaker(
            bind=cls.engine, autoflush=False, expire_on_commit=False, class_=Session
        )

        def override_database_session():  # type: ignore[no-untyped-def]
            with cls.session_factory() as session:
                yield session

        cls.override_database_session = override_database_session
        app.dependency_overrides[get_database_session] = override_database_session

    @classmethod
    def tearDownClass(cls) -> None:
        app.dependency_overrides.pop(get_database_session, None)
        cls.engine.dispose()

    async def asyncSetUp(self) -> None:
        Base.metadata.drop_all(self.engine)
        Base.metadata.create_all(self.engine)
        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver"
        )
        project = await self.client.post("/projects", json={"name": "Documents"})
        self.project_id = project.json()["id"]
        paper = await self.client.post(
            f"/projects/{self.project_id}/papers",
            json={
                "source": "pubmed",
                "external_id": "12345",
                "title": "Saved paper",
                "authors": [],
            },
        )
        self.paper_id = paper.json()["paper"]["id"]

    async def asyncTearDown(self) -> None:
        await self.client.aclose()

    async def test_missing_paper_is_404(self) -> None:
        response = await self.client.post(
            f"/projects/{self.project_id}/papers/00000000-0000-0000-0000-000000000000/document"
        )
        self.assertEqual(response.status_code, 404)

    @patch(
        "backend.services.documents.acquisition.DocumentAcquisitionService.acquire",
        new_callable=AsyncMock,
    )
    async def test_success_is_persisted_and_readable(self, acquire: AsyncMock) -> None:
        acquire.return_value = AVAILABLE

        retrieved = await self.client.post(
            f"/projects/{self.project_id}/papers/{self.paper_id}/document"
        )
        stored = await self.client.get(
            f"/projects/{self.project_id}/papers/{self.paper_id}/document"
        )

        self.assertEqual(retrieved.status_code, 200, retrieved.text)
        self.assertEqual(retrieved.json()["retrieval_status"], "available")
        self.assertEqual(retrieved.json()["text_length"], len(AVAILABLE.text or ""))
        self.assertTrue(stored.json()["text_available"])
        self.assertEqual(stored.json()["text_preview"], AVAILABLE.text)

    @patch(
        "backend.services.documents.acquisition.DocumentAcquisitionService.acquire",
        new_callable=AsyncMock,
    )
    async def test_no_full_text_returns_structured_unavailable(self, acquire: AsyncMock) -> None:
        acquire.return_value = UNAVAILABLE

        response = await self.client.post(
            f"/projects/{self.project_id}/papers/{self.paper_id}/document"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["retrieval_status"], "unavailable")
        self.assertFalse(response.json()["text_available"])
        self.assertIn("No open-access", response.json()["error_message"])

    @patch(
        "backend.services.documents.acquisition.DocumentAcquisitionService.acquire",
        new_callable=AsyncMock,
    )
    async def test_duplicate_success_uses_cache_and_one_database_row(
        self, acquire: AsyncMock
    ) -> None:
        acquire.return_value = AVAILABLE
        url = f"/projects/{self.project_id}/papers/{self.paper_id}/document"

        first = await self.client.post(url)
        second = await self.client.post(url)

        self.assertFalse(first.json()["cached"])
        self.assertTrue(second.json()["cached"])
        acquire.assert_awaited_once()
        with self.session_factory() as session:
            self.assertEqual(session.query(PaperDocument).count(), 1)

    @patch(
        "backend.services.documents.acquisition.DocumentAcquisitionService.acquire",
        new_callable=AsyncMock,
    )
    async def test_force_refresh_reacquires_without_creating_a_second_row(
        self, acquire: AsyncMock
    ) -> None:
        acquire.return_value = AVAILABLE
        url = f"/projects/{self.project_id}/papers/{self.paper_id}/document"

        await self.client.post(url)
        refreshed = await self.client.post(url, params={"force_refresh": "true"})

        self.assertFalse(refreshed.json()["cached"])
        self.assertEqual(acquire.await_count, 2)
        with self.session_factory() as session:
            self.assertEqual(session.query(PaperDocument).count(), 1)

    async def test_not_retrieved_status_can_be_read(self) -> None:
        response = await self.client.get(
            f"/projects/{self.project_id}/papers/{self.paper_id}/document"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["retrieval_status"], "not_retrieved")


if __name__ == "__main__":
    unittest.main()
