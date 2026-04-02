"""Provider factory — creates AI providers based on configuration."""

from jsc.config import Settings
from jsc.providers.base import EmbeddingProvider, LLMProvider
from jsc.providers.openai_embeddings import OpenAIEmbeddingProvider
from jsc.providers.openai_llm import OpenAILLMProvider


def create_embedding_provider(settings: Settings) -> EmbeddingProvider:
    """Create an embedding provider based on settings.

    Currently only supports OpenAI. Add new providers here and
    switch on a config key (e.g. settings.embedding_provider = "openai" | "local").
    """
    return OpenAIEmbeddingProvider(settings)


def create_llm_provider(settings: Settings) -> LLMProvider:
    """Create an LLM provider based on settings."""
    return OpenAILLMProvider(settings)
