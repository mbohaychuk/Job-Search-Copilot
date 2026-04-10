"""Two-tier in-memory TTL cache for ephemeral search results."""

import time
from collections import OrderedDict
from typing import Any, Generic, TypeVar

from jsc.search.base import SearchPage

V = TypeVar("V")


class _LRUTtlStore(Generic[V]):
    """LRU-ordered dict with per-entry TTL expiration and a capacity cap."""

    def __init__(self, ttl: float, max_size: int) -> None:
        if max_size < 1:
            raise ValueError(f"max_size must be >= 1, got {max_size}")
        self._ttl = ttl
        self._max_size = max_size
        self._store: OrderedDict[str, tuple[V, float]] = OrderedDict()

    def get(self, key: str) -> V | None:
        item = self._store.get(key)
        if item is None:
            return None
        value, expires_at = item
        if time.monotonic() >= expires_at:
            del self._store[key]
            return None
        self._store.move_to_end(key)
        return value

    def put(self, key: str, value: V) -> None:
        if key in self._store:
            del self._store[key]
        while len(self._store) >= self._max_size:
            self._store.popitem(last=False)
        self._store[key] = (value, time.monotonic() + self._ttl)

    def sweep(self, now: float) -> None:
        expired = [k for k, (_, exp) in self._store.items() if now >= exp]
        for k in expired:
            del self._store[k]


class SearchCache:
    """Two-tier cache: query-level (SearchPage) and job-level (transient JobPosting).

    Both tiers use TTL-based expiration and LRU eviction when at capacity.
    """

    def __init__(self, settings: Any) -> None:
        self._queries: _LRUTtlStore[SearchPage] = _LRUTtlStore(
            ttl=settings.search_cache_query_ttl,
            max_size=settings.search_cache_max_queries,
        )
        self._jobs: _LRUTtlStore[Any] = _LRUTtlStore(
            ttl=settings.search_cache_job_ttl,
            max_size=settings.search_cache_max_jobs,
        )
        self._put_count = 0

    # --- Query tier ---

    def get_query(self, key: str) -> SearchPage | None:
        return self._queries.get(key)

    def put_query(self, key: str, page: SearchPage) -> None:
        self._queries.put(key, page)
        self._maybe_sweep()

    # --- Job tier ---

    def get_job(self, url_hash: str) -> Any | None:
        return self._jobs.get(url_hash)

    def put_job(self, url_hash: str, posting: Any) -> None:
        self._jobs.put(url_hash, posting)
        self._maybe_sweep()

    # --- Maintenance ---

    def sweep(self) -> None:
        """Remove all expired entries from both tiers."""
        now = time.monotonic()
        self._queries.sweep(now)
        self._jobs.sweep(now)

    def _maybe_sweep(self) -> None:
        """Periodic sweep — amortises cleanup cost over batches of writes."""
        self._put_count += 1
        if self._put_count >= 100:
            self._put_count = 0
            try:
                self.sweep()
            except Exception:
                pass  # never let maintenance corrupt a write path
