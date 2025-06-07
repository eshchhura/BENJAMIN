# jarvis/memory/vector_store.py
# -----------------------------------
# Uses FAISS (or Chroma) to store sentence embeddings of past turns.
# Enables semantic retrieval of related past context.
# -----------------------------------

import os
import logging
import asyncio
from typing import List, Optional

try:
    import faiss  # type: ignore
except Exception:  # pragma: no cover - optional dependency may be missing
    faiss = None

import numpy as np
try:
    from sentence_transformers import SentenceTransformer  # type: ignore
except Exception:  # pragma: no cover - provide dummy model if missing
    class SentenceTransformer:  # type: ignore
        def __init__(self, *_, **__):
            pass

        def get_sentence_embedding_dimension(self) -> int:
            return 3

        def encode(self, texts):
            return np.array([[0.0, 0.0, 0.0] for _ in texts], dtype=np.float32)

from .cache import LRUCache

logger = logging.getLogger(__name__)


def initialize_store(index_path: str, dim: int):
    """Create or load a FAISS index if available."""
    if faiss is not None:
        if os.path.exists(index_path):
            return faiss.read_index(index_path)
        return faiss.IndexFlatL2(dim)
    return np.empty((0, dim), dtype=np.float32)

class VectorStore:
    """Simple sentence embedding store with optional FAISS backend."""

    def __init__(self, index_path: str, cache_size: int = 128):
        os.makedirs(os.path.dirname(index_path), exist_ok=True)
        self.index_path = index_path
        self.model = SentenceTransformer("all-MiniLM-L6-v2")
        self.dim = self.model.get_sentence_embedding_dimension()
        self.texts: List[str] = []
        self.cache = LRUCache(maxsize=cache_size)

        backend = initialize_store(index_path, self.dim)
        if faiss is not None:
            self.index = backend
        else:
            self.index = None
            self.vectors = backend

        logger.info("VectorStore initialized with index path %s.", index_path)

    def store(self, text: str) -> None:
        """Compute embedding for ``text`` and add to the store."""
        vector = self.model.encode([text])[0].astype(np.float32)

        if self.index is not None:
            self.index.add(np.array([vector]))
            self._save_index()
        else:
            self.vectors = np.vstack([self.vectors, vector])

        self.texts.append(text)

    def retrieve(self, query: str, top_k: int = 3) -> List[str]:
        """Return up to ``top_k`` texts most similar to ``query``."""
        cache_key = (query, top_k)
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached

        vector = self.model.encode([query])[0].astype(np.float32)

        if self.index is not None:
            distances, indices = self.index.search(np.array([vector]), top_k)
            idxs = indices[0].tolist()
        else:
            if self.vectors.size == 0:
                idxs = []
            else:
                sims = np.dot(self.vectors, vector)
                norms = np.linalg.norm(self.vectors, axis=1) * np.linalg.norm(vector)
                sims = sims / np.clip(norms, 1e-12, None)
                idxs = (-sims).argsort()[:top_k].tolist()

        results = [self.texts[i] for i in idxs if i < len(self.texts)]
        self.cache.set(cache_key, results)
        return results

    async def aretrieve(self, query: str, top_k: int = 3) -> List[str]:
        """Asynchronous wrapper around :meth:`retrieve`."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.retrieve, query, top_k)

    def _save_index(self) -> None:
        if faiss is not None:
            faiss.write_index(self.index, self.index_path)
