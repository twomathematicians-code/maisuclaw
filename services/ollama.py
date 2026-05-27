"""
services/ollama.py — Ollama HTTP API wrapper with streaming + vision support
"""
import json
import base64
import requests
from config import OLLAMA_BASE_URL


def chat(model: str, messages: list[dict], stream: bool = False) -> str:
    """Non-streaming chat. Returns full reply."""
    resp = requests.post(
        f"{OLLAMA_BASE_URL}/api/chat",
        json={"model": model, "messages": messages, "stream": False},
        timeout=300,
    )
    resp.raise_for_status()
    return resp.json()["message"]["content"]


def chat_stream(model: str, messages: list[dict]):
    """Streaming chat. Yields dicts with content, done, model."""
    resp = requests.post(
        f"{OLLAMA_BASE_URL}/api/chat",
        json={"model": model, "messages": messages, "stream": True},
        stream=True,
        timeout=300,
    )
    resp.raise_for_status()
    for line in resp.iter_lines():
        if not line:
            continue
        chunk = line.decode("utf-8")
        if not chunk.strip():
            continue
        data = json.loads(chunk)
        content = data.get("message", {}).get("content", "")
        done = data.get("done", False)
        if content:
            yield {"content": content, "done": False, "model": model}
        if done:
            yield {"content": "", "done": True, "model": model}


def chat_with_images(model: str, text: str, image_paths: list[str]) -> str:
    """Send text + images to a vision model. Returns full reply."""
    content = [{"type": "text", "text": text}]
    for path in image_paths:
        b64 = _image_to_base64(path)
        mime = _guess_mime(path)
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:{mime};base64,{b64}"},
        })
    messages = [{"role": "user", "content": content}]
    return chat(model, messages)


def chat_with_base64_images(model: str, text: str, images_b64: list[str]) -> str:
    """Send text + base64-encoded images to a vision model."""
    content = [{"type": "text", "text": text}]
    for b64 in images_b64:
        content.append({
            "type": "image_url",
            "image_url": {"url": b64 if b64.startswith("data:") else f"data:image/png;base64,{b64}"},
        })
    messages = [{"role": "user", "content": content}]
    return chat(model, messages)


def embed(texts: list[str], model: str = None) -> list[list[float]]:
    """Return embeddings for texts."""
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


# ── helpers ────────────────────────────────────────────────────────

def _image_to_base64(filepath: str) -> str:
    with open(filepath, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def _guess_mime(filepath: str) -> str:
    ext = filepath.lower().split(".")[-1]
    mime_map = {
        "png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg",
        "gif": "image/gif", "bmp": "image/bmp", "webp": "image/webp",
    }
    return mime_map.get(ext, "image/png")
