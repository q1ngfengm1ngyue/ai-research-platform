"""Project CRUD, paper persistence, deduplication, and isolation tests."""

import unittest

import httpx
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.api.dependencies import get_database_session
from backend.database import Base
from backend.main import app
from backend.models.project import Paper, Project


class ProjectApiTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )

        @event.listens_for(cls.engine, "connect")
        def enable_foreign_keys(dbapi_connection, connection_record) -> None:  # type: ignore[no-untyped-def]
            del connection_record
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        cls.session_factory = sessionmaker(
            bind=cls.engine, autoflush=False, expire_on_commit=False, class_=Session
        )

        def override_database_session():  # type: ignore[no-untyped-def]
            session = cls.session_factory()
            try:
                yield session
            finally:
                session.close()

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

    async def asyncTearDown(self) -> None:
        await self.client.aclose()

    async def _create_project(self, name: str) -> dict[str, object]:
        response = await self.client.post(
            "/projects", json={"name": name, "description": f"{name} description"}
        )
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    async def test_project_crud(self) -> None:
        project = await self._create_project("Cancer Research")
        project_id = project["id"]

        fetched = await self.client.get(f"/projects/{project_id}")
        self.assertEqual(fetched.status_code, 200)
        self.assertEqual(fetched.json()["name"], "Cancer Research")
        self.assertEqual(fetched.json()["paper_count"], 0)

        updated = await self.client.patch(
            f"/projects/{project_id}",
            json={"name": "Cancer Genomics", "description": None},
        )
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.json()["name"], "Cancer Genomics")
        self.assertIsNone(updated.json()["description"])

        projects = await self.client.get("/projects")
        self.assertEqual(projects.status_code, 200)
        self.assertEqual(len(projects.json()), 1)

        deleted = await self.client.delete(f"/projects/{project_id}")
        self.assertEqual(deleted.status_code, 204)
        self.assertEqual((await self.client.get(f"/projects/{project_id}")).status_code, 404)

    async def test_saves_both_sources_and_deduplicates_inside_project(self) -> None:
        project = await self._create_project("AI Literature")
        project_id = project["id"]
        pubmed_payload = {
            "source": "pubmed",
            "external_id": "12345",
            "title": "A PubMed Paper",
            "abstract": "Abstract",
            "authors": ["Ada Lovelace"],
            "journal": "Example Journal",
            "publication_year": 2026,
            "doi": "https://doi.org/10.1000/Example",
            "url": "https://pubmed.ncbi.nlm.nih.gov/12345/",
        }

        first = await self.client.post(f"/projects/{project_id}/papers", json=pubmed_payload)
        duplicate = await self.client.post(
            f"/projects/{project_id}/papers", json=pubmed_payload
        )
        self.assertEqual(first.status_code, 201, first.text)
        self.assertTrue(first.json()["created"])
        self.assertEqual(duplicate.status_code, 200, duplicate.text)
        self.assertFalse(duplicate.json()["created"])

        openalex_same_doi = {
            **pubmed_payload,
            "source": "openalex",
            "external_id": "W999",
            "title": "The same paper from OpenAlex",
        }
        cross_source_duplicate = await self.client.post(
            f"/projects/{project_id}/papers", json=openalex_same_doi
        )
        self.assertEqual(cross_source_duplicate.status_code, 200)
        self.assertFalse(cross_source_duplicate.json()["created"])

        openalex_unique = {
            **openalex_same_doi,
            "external_id": "W1000",
            "title": "A distinct OpenAlex paper",
            "doi": "10.1000/openalex-unique",
        }
        saved_openalex = await self.client.post(
            f"/projects/{project_id}/papers", json=openalex_unique
        )
        self.assertEqual(saved_openalex.status_code, 201)
        self.assertTrue(saved_openalex.json()["created"])

        papers = (await self.client.get(f"/projects/{project_id}/papers")).json()
        self.assertEqual(len(papers), 2)
        self.assertEqual({paper["source"] for paper in papers}, {"pubmed", "openalex"})
        self.assertEqual(
            (await self.client.get(f"/projects/{project_id}")).json()["paper_count"],
            2,
        )

    async def test_project_paper_isolation_and_removal(self) -> None:
        project_a = await self._create_project("Project A")
        project_b = await self._create_project("Project B")
        payload = {
            "source": "pubmed",
            "external_id": "777",
            "title": "Shared reference",
            "authors": [],
            "publication_year": 2025,
        }

        paper_a = (
            await self.client.post(f"/projects/{project_a['id']}/papers", json=payload)
        ).json()["paper"]
        paper_b_response = await self.client.post(
            f"/projects/{project_b['id']}/papers", json=payload
        )
        self.assertEqual(paper_b_response.status_code, 201)

        papers_a = (await self.client.get(f"/projects/{project_a['id']}/papers")).json()
        papers_b = (await self.client.get(f"/projects/{project_b['id']}/papers")).json()
        self.assertEqual(len(papers_a), 1)
        self.assertEqual(len(papers_b), 1)
        self.assertNotEqual(papers_a[0]["project_id"], papers_b[0]["project_id"])

        wrong_project_delete = await self.client.delete(
            f"/projects/{project_b['id']}/papers/{paper_a['id']}"
        )
        self.assertEqual(wrong_project_delete.status_code, 404)

        removed = await self.client.delete(
            f"/projects/{project_a['id']}/papers/{paper_a['id']}"
        )
        self.assertEqual(removed.status_code, 204)
        self.assertEqual(
            (await self.client.get(f"/projects/{project_a['id']}/papers")).json(), []
        )


if __name__ == "__main__":
    unittest.main()
