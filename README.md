# AI Research Assistant Platform

## Project

AI Research Assistant Platform is a modular research-support application for researchers. The long-term project will explore literature search, research knowledge management, RAG, and AI-assisted research workflows.

## Current Version

V1 Prototype

## Current Stage

Day 2 — Literature Search

The application now searches real PubMed and OpenAlex metadata and converts both providers into one `LiteratureItem` structure. RAG, embeddings, vector databases, LLM calls, agents, and full-text downloads are intentionally not included yet.

## Architecture

```text
Browser frontend
  ↓ GET /api/literature/search
FastAPI route (validation and HTTP response)
  ↓
Literature service (provider selection/orchestration)
  ├── PubMed: ESearch → EFetch → XML parser
  └── OpenAlex: Works search → JSON parser
  ↓
Unified LiteratureItem JSON
  ↓
Safe DOM rendering in the frontend
```

The current project structure is intentionally small:

```text
ai-research-platform/
├── backend/
│   ├── api/routes/literature.py
│   ├── schemas/literature.py
│   ├── services/literature/
│   │   ├── literature_service.py
│   │   ├── openalex_service.py
│   │   └── pubmed_service.py
│   └── main.py
├── frontend/index.html
├── tests/
│   ├── test_api_validation.py
│   └── test_literature_parsing.py
├── .env.example
├── .gitignore
├── README.md
└── requirements.txt
```

Routes handle HTTP validation, services communicate with providers, and schemas define the provider-independent response. The frontend receives structured JSON and safely renders external text without injecting it as HTML.

## How to Run

Python 3.11 or newer is recommended.

### 1. Create and activate a virtual environment

From the project root in PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 2. Install dependencies

```powershell
python -m pip install -r requirements.txt
```

### 3. Start the backend

Optionally copy `.env.example` to `.env` and add `NCBI_API_KEY` or `OPENALEX_API_KEY`. The code attempts anonymous requests when keys are absent, but provider policies and rate limits can change. Never commit `.env`.

```powershell
python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

The API is available at:

- <http://127.0.0.1:8000/>
- <http://127.0.0.1:8000/health>
- <http://127.0.0.1:8000/docs>

### 4. Start the frontend

Open a second PowerShell window, return to the project root, and run:

```powershell
python -m http.server 5500 --directory frontend
```

Then open <http://127.0.0.1:5500/>, enter keywords, select PubMed, OpenAlex, or All, and select **Search Literature**.

Keep both terminal processes running while using the page. Stop either server with `Ctrl+C`.

## API Endpoints

| Method | Path | Purpose | Response |
| --- | --- | --- | --- |
| GET | `/` | Basic API check | `{"message":"AI Research Platform is running"}` |
| GET | `/health` | Health check used by the frontend | `{"status":"ok"}` |
| GET | `/api/literature/search` | Search literature metadata | Unified search response |

The search endpoint accepts:

| Parameter | Required | Default | Validation |
| --- | --- | --- | --- |
| `q` | yes | — | non-empty, at most 500 characters |
| `source` | no | `all` | `pubmed`, `openalex`, or `all` |
| `limit` | no | `10` | integer from 1 to 20 |

Examples:

```text
/api/literature/search?q=CRISPR&source=pubmed&limit=5
/api/literature/search?q=CRISPR&source=openalex&limit=5
/api/literature/search?q=CRISPR&source=all&limit=5
```

When `source=all`, both searches run concurrently. If one provider is unavailable, results from the other are returned with a warning; if both fail, the API returns a safe `503` response.

## Unified Literature Item

```json
{
  "id": "provider identifier",
  "source": "pubmed or openalex",
  "title": "Paper title",
  "authors": ["Author One"],
  "abstract": "Abstract text or null",
  "publication_date": "Provider date or null",
  "year": 2026,
  "journal": "Journal/source name or null",
  "doi": "Normalised DOI or null",
  "url": "Provider record URL"
}
```

## Tests

```powershell
python -m unittest discover -s tests -v
```

The suite checks Day 1 regression behavior, request validation, both provider parsers, structured abstracts, and missing optional fields.

## Local CORS Configuration

The backend accepts browser requests from `http://127.0.0.1:5500` and `http://localhost:5500`. These origins are only for local Day 1 development and can be moved into environment-based configuration when deployment work begins.

## Next Step

Day 3 — RAG Part 1: Document Processing, Chunking, Embedding Preparation

