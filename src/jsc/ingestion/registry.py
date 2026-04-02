"""Adapter registry — maps adapter_type strings to adapter classes."""

from jsc.ingestion.adapters.career_page import CareerPageAdapter
from jsc.ingestion.adapters.generic_html import GenericHTMLAdapter
from jsc.ingestion.adapters.greenhouse import GreenhouseAdapter
from jsc.ingestion.adapters.lever import LeverAdapter
from jsc.ingestion.base import SourceAdapter

_ADAPTERS: dict[str, type] = {
    "greenhouse": GreenhouseAdapter,
    "lever": LeverAdapter,
    "career_page": CareerPageAdapter,
    "generic_html": GenericHTMLAdapter,
}


def get_adapter(adapter_type: str) -> SourceAdapter:
    """Get an adapter instance by type name.

    Raises KeyError if the adapter type is not registered.
    """
    cls = _ADAPTERS.get(adapter_type)
    if cls is None:
        raise KeyError(
            f"Unknown adapter type: {adapter_type!r}. "
            f"Available: {sorted(_ADAPTERS.keys())}"
        )
    return cls()


def register_adapter(adapter_type: str, cls: type) -> None:
    """Register a new adapter type at runtime."""
    _ADAPTERS[adapter_type] = cls
