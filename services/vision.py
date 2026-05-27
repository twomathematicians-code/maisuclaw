"""
services/vision.py — multimodal vision via Ollama VLM models
Sends images (file paths, base64, clipboard screenshots) to vision-capable
models like llava and minicpm-v through the standard Ollama chat API.
"""

import base64
import requests
from pathlib import Path
from config import OLLAMA_BASE_URL

# Default vision model — change in config if you prefer minicpm-v or another VLM
MODEL_VISION = "llava:13b"

# Timeout for vision requests (models are large and slow)
_VISION_TIMEOUT = 600


def _read_image_as_b64(image_path: str) -> str:
    """Read an image file and return its base64-encoded content.

    Detects common image formats. Returns raw base64 string (no data URI prefix).
    Raises FileNotFoundError or ValueError for unsupported files.
    """
    path = Path(image_path).resolve()
    if not path.exists():
        raise FileNotFoundError(f"Image not found: {path}")

    supported_ext = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".tiff"}
    if path.suffix.lower() not in supported_ext:
        raise ValueError(f"Unsupported image format: {path.suffix}")

    data = path.read_bytes()
    mime_map = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".bmp": "image/bmp",
        ".webp": "image/webp",
        ".tiff": "image/tiff",
    }
    mime = mime_map.get(path.suffix.lower(), "image/png")
    b64 = base64.b64encode(data).decode("utf-8")
    return f"data:{mime};base64,{b64}"


def _build_vision_messages(
    prompt: str,
    image_data_uris: list[str],
) -> list[dict]:
    """Build the messages payload for Ollama's vision chat API.

    Ollama accepts OpenAI-style multimodal content blocks:
      {"type": "text", "text": "..."}
      {"type": "image_url", "image_url": {"url": "data:image/png;base64,..."}}
    """
    content: list[dict] = [{"type": "text", "text": prompt}]

    for uri in image_data_uris:
        # If the caller already passed a full data URI, use as-is.
        # Otherwise assume raw base64 and wrap it.
        if uri.startswith("data:"):
            data_uri = uri
        else:
            data_uri = f"data:image/png;base64,{uri}"

        content.append({
            "type": "image_url",
            "image_url": {"url": data_uri},
        })

    return [{"role": "user", "content": content}]


def _call_vision_model(
    messages: list[dict],
    model: str,
    stream: bool = False,
) -> str:
    """Send a chat request to Ollama and return the full text response."""
    resp = requests.post(
        f"{OLLAMA_BASE_URL}/api/chat",
        json={"model": model, "messages": messages, "stream": stream},
        timeout=_VISION_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()["message"]["content"]


def analyze_image(
    image_path: str,
    prompt: str = "Describe this image in detail.",
    model: str | None = None,
) -> str:
    """Analyze a single image file using an Ollama vision model.

    Args:
        image_path: Absolute or relative path to an image file.
        prompt: Text prompt to send alongside the image.
        model: Ollama model name (defaults to MODEL_VISION).

    Returns:
        The model's text response describing / answering about the image.
    """
    model = model or MODEL_VISION
    data_uri = _read_image_as_b64(image_path)
    messages = _build_vision_messages(prompt, [data_uri])
    return _call_vision_model(messages, model)


def analyze_images(
    image_paths: list[str],
    prompt: str = "Describe and compare these images.",
    model: str | None = None,
) -> str:
    """Analyze multiple images in a single request.

    Args:
        image_paths: List of file paths to images.
        prompt: Text prompt to send alongside the images.
        model: Ollama model name (defaults to MODEL_VISION).

    Returns:
        The model's text response about all provided images.
    """
    model = model or MODEL_VISION
    if not image_paths:
        raise ValueError("No image paths provided.")

    data_uris = [_read_image_as_b64(p) for p in image_paths]
    messages = _build_vision_messages(prompt, data_uris)
    return _call_vision_model(messages, model)


def analyze_screenshot(
    base64_data: str,
    prompt: str = "Describe what is shown in this screenshot.",
    model: str | None = None,
) -> str:
    """Analyze a screenshot passed as raw base64 data (e.g. from clipboard).

    Args:
        base64_data: Base64-encoded image data, either raw or with a data URI prefix.
        prompt: Text prompt to send alongside the screenshot.
        model: Ollama model name (defaults to MODEL_VISION).

    Returns:
        The model's text response about the screenshot.
    """
    model = model or MODEL_VISION
    if not base64_data:
        raise ValueError("No base64 image data provided.")

    messages = _build_vision_messages(prompt, [base64_data])
    return _call_vision_model(messages, model)
