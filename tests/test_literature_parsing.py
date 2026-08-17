"""Tests for provider-specific metadata parsing."""

import unittest

from backend.services.literature.openalex_service import _parse_openalex_work
from backend.services.literature.pubmed_service import _parse_pubmed_xml


class PubMedParsingTests(unittest.TestCase):
    def test_parses_structured_abstract_authors_date_and_doi(self) -> None:
        xml = """
        <PubmedArticleSet>
          <PubmedArticle>
            <MedlineCitation>
              <PMID>12345678</PMID>
              <Article>
                <Journal>
                  <JournalIssue><PubDate><Year>2025</Year><Month>Jan</Month></PubDate></JournalIssue>
                  <Title>Example Journal</Title>
                </Journal>
                <ArticleTitle>An <i>Example</i> Paper</ArticleTitle>
                <Abstract>
                  <AbstractText Label="BACKGROUND">First section.</AbstractText>
                  <AbstractText Label="RESULTS">Second section.</AbstractText>
                </Abstract>
                <AuthorList>
                  <Author><ForeName>Ada</ForeName><LastName>Lovelace</LastName></Author>
                  <Author><CollectiveName>Example Consortium</CollectiveName></Author>
                </AuthorList>
              </Article>
            </MedlineCitation>
            <PubmedData>
              <ArticleIdList><ArticleId IdType="doi">https://doi.org/10.1000/example</ArticleId></ArticleIdList>
            </PubmedData>
          </PubmedArticle>
        </PubmedArticleSet>
        """

        items = _parse_pubmed_xml(xml)

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].title, "An Example Paper")
        self.assertEqual(items[0].authors, ["Ada Lovelace", "Example Consortium"])
        self.assertEqual(items[0].year, 2025)
        self.assertEqual(items[0].journal, "Example Journal")
        self.assertEqual(items[0].doi, "10.1000/example")
        self.assertIn("BACKGROUND: First section.", items[0].abstract or "")

    def test_missing_optional_fields_do_not_fail(self) -> None:
        xml = """
        <PubmedArticleSet><PubmedArticle><MedlineCitation>
          <PMID>7</PMID><Article><ArticleTitle>Minimal paper</ArticleTitle></Article>
        </MedlineCitation></PubmedArticle></PubmedArticleSet>
        """

        item = _parse_pubmed_xml(xml)[0]

        self.assertEqual(item.authors, [])
        self.assertIsNone(item.abstract)
        self.assertIsNone(item.doi)
        self.assertIsNone(item.year)


class OpenAlexParsingTests(unittest.TestCase):
    def test_reconstructs_inverted_abstract_and_maps_metadata(self) -> None:
        work = {
            "id": "https://openalex.org/W123",
            "doi": "https://doi.org/10.1000/openalex",
            "display_name": "OpenAlex Example",
            "publication_year": 2024,
            "publication_date": "2024-03-20",
            "authorships": [
                {"author": {"display_name": "Grace Hopper"}},
                {"author": {"display_name": "Alan Turing"}},
            ],
            "abstract_inverted_index": {
                "research": [2],
                "AI": [0],
                "supports": [1],
            },
            "primary_location": {
                "source": {"display_name": "Open Research Journal"}
            },
        }

        item = _parse_openalex_work(work)

        self.assertIsNotNone(item)
        assert item is not None
        self.assertEqual(item.id, "W123")
        self.assertEqual(item.authors, ["Grace Hopper", "Alan Turing"])
        self.assertEqual(item.abstract, "AI supports research")
        self.assertEqual(item.journal, "Open Research Journal")
        self.assertEqual(item.doi, "10.1000/openalex")

    def test_missing_optional_fields_do_not_fail(self) -> None:
        item = _parse_openalex_work({"id": "https://openalex.org/W7"})

        self.assertIsNotNone(item)
        assert item is not None
        self.assertEqual(item.authors, [])
        self.assertIsNone(item.abstract)
        self.assertIsNone(item.doi)
        self.assertIsNone(item.journal)


if __name__ == "__main__":
    unittest.main()
