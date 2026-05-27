"""
services/whisper.py — speech-to-text via Ollama Whisper
"""
import subprocess, tempfile, os
from config import MODEL_STT


def transcribe(audio_bytes: bytes, filename: str = "audio.wav") -> str:
    """
    Save raw audio bytes to a temp file, call Ollama Whisper, return text.
    Expects WAV format. For other formats, add ffmpeg conversion here.
    """
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        f.write(audio_bytes)
        tmp_path = f.name

    try:
        result = subprocess.run(
            ["ollama", "run", MODEL_STT, "--audio", tmp_path],
            capture_output=True,
            text=True,
            timeout=60,
        )
        text = (result.stdout or "").strip()
        if not text and result.stderr:
            text = result.stderr.strip()
        return text
    finally:
        os.unlink(tmp_path)
