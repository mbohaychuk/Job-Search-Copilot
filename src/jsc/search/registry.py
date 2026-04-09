"""Search provider registry — maps provider names to instances."""

from typing import Any

from jsc.search.base import SearchProvider
from jsc.search.providers.adzuna import AdzunaProvider

_PROVIDERS: dict[str, type] = {
    "adzuna": AdzunaProvider,
}


def get_provider(name: str, settings: Any) -> SearchProvider:
    """Get a provider instance by name. Raises KeyError if not registered."""
    cls = _PROVIDERS.get(name)
    if cls is None:
        raise KeyError(
            f"Unknown search provider: {name!r}. "
            f"Available: {sorted(_PROVIDERS.keys())}"
        )
    return cls(settings)


def register_provider(name: str, cls: type) -> None:
    """Register a search provider."""
    _PROVIDERS[name] = cls


def available_providers() -> list[str]:
    """Return names of all registered providers."""
    return sorted(_PROVIDERS.keys())
