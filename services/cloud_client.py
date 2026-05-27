"""
maisuclaw v0.3.0 — Cloud Model Client
Supports Groq and OpenRouter for free cloud-based AI inference.
Uses OpenAI-compatible API format.
"""

import httpx
import json
from typing import AsyncGenerator, Optional

from config import GROQ_API_KEY, GROQ_BASE_URL, OPENROUTER_API_KEY, OPENROUTER_BASE_URL


class CloudModelError(Exception):
    """Custom exception for cloud model errors."""
    def __init__(self, message: str, provider: str = "", status_code: int = 0):
        self.message = message
        self.provider = provider
        self.status_code = status_code
        super().__init__(self.message)


class GroqClient:
    """Groq API client — free tier, blazing fast inference."""

    def __init__(self, api_key: str = GROQ_API_KEY, base_url: str = GROQ_BASE_URL):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = 120

    @property
    def is_available(self) -> bool:
        return bool(self.api_key)

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def chat_stream(
        self,
        messages: list[dict],
        model: str = "llama-3.3-70b-versatile",
        temperature: float = 0.7,
        max_tokens: int = 8192,
    ) -> AsyncGenerator[str, None]:
        """Stream chat completion from Groq."""
        if not self.is_available:
            raise CloudModelError(
                "Groq API key not set. Set GROQ_API_KEY environment variable. "
                "Get a free key at https://console.groq.com/",
                provider="groq"
            )

        payload = {
            "model": model,
            "messages": messages,
            "stream": True,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/chat/completions",
                    json=payload,
                    headers=self._headers()
                ) as resp:
                    if resp.status_code != 200:
                        body = await resp.aread()
                        raise CloudModelError(
                            f"Groq API error {resp.status_code}: {body.decode()[:500]}",
                            provider="groq",
                            status_code=resp.status_code
                        )
                    async for line in resp.aiter_lines():
                        if not line.strip() or not line.startswith("data: "):
                            continue
                        data_str = line[6:]
                        if data_str.strip() == "[DONE]":
                            break
                        try:
                            data = json.loads(data_str)
                            content = data.get("choices", [{}])[0].get("delta", {}).get("content", "")
                            if content:
                                yield content
                        except json.JSONDecodeError:
                            continue

        except httpx.ConnectError:
            raise CloudModelError(
                "Cannot connect to Groq API. Check your internet connection.",
                provider="groq"
            )
        except httpx.TimeoutException:
            raise CloudModelError(
                "Groq API request timed out.",
                provider="groq"
            )

    async def list_models(self) -> list[str]:
        """List available Groq models."""
        if not self.is_available:
            return []
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"{self.base_url}/models", headers=self._headers())
                if resp.status_code == 200:
                    data = resp.json()
                    return [m["id"] for m in data.get("data", [])]
                return []
        except Exception:
            return []


class OpenRouterClient:
    """OpenRouter API client — access to many free models."""

    def __init__(self, api_key: str = OPENROUTER_API_KEY, base_url: str = OPENROUTER_BASE_URL):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = 120

    @property
    def is_available(self) -> bool:
        return bool(self.api_key)

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://maisuclaw.local",
            "X-Title": "MaisuClaw",
        }

    async def chat_stream(
        self,
        messages: list[dict],
        model: str = "meta-llama/llama-3.1-8b-instruct:free",
        temperature: float = 0.7,
        max_tokens: int = 8192,
    ) -> AsyncGenerator[str, None]:
        """Stream chat completion from OpenRouter."""
        if not self.is_available:
            raise CloudModelError(
                "OpenRouter API key not set. Set OPENROUTER_API_KEY environment variable. "
                "Get a free key at https://openrouter.ai/keys",
                provider="openrouter"
            )

        payload = {
            "model": model,
            "messages": messages,
            "stream": True,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/chat/completions",
                    json=payload,
                    headers=self._headers()
                ) as resp:
                    if resp.status_code != 200:
                        body = await resp.aread()
                        raise CloudModelError(
                            f"OpenRouter API error {resp.status_code}: {body.decode()[:500]}",
                            provider="openrouter",
                            status_code=resp.status_code
                        )
                    async for line in resp.aiter_lines():
                        if not line.strip() or not line.startswith("data: "):
                            continue
                        data_str = line[6:]
                        if data_str.strip() == "[DONE]":
                            break
                        try:
                            data = json.loads(data_str)
                            content = data.get("choices", [{}])[0].get("delta", {}).get("content", "")
                            if content:
                                yield content
                        except json.JSONDecodeError:
                            continue

        except httpx.ConnectError:
            raise CloudModelError(
                "Cannot connect to OpenRouter API. Check your internet connection.",
                provider="openrouter"
            )
        except httpx.TimeoutException:
            raise CloudModelError(
                "OpenRouter API request timed out.",
                provider="openrouter"
            )


# Global instances
groq_client = GroqClient()
openrouter_client = OpenRouterClient()
