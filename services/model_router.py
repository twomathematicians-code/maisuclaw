"""
maisuclaw v0.3.0 — Unified Model Router
Routes requests to the correct provider (Ollama / Groq / OpenRouter).
"""

from typing import AsyncGenerator

from config import config
from services.ollama_client import ollama_client, OllamaError
from services.cloud_client import groq_client, openrouter_client, CloudModelError


class ModelRouter:
    """Routes chat requests to the appropriate model provider."""

    def __init__(self):
        self._ollama_checked = False

    async def _check_ollama(self):
        """Check Ollama availability once at startup."""
        if not self._ollama_checked:
            await ollama_client.health_check()
            self._ollama_checked = True

    async def chat_stream(
        self,
        messages: list[dict],
        model_id: str = "llama3",
        system_prompt: str = "",
        temperature: float = 0.7,
    ) -> AsyncGenerator[str, None]:
        """
        Stream chat from any provider.
        Automatically routes to the correct backend based on model config.
        """
        model_cfg = config.get_model(model_id)
        if not model_cfg:
            # Try Ollama as fallback
            await self._check_ollama()
            if ollama_client.is_available:
                async for chunk in ollama_client.chat_stream(
                    messages, model=model_id, system_prompt=system_prompt
                ):
                    yield chunk
            else:
                raise ValueError(f"Unknown model: {model_id}. No provider available.")
            return

        provider = model_cfg.provider

        if provider == "ollama":
            await self._check_ollama()
            async for chunk in ollama_client.chat_stream(
                messages, model=model_id, system_prompt=system_prompt
            ):
                yield chunk

        elif provider == "groq":
            async for chunk in groq_client.chat_stream(
                messages, model=model_id,
                temperature=temperature,
                max_tokens=model_cfg.max_tokens
            ):
                yield chunk

        elif provider == "openrouter":
            async for chunk in openrouter_client.chat_stream(
                messages, model=model_id,
                temperature=temperature,
                max_tokens=model_cfg.max_tokens
            ):
                yield chunk

        else:
            raise ValueError(f"Unknown provider: {provider}")

    async def get_provider_status(self) -> dict:
        """Get status of all providers."""
        await self._check_ollama()
        return {
            "ollama": {
                "available": ollama_client.is_available,
                "models": ollama_client.available_models,
                "url": ollama_client.base_url,
            },
            "groq": {
                "available": groq_client.is_available,
                "has_api_key": bool(groq_client.api_key),
            },
            "openrouter": {
                "available": openrouter_client.is_available,
                "has_api_key": bool(openrouter_client.api_key),
            },
        }


# Global router
model_router = ModelRouter()
