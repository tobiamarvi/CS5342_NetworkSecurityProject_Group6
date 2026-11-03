"""Shared retrieval for both agents: retrieve(query) -> top-k course chunks."""
import json
from functools import lru_cache
from pathlib import Path

import faiss
from sentence_transformers import SentenceTransformer

INDEX_DIR = Path(__file__).resolve().parents[1] / "index"
# bge-small reads 512 tokens, close to a 500-word chunk (MiniLM stops at 256)
MODEL_NAME = "BAAI/bge-small-en-v1.5"
QUERY_PREFIX = "Represent this sentence for searching relevant passages: "


@lru_cache(maxsize=1)
def model():
    return SentenceTransformer(MODEL_NAME, device="cpu")  # GPU is left for the LLM


def embed(texts, query=False):
    if query:
        texts = [QUERY_PREFIX + t for t in texts]
    return model().encode(texts, normalize_embeddings=True, convert_to_numpy=True,
                          batch_size=32, show_progress_bar=not query)


@lru_cache(maxsize=1)
def _store():
    index = faiss.read_index(str(INDEX_DIR / "faiss.index"))
    chunks = json.loads((INDEX_DIR / "chunks.json").read_text(encoding="utf-8"))
    return index, chunks


def index_exists():
    return (INDEX_DIR / "faiss.index").exists()


def retrieve(query, k=5):
    """Return [{text, source, pages, score}] best first. score = cosine similarity."""
    index, chunks = _store()
    scores, ids = index.search(embed([query], query=True), k)
    return [{**chunks[i], "score": float(s)} for s, i in zip(scores[0], ids[0]) if i != -1]
