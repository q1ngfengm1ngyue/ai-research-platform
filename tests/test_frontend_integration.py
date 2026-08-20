"""Checks that the Next.js App Router pages call the Day 3 API paths."""

from pathlib import Path
import unittest


FRONTEND_DIR = Path(__file__).resolve().parents[1] / "frontend"


class FrontendIntegrationTests(unittest.TestCase):
    def test_frontend_is_a_minimal_nextjs_app_router_project(self) -> None:
        package = (FRONTEND_DIR / "package.json").read_text(encoding="utf-8")
        self.assertIn('"next": "16.3.1"', package)
        self.assertTrue((FRONTEND_DIR / "app" / "layout.js").is_file())
        self.assertTrue((FRONTEND_DIR / "app" / "page.js").is_file())
        self.assertTrue(
            (FRONTEND_DIR / "app" / "projects" / "[projectId]" / "page.js").is_file()
        )
        self.assertFalse((FRONTEND_DIR / "index.html").exists())

    def test_search_page_can_save_results_to_a_project(self) -> None:
        page = (FRONTEND_DIR / "app" / "page.js").read_text(encoding="utf-8")
        self.assertIn("Save to Project", page)
        self.assertIn("/projects/${projectId}/papers", page)
        self.assertIn("publication_year: item.year", page)
        self.assertIn("/api/literature/search", page)

    def test_project_pages_use_crud_and_paper_endpoints(self) -> None:
        list_page = (FRONTEND_DIR / "app" / "projects" / "page.js").read_text(
            encoding="utf-8"
        )
        detail_page = (
            FRONTEND_DIR / "app" / "projects" / "[projectId]" / "page.js"
        ).read_text(encoding="utf-8")
        self.assertIn('fetch(`${API_BASE_URL}/projects`', list_page)
        self.assertIn('method: "POST"', list_page)
        self.assertIn('method: "PATCH"', detail_page)
        self.assertIn('method: "DELETE"', detail_page)
        self.assertIn("/papers/${paperId}", detail_page)

    def test_project_detail_can_retrieve_and_preview_documents(self) -> None:
        detail_page = (
            FRONTEND_DIR / "app" / "projects" / "[projectId]" / "page.js"
        ).read_text(encoding="utf-8")
        self.assertIn("Retrieve Full Text", detail_page)
        self.assertIn("/papers/${paperId}/document", detail_page)
        self.assertIn("text_preview", detail_page)


if __name__ == "__main__":
    unittest.main()
