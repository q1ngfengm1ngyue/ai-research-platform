# AI Research Assistant Platform

## Project

AI Research Assistant Platform is a modular research-support application for researchers. The long-term project will explore literature search, research knowledge management, RAG, and AI-assisted research workflows.

## Current Version

V1 Prototype

## Current Stage

Task 5 — Open-Access Document Retrieval and Parsing

The application searches real PubMed and OpenAlex metadata, manages research Projects, saves provider-independent papers into a project-scoped PostgreSQL library, and can retrieve legally available full text as clean, persisted document text. Chunking, embeddings, pgvector, semantic search, RAG, citation generation, LLM calls, and agents are intentionally not included yet.

The original static HTML/CSS/JavaScript behavior and visual style have been migrated to a minimal Next.js App Router frontend.

## Architecture

```text
Next.js App Router frontend
  ├── Literature Search → GET /api/literature/search
  │     ├── PubMed: ESearch → EFetch → XML parser
  │     └── OpenAlex: Works search → JSON parser
  ├── Project workspace → /projects CRUD
  ├── Save Paper → /projects/{project_id}/papers
  └── Retrieve document → PMC JATS first, then OpenAlex OA location
                           ↓
                    FastAPI routes
                           ↓
          Project/Paper/Document services
                           ↓
               XML / HTML / PDF parsers
                           ↓
                     SQLAlchemy 2
                           ↓
                     PostgreSQL 16
```

The current project structure remains intentionally small:

```text
ai-research-platform/
├── backend/
│   ├── api/
│   │   ├── dependencies.py
│   │   └── routes/
│   │       ├── documents.py
│   │       ├── literature.py
│   │       ├── papers.py
│   │       └── projects.py
│   ├── models/
│   │   ├── document.py
│   │   └── project.py
│   ├── schemas/
│   │   ├── documents.py
│   │   ├── literature.py
│   │   └── projects.py
│   ├── services/literature/
│   │   ├── literature_service.py
│   │   ├── openalex_service.py
│   │   └── pubmed_service.py
│   ├── services/paper_service.py
│   ├── services/project_service.py
│   ├── services/document_service.py
│   ├── services/documents/
│   │   ├── acquisition.py
│   │   ├── http_client.py
│   │   ├── sources.py
│   │   └── parsers/
│   ├── database.py
│   └── main.py
├── frontend/
│   ├── app/
│   │   ├── globals.css
│   │   ├── layout.js
│   │   ├── page.js
│   │   └── projects/
│   │       ├── page.js
│   │       └── [projectId]/page.js
│   ├── .env.example
│   ├── AGENTS.md
│   ├── CLAUDE.md
│   ├── package-lock.json
│   └── package.json
├── scripts/init_db.py
├── tests/
│   ├── test_api_validation.py
│   ├── test_document_acquisition.py
│   ├── test_document_api.py
│   ├── test_document_parsers.py
│   ├── test_frontend_integration.py
│   ├── test_literature_parsing.py
│   └── test_project_api.py
├── .env.example
├── .gitignore
├── docker-compose.yml
├── README.md
└── requirements.txt
```

Routes handle HTTP validation, services contain provider/database operations, and schemas define provider-independent responses. The frontend receives structured JSON and safely renders external text without injecting it as HTML.

## Directory Notes

GitHub's middle file-list column displays the latest commit message, not a custom note. Use this table as the directory description:

| Path | Purpose |
| --- | --- |
| `backend/api/routes/` | Literature, Project, saved-paper, and Document endpoints |
| `backend/models/` | SQLAlchemy Project, Paper, and PaperDocument tables |
| `backend/services/literature/` | Existing PubMed/OpenAlex integrations |
| `backend/services/project_service.py` | Project CRUD operations |
| `backend/services/paper_service.py` | Paper persistence and deduplication |
| `backend/services/document_service.py` | Document cache, persistence, and response presentation |
| `backend/services/documents/` | OA discovery, bounded HTTP reads, and content-specific parsers |
| `backend/database.py` | Engine, Session, Base, initialization, and health query |
| `frontend/app/` | Next.js App Router search, Project list, and dynamic detail routes |
| `scripts/init_db.py` | Creates Day 3 tables in PostgreSQL |
| `tests/` | Day 1–3 regression and behavior tests |

## Database Schema

`projects` contains `id`, `name`, `description`, `created_at`, and `updated_at`. `papers` contains `id`, `project_id`, `source`, `external_id`, `title`, `abstract`, `authors` (JSON), `journal`, `publication_year`, `doi`, `url`, and `created_at`.

`papers.project_id` references `projects.id` with cascade delete. Two database constraints prevent duplicates inside a Project:

- unique `(project_id, source, external_id)`;
- unique `(project_id, doi)` when DOI is present.

PostgreSQL permits multiple `NULL` DOI values. The same paper can be saved once in Project A and independently once in Project B.

`paper_documents` contains `id`, unique `paper_id`, `source`, `source_url`, `content_type`, `title`, `text`, `retrieval_status`, `error_message`, `retrieved_at`, `created_at`, and `updated_at`. `paper_id` references `papers.id` with cascade delete, giving each saved Paper at most one current Document row. Retrieval status is constrained to `available`, `unavailable`, or `failed`.

This project currently uses `Base.metadata.create_all()` through `python -m scripts.init_db` for additive table initialization; Alembic is not configured. Running the initializer against an existing Task 1–4 PostgreSQL database creates `paper_documents` without rewriting `projects` or `papers`.

## Environment Variables

Copy `.env.example` to `.env`, then replace the example PostgreSQL password locally:

```dotenv
NCBI_API_KEY=
OPENALEX_API_KEY=
POSTGRES_DB=ai_research
POSTGRES_USER=ai_research
POSTGRES_PASSWORD=change_me
DATABASE_URL=postgresql+psycopg://ai_research:change_me@127.0.0.1:5432/ai_research
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
```

The provider keys are optional. `DATABASE_URL` is required for Project/Paper endpoints. The browser-visible FastAPI URL can be placed in `frontend/.env.local` using `frontend/.env.example` as the template. Never commit `.env` or `.env.local`.

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

### 3. Configure and start PostgreSQL

From the project root:

```powershell
Copy-Item .env.example .env
notepad .env
docker compose up -d postgres
docker compose ps
```

This requires Docker Desktop. Alternatively, create the `ai_research` user/database in an installed PostgreSQL server and point `DATABASE_URL` at it. Day 3 uses ordinary PostgreSQL only; pgvector is not required.

### 4. Initialize the schema and start the backend

```powershell
python -m scripts.init_db
python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

The API is available at:

- <http://127.0.0.1:8000/>
- <http://127.0.0.1:8000/health>
- <http://127.0.0.1:8000/health/database>
- <http://127.0.0.1:8000/docs>

### 5. Install and start the Next.js frontend

Node.js 20.9 or newer is required. Open a second PowerShell window and run:

```powershell
Set-Location 'D:\实习任务\ai-research-platform\frontend'
Copy-Item .env.example .env.local
npm install
npm run dev
```

Open <http://localhost:3000/projects> to create a Project and <http://localhost:3000/> to search and save literature. This repository standardizes on npm; use `package-lock.json` and do not add another package-manager lock file.

Keep both terminal processes running while using the page. Stop either server with `Ctrl+C`.

## API Endpoints

| Method | Path | Purpose | Response |
| --- | --- | --- | --- |
| GET | `/` | Basic API check | `{"message":"AI Research Platform is running"}` |
| GET | `/health` | Health check used by the frontend | `{"status":"ok"}` |
| GET | `/health/database` | PostgreSQL connection check | Database status |
| GET | `/api/literature/search` | Search literature metadata | Unified search response |
| POST | `/projects` | Create Project | Project |
| GET | `/projects` | List Projects | Projects with paper counts |
| GET | `/projects/{project_id}` | Read Project | Project |
| PATCH | `/projects/{project_id}` | Update Project | Project |
| DELETE | `/projects/{project_id}` | Delete Project and papers | No content |
| POST | `/projects/{project_id}/papers` | Save/deduplicate search result | Paper and created flag |
| GET | `/projects/{project_id}/papers` | List Project papers | Paper list |
| DELETE | `/projects/{project_id}/papers/{paper_id}` | Remove Project paper | No content |
| GET | `/projects/{project_id}/papers/{paper_id}/document` | Read persisted retrieval status and text preview | Document status |
| POST | `/projects/{project_id}/papers/{paper_id}/document` | Retrieve, parse, and persist legal OA full text | Document status |

The Document POST endpoint accepts the optional query parameter `force_refresh=true`. By default, an already available Document is returned from PostgreSQL with `cached: true` and no external download. Failed or unavailable attempts update the same one-to-one row rather than creating duplicates.

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

## Document Retrieval

### Supported full-text sources

The retrieval service uses saved Paper metadata and never accepts an arbitrary download URL from an API caller:

1. For a saved PubMed paper, NCBI ELink maps the PMID to PMC. When available, PMC JATS/XML is downloaded through NCBI EFetch and preferred over PDF.
2. If PMC is unavailable or fails, a saved OpenAlex ID—or a DOI saved with either provider—is resolved through the OpenAlex Works API. Only a location declared open access by OpenAlex is considered; `best_oa_location` is preferred, followed by an OA `primary_location`.
3. An OA location may return XML/JATS, HTML, PDF, or plain text. The response Content-Type and PDF signature determine the parser.

The system does **not** bypass paywalls, authenticate to publisher accounts, use Sci-Hub, defeat PDF protections, or download from caller-supplied URLs.

### Parsing and clean text

- JATS/XML extraction retains the article title, abstract, section headings, and body paragraphs.
- HTML extraction removes script, style, navigation, header, footer, aside, and markup before normalizing readable text.
- PDF extraction uses `pypdf` and reads the existing text layer only. OCR is not performed.
- Unicode is normalized, repeated horizontal whitespace is collapsed, and paragraph boundaries are retained. The result is not chunked.

API responses return metadata, text length, and at most the first 1,500 characters as `text_preview`; the complete clean text remains in PostgreSQL for later processing stages.

### Retrieval states and failures

The project detail page displays `Not retrieved`, `Retrieving`, `Available`, `Unavailable`, or `Failed`. `Unavailable` means no declared OA source was found. Expected provider timeouts, HTTP 403/404/429/5xx responses, empty bodies, malformed documents, unsupported content types, encrypted or damaged PDFs, and PDFs without a text layer are returned as structured status/error fields instead of uncaught FastAPI errors.

External requests use a descriptive User-Agent, bounded connect/read timeouts, no unbounded retry, at most three redirects, and a 25 MiB download limit. Every initial and redirected URL must use HTTP(S), ports 80/443, and a publicly routable host; localhost, private, loopback, link-local, and other non-public addresses are rejected.

### Triggering retrieval

In the UI, open `/projects/{project_id}` and choose **Retrieve Full Text** on a saved paper. On success the card shows the source, normalized content type, text length, and preview.

PowerShell API example:

```powershell
$projectId = '<project UUID>'
$paperId = '<paper UUID>'
Invoke-RestMethod -Method Post `
  -Uri "http://127.0.0.1:8000/projects/$projectId/papers/$paperId/document"
Invoke-RestMethod `
  -Uri "http://127.0.0.1:8000/projects/$projectId/papers/$paperId/document"
```

### Current limitations

- PMC discovery currently starts from a PubMed PMID; manually entered PMC IDs are not a separate Paper source.
- OpenAlex fallback depends on a valid saved OpenAlex ID or DOI and on OpenAlex marking the location OA.
- HTML extraction is conservative heuristic text cleanup, not a publisher-specific readability engine.
- Scanned/image-only and encrypted PDFs are reported as failed; OCR and password handling are intentionally absent.
- A source larger than 25 MiB is rejected, and transient failures are not automatically retried.
- The API intentionally exposes only a bounded preview, not a dedicated full-text reader endpoint.
- The current initialization mechanism creates new tables but does not provide versioned schema downgrades.

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

The suite checks Task 1 regression behavior, literature request validation/provider parsers, Project CRUD, PubMed/OpenAlex save payloads, deduplication and Project isolation, XML/HTML/PDF parsing, mocked PMC/OpenAlex acquisition failures, Document API persistence/cache behavior, the Next.js App Router structure, and frontend API paths. Unit/API tests use a deterministic in-memory SQLAlchemy test engine; real PostgreSQL and OA verification are run separately.

Verify the frontend production build separately:

```powershell
Set-Location frontend
npm run build
```

## Task 5 Acceptance Verification

Verified locally on 2026-08-20 with Python 3.12, `pypdf` 6.16.1, Next.js 16.3.1, Docker Engine 29.7.2, PostgreSQL 16, and the repository's existing Task 1–4 data:

- `python -m scripts.init_db` added `paper_documents` to the real PostgreSQL database while retaining `projects` and `papers`.
- A real API smoke Paper with PMID `16060722` mapped to `PMC1182327`.
- NCBI EFetch returned PMC JATS/XML, which parsed to 28,481 characters of clean text and persisted with status `available`.
- A new Python/FastAPI process queried the same Document ID, text length, and preview from PostgreSQL without making another retrieval request.
- Automated test result: 37 passed, 0 failed.
- Next.js production build completed successfully for `/`, `/projects`, and `/projects/[projectId]`.

The smoke Project is named `Task 5 OA Smoke 2026-08-20` so its persisted Paper and Document can be inspected locally.

## Earlier Task 3 Acceptance Verification

Verified locally on 2026-08-19 with Node.js 24.19.0, npm 11.17.0, Docker Engine 29.7.2, Docker Compose 5.4.0, and PostgreSQL 16.15:

- PostgreSQL container reached `healthy` and exposed port 5432.
- `python -m scripts.init_db` created real `projects` and `papers` tables.
- `/health/database` returned HTTP 200 with `{"status":"ok","database":"postgresql"}`.
- A real Project persisted after FastAPI was stopped and restarted.
- Real PubMed (`25315507`) and OpenAlex (`W2064815984`) records were saved.
- Re-saving the PubMed record returned `created: false` and produced no duplicate row.
- Project A contained only its PubMed paper; Project B contained only its OpenAlex paper.
- Removing a paper returned 204; deleting Project A removed its paper through database cascade.
- Automated test result: 16 passed, 0 failed.
- `npm run build` completed successfully for `/`, `/projects`, and `/projects/[projectId]`.

Local `.env`, `frontend/.env.local`, `node_modules`, `.next`, and the Docker volume are not committed.

## Local CORS Configuration

The backend accepts the Next.js development origins `http://127.0.0.1:3000` and `http://localhost:3000`. The former static-server port 5500 remains allowed for local compatibility.

## Task 6+ Readiness

Stable Project/Paper/Document IDs, project-scoped access, clean persisted document text, PostgreSQL sessions, and cascade behavior are now prepared for later chunking and metadata work. Chunking, embedding, pgvector, semantic search, RAG, citation generation, and complete research QA workflows are not implemented in Task 5.
