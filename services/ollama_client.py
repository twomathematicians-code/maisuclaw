"""
maisuclaw v0.3.0 — Ollama Client
Handles local Ollama API with proper error handling and health checks.
"""

import httpx
import asyncio
import json
from typing import AsyncGenerator, Optional

from config import OLLAMA_BASE_URL, OLLAMA_TIMEOUT


class OllamaError(Exception):
    """Custom exception for Ollama-specific errors."""
    def __init__(self, message: str, status_code: int = 0):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class OllamaClient:
    """Async Ollama API client with health checking."""

    def __init__(self, base_url: str = OLLAMA_BASE_URL, timeout: int = OLLAMA_TIMEOUT):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._available = None
        self._available_models = []

    async def health_check(self) -> bool:
        """Check if Ollama server is reachable. Returns True if healthy."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self.base_url}/api/tags")
                if resp.status_code == 200:
                    data = resp.json()
                    self._available_models = [
                        m.get("name", "") for m in data.get("models", [])
                    ]
                    self._available = True
                    return True
                self._available = False
                return False
        except (httpx.ConnectError, httpx.TimeoutException, httpx.ConnectError):
            self._available = False
            return False
        except Exception:
            self._available = False
            return False

    @property
    def is_available(self) -> bool:
        return self._available if self._available is not None else False

    @property
    def available_models(self) -> list[str]:
        return self._available_models

    def _ensure_available(self):
        """Raise OllamaError if Ollama is not running."""
        if not self.is_available:
            raise OllamaError(
                "Ollama is not running or not reachable at "
                f"{self.base_url}. Please start Ollama first "
                "(run 'ollama serve' in terminal) or switch to a cloud model.",
                status_code=0
            )

    async def chat_stream(
        self,
        messages: list[dict],
        model: str = "llama3",
        system_prompt: str = "",
        tools: list[dict] = None,
        images: list[str] = None,
    ) -> AsyncGenerator[str, None]:
        """
        Stream chat completion from Ollama.
        Yields content chunks as they arrive.
        """
        self._ensure_available()

        payload = {
            "model": model,
            "messages": messages,
            "stream": True,
            "options": {
                "temperature": 0.7,
                "num_predict": 4096,
            }
        }
        if system_prompt:
            payload["system"] = system_prompt
        if images:
            payload["images"] = images

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                async with client.stream("POST", f"{self.base_url}/api/chat", json=payload) as resp:
                    if resp.status_code != 200:
                        body = await resp.aread()
                        raise OllamaError(
                            f"Ollama returned status {resp.status_code}: {body.decode()[:500]}",
                            status_code=resp.status_code
                        )
                    async for line in resp.aiter_lines():
                        if not line.strip():
                            continue
                        try:
                            data = json.loads(line)
                            content = data.get("message", {}).get("content", "")
                            if content:
                                yield content
                            # Check if done
                            if data.get("done", False):
                                break
                        except json.JSONDecodeError:
                            continue

        except httpx.ConnectError:
            raise OllamaError(
                f"Cannot connect to Ollama at {self.base_url}. "
                "Is Ollama running? Start it with 'ollama serve'.",
                status_code=0
            )
        except httpx.TimeoutException:
            raise OllamaError(
                f"Ollama request timed out after {self.timeout}s. "
                "The model may be too large for your hardware.",
                status_code=0
            )

    async def chat_complete(
        self,
        messages: list[dict],
        model: str = "llama3",
        system_prompt: str = "",
        images: list[str] = None,
    ) -> str:
        """Non-streaming chat completion (collects full response)."""
        chunks = []
        async for chunk in self.chat_stream(messages, model, system_prompt, images=images):
            chunks.append(chunk)
        return "".join(chunks)

    async def list_models(self) -> list[dict]:
        """List all locally available Ollama models."""
        self._ensure_available()
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{self.base_url}/api/tags")
            if resp.status_code == 200:
                data = resp.json()
                return data.get("models", [])
            return []

    async def pull_model(self, model_name: str) -> AsyncGenerator[str, None]:
        """Pull/download a model from Ollama registry."""
        self._ensure_available()
        async with httpx.AsyncClient(timeout=600.0) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/api/pull",
                json={"name": model_name, "stream": True}
            ) as resp:
                async for line in resp.aiter_lines():
                    if line.strip():
                        yield line


# Global client instance
ollama_client = OllamaClient()
