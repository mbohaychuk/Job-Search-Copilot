# Ephemeral Search Layer — Design Spec

## Problem

The current ingestion system is a company-by-company crawl model. Users must manually register each job source (Greenhouse board, Lever slug, career page URL) and trigger collection. There is no way to search broadly across the job market — only to monitor sources you already know about.

Job aggregator APIs like Adzuna solve this, but their terms of service prohibit persisting results to a database for ongoing use. We need an architecture that supports on-demand, ephemeral job search alongside the existing stored ingestion pipeline.

## Decision

Add a parallel **ephemeral search layer** (`search/` module) that queries external aggregator APIs on demand, caches results in memory, runs them through the existing ranking pipeline, and returns them without database persistence. Adzuna is the first provider; the architecture supports any number of additional providers.

Results are cached in-memory with TTLs — legally ephemeral (not persisted to disk/DB) but practically available for the duration of a user session.

## Architecture

### Module Structure

```
src/jsc/
  search/                              # NEW module
    __init__.py
    base.py                            # SearchProvider protocol, dataclasses
    registry.py                        # provider registry
    cache.py                           # two-tier in-memory TTL cache
    service.py                         # SearchService orchestrator
    providers/
      __init__.py
      adzuna.py                        # first provider
  api/
    search.py                          # NEW: GET /api/v1/search
  schemas/
    search.py                          # NEW: response schemas
```

### Reused Components (no changes needed)

| Component | Reuse |
|---|---|
| `JobNormalizer` | Enrich ephemeral results with seniority, remote type, skills |
| `RankingPipeline` + all 5 scorers | Rank ephemeral results against candidate profile |
| `EmbeddingProvider` | Generate embeddings on the fly |
| `SkillTaxonomy` | Skill extraction from descriptions |
| `ParsedJob` dataclass | Adzuna provider outputs `ParsedJob`, same as ingestion adapters |
| `Fetcher` | HTTP calls with rate limiting, retries, SSRF protection |
| `Settings` | Extended with Adzuna config fields |
| `verify_api_key` | Search endpoint uses same auth |
| `Paginated[T]` | Pagination wrapper |
| `MatchExplanation` | Ranking explanation schema |
| `JobSkillRead` | Skill schema |
| `url_hash()` | Stable ID generation for ephemeral jobs |

### Modified Files

| File | Change |
|---|---|
| `config.py` | Add `adzuna_app_id`, `adzuna_app_key`, cache TTL/size settings |
| `dependencies.py` | Add `get_search_cache` (singleton), `get_search_service` (per-request) |
| `main.py` | Register search router |

## Data Flow

```
GET /api/v1/search?q=python&location=Calgary&candidate_id=...
  -> SearchService.search(query, candidate_id)
    -> cache.get_query(query)  ->  HIT?  -> skip to ranking
    -> provider.search(query, fetcher)  ->  list[ParsedJob]
    -> JobNormalizer.normalize(each)  ->  enriched ParsedJob
    -> build transient JobPosting + JobSkill objects (in-memory, no DB)
    -> EmbeddingProvider.embed(descriptions)  ->  attach embeddings
    -> cache.put_query(query, results) + cache.put_jobs(each)
    -> RankingPipeline.rank(candidate, transient_jobs)  ->  ranked results
    -> serialize to SearchResponse
  -> return response
```

The ranking pipeline receives transient (detached) `JobPosting` ORM instances. All 5 scorers only read attributes from `JobPosting` — they never issue DB queries — so transient objects work without modification.

## SearchProvider Protocol

```python
class SearchProvider(Protocol):
    name: str

    async def search(self, query: SearchQuery, fetcher: Fetcher) -> SearchPage:
        ...
```

### SearchQuery

```python
@dataclass
class SearchQuery:
    keywords: str                      # "python developer"
    location: str | None = None        # "Calgary"
    country: str = "ca"                # two-letter country code
    remote_only: bool = False
    page: int = 1
    page_size: int = 20
```

### SearchPage

```python
@dataclass
class SearchPage:
    results: list[ParsedJob]           # reuses existing dataclass
    total: int                         # total across all pages
    page: int
    page_size: int
    provider: str                      # "adzuna"
    attribution: Attribution | None    # ToS-required attribution info
```

### Attribution

```python
@dataclass
class Attribution:
    text: str                          # "Jobs by Adzuna"
    url: str                           # "https://www.adzuna.com"
```

## Two-Tier Cache

All in-memory, no external dependencies.

### Tier 1 — Query Cache

- **Key**: hash of (provider, keywords, location, country, remote_only, page, page_size)
- **Value**: `SearchPage`
- **TTL**: 1 hour (configurable via `search_cache_query_ttl`)
- **Max entries**: 1000 (configurable via `search_cache_max_queries`)

Prevents duplicate API calls when a user re-runs the same search or navigates back.

### Tier 2 — Job Cache

- **Key**: `url_hash(job_url)` (reuses existing utility)
- **Value**: Transient `JobPosting` with embedding and skills already computed
- **TTL**: 4 hours (configurable via `search_cache_job_ttl`)
- **Max entries**: 5000 (configurable via `search_cache_max_jobs`)

Avoids re-normalizing and re-embedding the same job when it appears across different searches. Longer TTL than query cache because individual job content doesn't change.

### Eviction

- On each `get()`: check if the entry has expired, return `None` if so.
- Every 100 `put()` calls: sweep all expired entries.
- When at max capacity: evict oldest entries first (LRU).

## Adzuna Provider

### API Endpoint

```
GET https://api.adzuna.com/v1/api/jobs/{country}/search/{page}
    ?app_id={adzuna_app_id}
    &app_key={adzuna_app_key}
    &what={keywords}
    &where={location}
    &results_per_page={page_size}
```

### Field Mapping

| Adzuna field | ParsedJob field |
|---|---|
| `title` | `title` |
| `company.display_name` | `company` |
| `location.display_name` | `location` |
| `description` | `description_text` |
| `redirect_url` | `metadata["url"]` |
| `salary_min` | `salary_min` |
| `salary_max` | `salary_max` |
| `created` | `posted_at` |
| `category.label` | `department` |

### Configuration

```python
# In Settings (config.py)
adzuna_app_id: str = ""
adzuna_app_key: str = ""
```

Provider raises a clear error if credentials are not configured.

### Attribution (ToS Compliance)

Adzuna requires "Jobs by Adzuna" (min 116x23px) with hyperlink. The API response includes an `attribution` object so the frontend knows what to render. This keeps compliance in the response contract.

## API Endpoint

### `GET /api/v1/search`

| Param | Type | Required | Default | Description |
|---|---|---|---|---|
| `q` | str | yes | — | Search keywords |
| `location` | str | no | — | City/region |
| `country` | str | no | `"ca"` | Two-letter country code |
| `remote_only` | bool | no | `false` | Filter to remote jobs only |
| `candidate_id` | UUID | yes | — | Candidate profile for ranking |
| `page` | int | no | `1` | Page number |
| `page_size` | int | no | `20` | Results per page (max 50) |

`candidate_id` is required — the user must have a profile before searching. The endpoint returns 400 if the candidate doesn't exist.

### Response Schema

```python
class SearchResultRead(BaseModel):
    id: str                            # url_hash — stable cache identifier
    title: str
    company: str
    location: str
    is_remote: bool
    remote_type: str | None
    seniority: str | None
    posted_at: datetime | None
    url: str                           # link to original posting
    skills: list[JobSkillRead]         # reused schema
    salary_min: int | None
    salary_max: int | None
    salary_currency: str | None
    provider: str                      # "adzuna"
    match_score: float                 # always present (candidate required)
    match_explanation: MatchExplanation # always present

class SearchAttribution(BaseModel):
    text: str                          # "Jobs by Adzuna"
    url: str                           # link to adzuna.com

class SearchResponse(BaseModel):
    items: list[SearchResultRead]
    total: int
    page: int
    page_size: int
    pages: int
    attribution: SearchAttribution | None
```

## Fetcher Lifecycle

The existing `Fetcher` is an async context manager (manages an `httpx.AsyncClient`). The `SearchService.search()` method creates a `Fetcher` per-call:

```python
async with Fetcher(self._settings) as fetcher:
    page = await provider.search(query, fetcher)
```

This matches how the `IngestionCoordinator` uses it — one `Fetcher` per `run()` call.

## Dependency Injection

```python
# Singleton — lives for app lifetime (holds the in-memory cache)
@lru_cache
def get_search_cache(settings) -> SearchCache:
    return SearchCache(settings)

# Per-request — needs fresh DB session to load candidate
def get_search_service(
    session,                           # load candidate for ranking
    settings,
    search_cache,                      # singleton
    normalizer,                        # reused
    embedding_provider,                # reused
    ranking_pipeline,                  # reused
) -> SearchService:
    ...
```

`SearchCache` is app-scoped (singleton). `SearchService` is request-scoped (needs DB session). This follows the same pattern as existing dependencies.

## Settings Additions

```python
# Search providers
adzuna_app_id: str = ""
adzuna_app_key: str = ""

# Search cache
search_cache_query_ttl: int = 3600     # 1 hour, seconds
search_cache_job_ttl: int = 14400      # 4 hours, seconds
search_cache_max_queries: int = 1000
search_cache_max_jobs: int = 5000
```

## Future Providers

Adding a new ephemeral provider (e.g., The Muse, Remotive, RemoteOK) requires:

1. Create `search/providers/the_muse.py` implementing `SearchProvider`
2. Register it in `search/registry.py`
3. Add any provider-specific settings to `config.py`

No changes needed to the cache, service, API endpoint, or ranking pipeline.
