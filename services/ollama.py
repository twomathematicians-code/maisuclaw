"""
services/ollama.py — thin wrapper around the Ollama HTTP API
"""
import requests
from config import OLLAMA_BASE_URL


def chat(model: str, messages: list[dict], stream: bool = False) -> str:
    """Send messages to a model and return the assistant reply."""
    resp = requests.post(
        f"{OLLAMA_BASE_URL}/api/chat",
        json={"model": model, "messages": messages, "stream": stream},
        timeout=300,
    )
    resp.raise_for_status()
    return resp.json()["message"]["content"]


def chat_stream(model: str, messages: list[dict]):
    """Yield chunks from a streaming chat completion."""
    resp = requests.post(
        f"{OLLAMA_BASE_URL}/api/chat",
        json={"model": model, "messages": messages, "stream": True},
        stream=True,
        timeout=300,
    )
    resp.raise_for_status()
    for line in resp.iter_lines():
        if line:
            chunk = line.decode("utf-8")
            if '"content"' in chunk and '"done":true' not in chunk:
                # extract the content value
                import json
                data = json.loads(chunk)
                content = data.get("message", {}).get("content", "")
                if content:
                    yield content


def embed(texts: list[str], model: str = None) -> list[list[float]]:
    """Return embeddings for one or more texts."""
    from config import MODEL_EMBED
    model = model or MODEL_EMBED
    resp = requests.post(
        f"{OLLAMA_BASE_URL}/api/embed",
        json={"model": model, "input": texts},
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()["embeddings"]


def list_models() -> list[dict]:
    """Return all locally available Ollama models."""
    resp = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=10)
    resp.raise_for_status()
    return resp.json().get("models", [])
