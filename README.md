# Job Search Copilot

Resume-to-Job Match Analyzer — discovers software development job postings in Edmonton and Calgary, normalizes them, and ranks them against your resume using a hybrid scoring pipeline.

---

## Overview

Single-user MVP that:
1. **Collects** job postings from Greenhouse, Lever, career pages, and generic HTML sources
2. **Parses** your resume (PDF/DOCX) into a structured candidate profile
3. **Normalizes** job data: title, skills, seniority, location, remote status
4. **Ranks** jobs using a hybrid scoring pipeline (semantic similarity + deterministic feature scoring)
5. **Explains** why each job matches or doesn't match your profile

This is **not** an auto-apply bot. No cover letters, no form filling, no browser automation.

---

## Tech Stack

- **Python 3.12+** with **FastAPI**
- **PostgreSQL 16** with **pgvector** for embeddings
- **SQLAlchemy 2** (async) + **Alembic** for migrations
- **Pydantic v2** for schemas and config
- **OpenAI** (text-embedding-3-small + GPT-4o-mini) — provider-swappable
- **httpx** for async HTTP, **BeautifulSoup** / **selectolax** for parsing
- **Docker Compose** for local development

---

## Architecture

```
API (FastAPI)
 └── Services (resume, job, match, search)
      ├── Ingestion Pipeline (stored jobs)
      │    ├── Fetcher (httpx + robots.txt + rate limiting)
      │    ├── Source Adapters (Greenhouse, Lever, career page, generic HTML)
      │    └── Normalizer (skill extraction, seniority, remote detection)
      ├── Ephemeral Search Pipeline (on-demand, not persisted)
      │    ├── Search Providers (Adzuna, ...)
      │    ├── In-Memory Cache (query-level + job-level TTL)
      │    └── Reuses: Fetcher, Normalizer, Embedding, Ranking
      ├── Parsing Pipeline
      │    ├── Resume Parser (PyMuPDF, python-docx)
      │    └── Profile Extractor (LLM-based structured extraction)
      └── Ranking Pipeline
           ├── Semantic Similarity (40%) — cosine of embeddings
           ├── Skill Coverage (25%) — deterministic skill set overlap
           ├── Title/Role Match (15%) — role family + token similarity
           ├── Seniority Match (10%) — level distance scoring
           └── Location/Remote Fit (10%) — rules-based
```

---

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Python 3.12+
- An OpenAI API key (for embeddings and LLM extraction)

### 1. Clone and configure

```bash
git clone https://github.com/mbohaychuk/Job-Search-Copilot.git
cd Job-Search-Copilot
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY
```

### 2. Start the database

```bash
docker compose up -d db
```

### 3. Install dependencies

```bash
pip install -e ".[dev]"
```

### 4. Run migrations

```bash
alembic upgrade head
```

### 5. Start the API

```bash
uvicorn jsc.main:create_app --factory --reload
```

The API is now at http://localhost:8000. OpenAPI docs at http://localhost:8000/docs.

### 6. Run tests

```bash
pytest
```

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Liveness check |
| GET | `/ready` | Readiness check (DB) |
| POST | `/api/v1/candidates/upload-resume` | Upload PDF/DOCX resume |
| GET | `/api/v1/candidates/{id}` | Get candidate profile |
| PUT | `/api/v1/candidates/{id}` | Update candidate preferences |
| POST | `/api/v1/jobs/collect` | Trigger job collection |
| GET | `/api/v1/jobs` | List jobs (paginated, filterable) |
| GET | `/api/v1/jobs/{id}` | Job detail |
| GET | `/api/v1/jobs/sources` | List configured sources |
| POST | `/api/v1/jobs/sources` | Add a job source |
| GET | `/api/v1/search` | Ephemeral job search (Adzuna, etc.) |
| POST | `/api/v1/matches/{candidate_id}/rank` | Trigger ranking |
| GET | `/api/v1/matches/{candidate_id}` | Ranked match list |
| GET | `/api/v1/matches/{candidate_id}/jobs/{job_id}` | Match detail + explanation |

---

## File Responsibilities

| Directory | Purpose |
|-----------|---------|
| `src/jsc/api/` | FastAPI routers and endpoint handlers |
| `src/jsc/db/models/` | SQLAlchemy ORM models |
| `src/jsc/schemas/` | Pydantic request/response schemas |
| `src/jsc/services/` | Business logic orchestration |
| `src/jsc/ingestion/` | Job discovery, fetching, adapter registry (stored jobs) |
| `src/jsc/search/` | Ephemeral search providers and in-memory cache |
| `src/jsc/parsing/` | Resume parsing, profile extraction, job normalization, skill taxonomy |
| `src/jsc/ranking/` | Scoring pipeline, individual scorers, explainer |
| `src/jsc/providers/` | AI provider abstractions (embedding, LLM) |
| `src/jsc/utils/` | Text, URL, robots.txt utilities |
| `migrations/` | Alembic database migrations |
| `tests/` | Unit and integration tests |

---

## Design Decisions

- **Hybrid ranking over pure-LLM**: Cheaper, faster, explainable, and tunable
- **Shared skill taxonomy**: Canonical skill names with aliases enable deterministic matching
- **Raw storage**: Original job HTML/JSON preserved for re-parsing without re-crawling
- **Provider abstraction**: Swap OpenAI for any embedding/LLM provider by implementing one class
- **Pre-computed embeddings**: No API calls at ranking time — just vector math
- **Configurable weights**: Scoring weights tunable via environment variables
- **Ephemeral search layer for aggregator APIs**: Major job aggregators (Adzuna, etc.) prohibit persisting search results to a database under their free-tier terms of service. Rather than violating ToS or paying for enterprise licenses, we built a separate **ephemeral search layer** that queries aggregator APIs on demand, caches results in-memory with TTLs (query-level: 1 hour, job-level: 4 hours), and runs them through the full ranking pipeline — all without writing a single row to the database. This keeps us ToS-compliant while still delivering ranked, personalized results. The in-memory cache prevents redundant API calls and avoids re-computing embeddings for the same job across different searches. See [`docs/superpowers/specs/2026-04-09-ephemeral-search-design.md`](docs/superpowers/specs/2026-04-09-ephemeral-search-design.md) for the full design.

### Why not just scrape Indeed/LinkedIn?

We investigated every major job data source as of April 2026. Indeed's API was shut down in 2019 with no replacement. LinkedIn's Jobs API requires partner approval (no personal access) and they actively pursue legal action against scrapers. Glassdoor's API was shut down after the Indeed merger. Google for Jobs has no public API. These are all dead ends for a personal project. Adzuna's free API (250 requests/day, 16+ countries) provides the best coverage-to-effort ratio, with The Muse, Remotive, and RemoteOK as supplemental free sources.

---

## Future Improvements

- Background job queue (arq + Redis) for async collection
- Frontend (React or HTMX)
- Scheduled crawls
- Additional ephemeral search providers (The Muse, Remotive, RemoteOK)
- Additional ATS adapters (SmartRecruiters, Ashby, Workable)
- User feedback loop for weight tuning
- Salary estimation

---

## License

This project is licensed under the MIT License — see the license file for details.

---

## Authors

Mark Bohaychuk
https://github.com/mbohaychuk

Justin Norton
https://github.com/JustinN9
