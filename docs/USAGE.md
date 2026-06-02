# Using Job-Search-Copilot

## What this is

A resume-to-job match analyzer for software roles in Edmonton and Calgary. It
ingests jobs, parses your resume, and ranks each posting with a hybrid score
(embedding similarity + deterministic feature scoring) plus an explanation.

**No web UI.** It is an API only — explore it via Swagger at `/docs`.

## Prerequisites

- Docker (for Postgres + pgvector)
- Python 3.12+ (a `.venv` ships in the repo for local dev)
- An OpenAI API key — required for resume parsing, job-embedding, and ranking.
  Without it, listing endpoints work but ingest/rank/search return errors.
- Optional: Adzuna `APP_ID` / `APP_KEY` for the ephemeral `/search` endpoint.

## First-time setup

1. Copy the env template and edit it:
   ```bash
   cp .env.example .env
   ```
   Then in `.env`:
   - Set `DATABASE_URL` host port to `5434` (5432 / 5433 are used by other
     local stacks):
     `DATABASE_URL=postgresql+asyncpg://jsc:devpassword@localhost:5434/jsc`
   - Set `OPENAI_API_KEY=sk-...`
   - **Delete the `POSTGRES_PASSWORD=` line.** `Settings` is strict and
     rejects unknown env keys (see "Known issues" below).

2. Start Postgres + pgvector on port 5434 (the bundled `docker-compose.yml`
   hardcodes 5432, so run the image directly):
   ```bash
   docker run -d --name jsc-pg -p 5434:5432 \
     -e POSTGRES_DB=jsc -e POSTGRES_USER=jsc -e POSTGRES_PASSWORD=devpassword \
     pgvector/pgvector:pg16
   ```

3. Install deps (or reuse the existing `.venv` in the repo):
   ```bash
   pip install -e ".[dev]"
   ```

4. Apply migrations:
   ```bash
   .venv/bin/alembic upgrade head
   ```

## Run it

Port 8000 may be taken (Briefer's ml-service binds to it). Use 8001:

```bash
.venv/bin/uvicorn jsc.main:create_app --factory --host 127.0.0.1 --port 8001
```

Open Swagger: <http://127.0.0.1:8001/docs>.

Liveness/readiness:
```bash
curl http://127.0.0.1:8001/health    # {"status":"ok"}
curl http://127.0.0.1:8001/ready     # {"status":"ready","db":true}
```

## Try it out

Smoke-test list endpoints (no OpenAI key needed):
```bash
curl 'http://127.0.0.1:8001/api/v1/jobs?limit=5'        # empty page
curl 'http://127.0.0.1:8001/api/v1/jobs/sources'         # []
```

Full flow (requires `OPENAI_API_KEY`):

1. `POST /api/v1/candidates/upload-resume` with a PDF or DOCX — returns a
   `candidate_id`. The handler calls OpenAI to extract a structured profile,
   so a missing/invalid key fails here.
2. `POST /api/v1/jobs/sources` to register a Greenhouse/Lever source.
3. `POST /api/v1/jobs/collect` to crawl + embed.
4. `POST /api/v1/matches/{candidate_id}/rank` to score all jobs.
5. `GET /api/v1/matches/{candidate_id}` for the ranked list,
   `GET /api/v1/matches/{candidate_id}/jobs/{job_id}` for the explanation.

Ephemeral aggregator search (Adzuna creds required):
`GET /api/v1/search?q=python&candidate_id=...&location=Edmonton`.

## Known issues / gotchas

- **No web UI** — it is an API. Use `/docs` (Swagger).
- **Duplicate `_grade` / `_grade_from_score` helpers** with identical bucket
  logic: `src/jsc/ranking/explainer.py:6` and `src/jsc/api/matches.py:16`.
  Should be consolidated into one shared helper.
- **`source_id` nullable mismatch.** The model `JobPosting.source_id` is
  `Mapped[UUID]` (non-Optional) and the migration column is `nullable=False`
  (`src/jsc/db/models/job.py:44`, `migrations/versions/f95cedc17fd1_initial_schema.py:79`),
  but the ephemeral search path constructs a `JobPosting` with
  `source_id=None` at `src/jsc/search/service.py:179`. Type-check disagrees
  with the schema; any code path that tries to persist that object would
  raise a NOT NULL violation.
- **`.env.example` ships a `POSTGRES_PASSWORD` key** that the strict
  `Settings` model rejects with `extra_forbidden`. Remove the line from
  `.env`, or the API/alembic won't boot.
- **`docker-compose.yml` hardcodes port 5432** with no env override. The
  workaround above (`docker run -p 5434:5432 ...`) sidesteps it. `compose up`
  as-is will collide with a host Postgres.
- **Port 8000 may be taken** by Briefer's ml-service. Run uvicorn on 8001.
- The Adzuna provider needs `ADZUNA_APP_ID` and `ADZUNA_APP_KEY`; without
  them `/api/v1/search` 4xx-errors.

## Stop / cleanup

```bash
pkill -f 'uvicorn jsc.main' || true
docker rm -f jsc-pg
```

To wipe DB state on next run, also remove the container's anonymous volume
(none was created above since we did not mount one — fresh container starts
fresh).
