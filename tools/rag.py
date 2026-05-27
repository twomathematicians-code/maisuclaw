"""
tools/rag.py — simple RAG: embed documents, search by similarity
"""
import os, json
from pathlib import Path
from services.ollama import embed
from services.memory import save_document, list_documents
import numpy as np


def _cosine(a, b):
    a, b = np.array(a), np.array(b)
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-8))


def index_file(filepath: str, chunk_size: int = 1000) -> str:
    """Read a file, chunk it, embed, and store in the documents DB."""
    p = Path(filepath).resolve()
    if not p.exists():
        return f"Error: file not found: {p}"

    text = p.read_text(encoding="utf-8", errors="ignore")
    if not text.strip():
        return "File is empty."

    # Simple chunking by paragraphs
    chunks = []
    lines = text.split("\n")
    current = []
    for line in lines:
        current.append(line)
        if len("\n".join(current)) >= chunk_size:
            chunks.append("\n".join(current))
            current = []
    if current:
        chunks.append("\n".join(current))

    # Embed in batches
    try:
        embeddings = embed(chunks)
        for i, (chunk, emb) in enumerate(zip(chunks, embeddings)):
            save_document(filepath, chunk, emb)
        return f"OK: indexed {len(chunks)} chunks from {p.name}"
    except Exception as e:
        # Save without embeddings if Ollama is down
        for chunk in chunks:
            save_document(filepath, chunk)
        return f"Warning: embeddings failed ({e}). Saved {len(chunks)} chunks without embeddings."


def search_documents(query: str, top_k: int = 3) -> list[dict]:
    """Search indexed documents by cosine similarity."""
    docs = list_documents()
    if not docs:
        return []

    # Get query embedding
    try:
        q_emb = embed([query])[0]
    except Exception:
        return []

    # Load full docs with embeddings
    from services.memory import _conn
    with _conn() as conn:
        rows = conn.execute("SELECT id, filepath, text, embedding FROM documents").fetchall()

    scored = []
    for r in rows:
        emb = json.loads(r["embedding"]) if r["embedding"] else None
        if emb:
            score = _cosine(q_emb, emb)
            scored.append({"id": r["id"], "filepath": r["filepath"], "text": r["text"][:500], "score": score})

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:top_k]
