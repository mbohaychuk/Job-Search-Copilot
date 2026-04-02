"""OpenAI LLM provider implementation."""

import json

from openai import AsyncOpenAI
from pydantic import BaseModel

from jsc.config import Settings


class OpenAILLMProvider:
    """Implements LLMProvider using OpenAI's chat completion API."""

    def __init__(self, settings: Settings) -> None:
        self._client = AsyncOpenAI(api_key=settings.openai_api_key)
        self._model = settings.openai_llm_model

    async def complete(
        self,
        prompt: str,
        *,
        system: str | None = None,
        response_schema: type[BaseModel] | None = None,
        temperature: float = 0.0,
        max_tokens: int = 2000,
    ) -> str:
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        kwargs: dict = {
            "model": self._model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        # If a Pydantic schema is provided, request structured JSON output
        if response_schema is not None:
            kwargs["response_format"] = {"type": "json_object"}
            # Append schema hint to system message so the model knows the shape
            schema_json = json.dumps(response_schema.model_json_schema(), indent=2)
            schema_instruction = (
                f"\nRespond with valid JSON matching this schema:\n{schema_json}"
            )
            if system:
                messages[0]["content"] += schema_instruction
            else:
                messages.insert(0, {"role": "system", "content": schema_instruction})

        response = await self._client.chat.completions.create(**kwargs)
        content = response.choices[0].message.content
        return content or ""
