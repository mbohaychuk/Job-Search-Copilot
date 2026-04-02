"""OpenAI embedding provider implementation."""

from openai import AsyncOpenAI

from jsc.config import Settings

# text-embedding-3-small produces 1536-dim vectors by default
_DIMENSION_MAP = {
    "text-embedding-3-small": 1536,
    "text-embedding-3-large": 3072,
    "text-embedding-ada-002": 1536,
}


class OpenAIEmbeddingProvider:
    """Implements EmbeddingProvider using OpenAI's embedding API."""

    def __init__(self, settings: Settings) -> None:
        self._client = AsyncOpenAI(api_key=settings.openai_api_key)
        self._model = settings.openai_embedding_model
        self._dim = _DIMENSION_MAP.get(self._model, 1536)

    @property
    def dimension(self) -> int:
        return self._dim

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        # OpenAI supports batching — send all at once (up to ~8k tokens each)
        response = await self._client.embeddings.create(
            model=self._model,
            input=texts,
        )
        # Response items are in the same order as inputs
        return [item.embedding for item in response.data]
