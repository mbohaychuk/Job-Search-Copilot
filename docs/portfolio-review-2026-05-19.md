# Portfolio review notes — 2026-05-19

Notes collected while preparing this project for portfolio capture.

Severity legend:
- 🔴 **Blocker** — would prevent a recruiter from running or evaluating the project
- 🟠 **Embarrassing** — visible to anyone who clones the repo; should be fixed before sharing
- 🟡 **Polish** — minor UX, docs, or code quality
- 🟢 **Idea** — not a defect; potential improvement to discuss

## 🔴 Blockers

_None found._ The app boots cleanly with no `.env` (all settings have sensible defaults), `/docs` and `/openapi.json` serve correctly, and `migrations/versions/f95cedc17fd1_initial_schema.py` exists so `alembic upgrade head` produces a real schema.

## 🟠 Embarrassing

### 1. The portfolio page promised a UI the project does not have
`Portfolio-Site/projects/job-search-copilot.html` previously said the media would be a "Ranked job list with explanation panel". The project is API-only — there is no frontend, no rendered job list, no panel. The portfolio page has now been updated to be honest about this (it shows the FastAPI docs + the `/search` endpoint schema, with a caption stating the UI is a planned module). Decide whether you want to (a) build a minimal results UI, or (b) keep the API-first framing. Either is fine — but the page text and the repo should agree.

## 🟡 Polish

### 2. Two near-identical grade functions
`src/jsc/api/matches.py:16` defines `_grade_from_score`; `src/jsc/ranking/explainer.py:6` defines `_grade`. Both map a 0–1 score to the same letter-grade ladder (A+/A/B+/B/C/D/F) with identical thresholds. They are byte-for-byte equivalent logic in two places — if you ever retune the thresholds, one will silently drift. Consolidate into a single shared helper (e.g. `jsc/ranking/grading.py`).

### 3. `JobPosting.source_id` is `NOT NULL` but the ephemeral search path constructs transient postings with `source_id=None`
`src/jsc/db/models/job.py` declares `source_id` as a non-nullable FK. `src/jsc/search/service.py` builds transient `JobPosting` objects with `source_id=None` for ranking-only use. This works *today* only because those transient objects are never flushed to the DB. It is a latent trap: any future change that accidentally adds one of these objects to a session will fail with an opaque integrity error. Either make `source_id` nullable, or use a dedicated non-ORM dataclass for transient search results so the model invariant can't be violated.

### 4. Embedding failures degrade silently
`src/jsc/search/service.py` (around the embedding call) catches embedding exceptions and only logs a `warning`. If OpenAI is unreachable, every semantic score silently becomes 0 and the search returns results ranked only by the deterministic components — with no signal to the caller that semantic ranking was skipped. Consider surfacing a flag in the `SearchResponse` (e.g. `semantic_ranking: false`) so a consumer knows the results are degraded.

## 🟢 Ideas

### 5. A `/ready` check that actually probes the DB
`/ready` returns a `ReadinessCheck` with a `db: bool`. Confirm it actually round-trips a query rather than just reporting engine existence — a readiness probe that can't detect a dead DB isn't doing its job. (Not verified during this review; flagged to check.)

### 6. The API is genuinely demo-ready — consider a thin results page
The OpenAPI surface is clean and the `match_explanation` schema (components, weighted scores, strengths, gaps) is the most impressive part of the project. A single static HTML page that calls `/search` and renders that explanation would turn this from "a backend" into "a product" for portfolio purposes — and it's a small amount of work relative to the backend that already exists.
