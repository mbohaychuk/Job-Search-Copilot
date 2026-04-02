"""Abstract protocols for AI model providers."""

from typing import Any, Protocol

from pydantic import BaseModel


class EmbeddingProvider(Protocol):
    """Generates vector embeddings from text."""

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts. Returns list of float vectors."""
        ...

    @property
    def dimension(self) -> int:
        """Dimensionality of the embedding vectors."""
        ...


class LLMProvider(Protocol):
    """Sends completion requests to a language model."""

    async def complete(
        self,
        prompt: str,
        *,
        system: str | None = None,
        response_schema: type[BaseModel] | None = None,
        temperature: float = 0.0,
        max_tokens: int = 2000,
    ) -> str:
        """Send a completion request. Returns the response text."""
        ...
