from functools import lru_cache
from typing import List

import numpy as np
from django.conf import settings
import requests
from sentence_transformers import SentenceTransformer


VECTOR_DIMENSIONS = 1536


@lru_cache(maxsize=1)
def _load_local_model(model_name: str) -> SentenceTransformer:
    return SentenceTransformer(model_name)


class EmbeddingService:
    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        backend: str | None = None,
    ) -> None:
        self.api_key = api_key or getattr(settings, "LLM_API_KEY", "")
        self.base_url = base_url or getattr(settings, "LLM_API_BASE_URL", "https://api.openai.com/v1")
        self.model = model or getattr(settings, "EMBEDDING_MODEL_NAME", "text-embedding-3-small")
        self.backend = (backend or getattr(settings, "EMBEDDING_BACKEND", "openai")).lower()

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _adapt_dimension(self, vector: List[float]) -> List[float]:
        """
        Ensure embeddings always have VECTOR_DIMENSIONS elements, padding or truncating as needed.
        This allows using local models with different dimensions without changing the DB schema.
        """
        arr = np.asarray(vector, dtype="float32").flatten()
        current_dim = arr.shape[0]
        if current_dim == VECTOR_DIMENSIONS:
            return arr.tolist()
        if current_dim > VECTOR_DIMENSIONS:
            return arr[:VECTOR_DIMENSIONS].tolist()

        padded = np.zeros(VECTOR_DIMENSIONS, dtype="float32")
        padded[:current_dim] = arr
        return padded.tolist()

    def _get_embedding_openai(self, text: str) -> List[float]:
        url = f"{self.base_url}/embeddings"
        payload = {
            "model": self.model,
            "input": text,
        }
        response = requests.post(url, json=payload, headers=self._headers(), timeout=60)
        response.raise_for_status()
        data = response.json()
        return self._adapt_dimension(data["data"][0]["embedding"])

    def _get_embedding_local(self, text: str) -> List[float]:
        model = _load_local_model(self.model)
        # sentence-transformers returns a numpy array; convert to list and adapt dimension.
        embedding = model.encode(text, normalize_embeddings=True)
        return self._adapt_dimension(embedding.tolist())

    def get_embedding(self, text: str) -> List[float]:
        if self.backend == "local":
            return self._get_embedding_local(text)
        return self._get_embedding_openai(text)


