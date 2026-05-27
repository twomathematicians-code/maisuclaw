"""
services/eta.py — response-time estimation for Ollama models
Provides rough ETA estimates based on model size, CPU-only inference,
and optional multipliers for images, tool use, and long inputs.

These are heuristic estimates for a ThinkPad-class machine (~8-32 GB RAM,
no dedicated GPU). Actual times vary with load, temperature, and model tuning.
"""

import math

# ── base estimates per model ────────────────────────────────────────
# Each entry maps a model name prefix → (tokens_per_sec, base_seconds)
# base_seconds is the estimated time for a short (~50-token) response.
# tokens_per_sec is used to scale for longer responses.
#
# For CPU-only inference on a modern ThinkPad:
#   - 0.5B params  ≈ 2-5 tok/s   (very fast)
#   - 3-4B params  ≈ 1.5-3 tok/s
#   - 7-9B params  ≈ 0.8-1.5 tok/s
#   - 13-14B params ≈ 0.4-0.8 tok/s
#   - Vision models add ~30-50% overhead per image

MODEL_PROFILES: dict[str, tuple[float, float]] = {
    # prefix:                (tok/s,  base_seconds for short reply)
    "qwen2.5:0.5b":          (5.0,   1),
    "phi3.5":                (2.0,   3),
    "gemma2:9b":             (1.0,   8),
    "qwen2.5-coder:7b":      (1.0,   8),
    "qwen2.5:14b":           (0.5,  15),
    "llava:13b":             (0.3,  20),   # vision models are slower
    "minicpm-v":             (0.4,  12),   # smaller vision model
    "deepseek-r1:8b":        (0.5,  15),   # reasoning models think longer
}

# Fallback profile for unknown models (assume mid-range)
_DEFAULT_PROFILE: tuple[float, float] = (0.8, 10)


def _match_profile(model: str) -> tuple[float, float]:
    """Find the best matching model profile by prefix match.

    Returns (tokens_per_sec, base_seconds) for the given model name.
    Falls back to _DEFAULT_PROFILE if nothing matches.
    """
    # Try exact match first
    if model in MODEL_PROFILES:
        return MODEL_PROFILES[model]

    # Try prefix match (longest prefix wins)
    best_prefix = ""
    best_profile = _DEFAULT_PROFILE
    for prefix, profile in MODEL_PROFILES.items():
        if model.startswith(prefix) and len(prefix) > len(best_prefix):
            best_prefix = prefix
            best_profile = profile

    return best_profile


def format_eta(seconds: int) -> str:
    """Format a duration in seconds to a human-readable label.

    Args:
        seconds: Duration in seconds.

    Returns:
        A label like "~8s", "~1m 20s", "~2m 0s".
    """
    if seconds < 60:
        return f"~{seconds}s"

    minutes = seconds // 60
    remainder = seconds % 60
    return f"~{minutes}m {remainder}s"


def estimate_eta(
    model: str,
    message_length: int = 0,
    has_image: bool = False,
    has_tools: bool = False,
) -> dict:
    """Estimate how long a model response will take.

    The estimate is based on:
      1. The model's known tokens/sec rate
      2. Input message length (longer context → slightly slower)
      3. Whether an image is included (2× multiplier for vision overhead)
      4. Whether tool use is active (1.5× for agent loop overhead)
      5. Whether the input message is long (>500 chars → 1.3× for context)

    Args:
        model: Ollama model name (e.g. "qwen2.5:14b").
        message_length: Character length of the user's input message.
        has_image: Whether the request includes an image.
        has_tools: Whether the agent tool loop is active.

    Returns:
        Dict with "seconds" (int) and "label" (str) keys.
        Example: {"seconds": 8, "label": "~8s"}
    """
    tok_per_sec, base_seconds = _match_profile(model)

    # For short messages, use the base_seconds directly (which already
    # encodes real-world startup + short-response timing for that model).
    # For longer messages, add incremental time based on tokens/sec.
    if message_length <= 200:
        total = base_seconds
    else:
        extra_tokens = (message_length - 200) / 15  # ~1 extra token per 15 chars
        extra_seconds = extra_tokens / tok_per_sec
        total = base_seconds + math.ceil(extra_seconds)

    # Apply multipliers
    multipliers = []

    if has_image:
        multipliers.append(2.0)   # Vision models process images slowly

    if has_tools:
        multipliers.append(1.5)   # Agent loop adds overhead

    if message_length > 500:
        multipliers.append(1.3)   # Long context slows inference

    for m in multipliers:
        total = math.ceil(total * m)

    # Clamp to a sane range
    total = max(1, min(total, 600))  # 1s minimum, 10m maximum

    return {
        "seconds": total,
        "label": format_eta(total),
    }
