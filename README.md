# AI Research Assistant Platform

## Project

AI Research Assistant Platform is a modular research-support application for researchers. The long-term project will explore literature search, research knowledge management, RAG, and AI-assisted research workflows.

## Current Version

V1 Prototype

## Current Stage

Day 3 — Project Workspace and Literature Management

The application searches real PubMed and OpenAlex metadata, manages research Projects, and saves provider-independent papers into a project-scoped PostgreSQL library. PDF processing, chunking, embeddings, pgvector, RAG, LLM calls, and agents are intentionally not included yet.

The original static HTML/CSS/JavaScript behavior and visual style have been migrated to a minimal Next.js App Router frontend.

## Architecture

```text
Next.js App Router frontend
  ├── Literature Search → GET /api/literature/search
  │     ├── PubMed: ESearch → EFetch → XML parser
  │     └── OpenAlex: Works search → JSON parser
  ├── Project workspace → /projects CRUD
  └── Save Paper → /projects/{project_id}/papers
                           ↓
                    FastAPI routes
                           ↓
                 Project/Paper services
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
│   │       ├── literature.py
│   │       ├── papers.py
│   │       └── projects.py
│   ├── models/project.py
│   ├── schemas/
│   │   ├── literature.py
│   │   └── projects.py
│   ├── services/literature/
│   │   ├── literature_service.py
│   │   ├── openalex_service.py
│   │   └── pubmed_service.py
│   ├── services/paper_service.py
│   ├── services/project_service.py
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
| `backend/api/routes/` | Literature, Project, and saved-paper HTTP endpoints |
| `backend/models/` | SQLAlchemy Project and Paper tables |
| `backend/services/literature/` | Existing PubMed/OpenAlex integrations |
| `backend/services/project_service.py` | Project CRUD operations |
| `backend/services/paper_service.py` | Paper persistence and deduplication |
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

The suite checks Day 1 regression behavior, Day 2 request validation/provider parsers, Project CRUD, PubMed/OpenAlex save payloads, external-id and DOI deduplication, Project A/Project B isolation, paper removal, the Next.js App Router structure, and frontend API paths. Unit/API tests use a deterministic in-memory SQLAlchemy test engine; the real PostgreSQL verification below is run separately.

Verify the frontend production build separately:

```powershell
Set-Location frontend
npm run build
```

## Day 3 Acceptance Verification

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

## Day 4 Readiness

Stable Project IDs, project-scoped Paper IDs, PostgreSQL configuration, SQLAlchemy sessions, cascade behavior, and a persistent literature library are now prepared for later PDF, chunking, embedding, pgvector, and RAG work. Those Day 4 features are not implemented here.
