# jarvis/memory/vector_store.py
# -----------------------------------
# Uses FAISS (or Chroma) to store sentence embeddings of past turns.
# Enables semantic retrieval of related past context.
# -----------------------------------

import faiss
import numpy as np
import os
import logging
from jarvis.config import Config
from sentence_transformers import SentenceTransformer  # e.g. 'all-MiniLM-L6-v2'

logger = logging.getLogger(__name__)

class VectorStore:
    """
    - On each new turn, compute embedding and add to FAISS index.
    - To retrieve relevant context, embed a query and search nearest neighbors.
    """

    def __init__(self, index_path: str):
        os.makedirs(os.path.dirname(index_path), exist_ok=True)
        self.index_path = index_path
        self.model = SentenceTransformer("all-MiniLM-L6-v2")
        self.dim = self.model.get_sentence_embedding_dimension()
        if os.path.exists(index_path):
            self.index = faiss.read_index(index_path)
        else:
            self.index = faiss.IndexFlatL2(self.dim)
            # Metadata store to map index IDs → (turn_id, timestamp) as needed
            self.metadata = []
        logger.info("VectorStore initialized with index path %s.", index_path)

    def add_turn(self, turn_text: str):
        """
        Compute embedding for turn_text and add to FAISS index.
        """
        vector = self.model.encode([turn_text])
        self.index.add(np.array(vector).astype(np.float32))
        # Append metadata (e.g., timestamp or turn ID) here if needed.
        self._save_index()

    def query_similar(self, query: str, top_k: int = 3):
        """
        Return the indices of the top_k most similar past turns for a given query.
        """
        vector = self.model.encode([query])
        distances, indices = self.index.search(np.array(vector).astype(np.float32), top_k)
        return indices[0], distances[0]

    def _save_index(self):
        faiss.write_index(self.index, self.index_path)
