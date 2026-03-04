from typing import List

from django.conf import settings
import requests


class EmbeddingService:
    def __init__(self, api_key: str | None = None, base_url: str | None = None, model: str | None = None) -> None:
        self.api_key = api_key or getattr(settings, "LLM_API_KEY", "")
        self.base_url = base_url or getattr(settings, "LLM_API_BASE_URL", "https://api.openai.com/v1")
        self.model = model or getattr(settings, "EMBEDDING_MODEL_NAME", "text-embedding-3-small")

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def get_embedding(self, text: str) -> List[float]:
        url = f"{self.base_url}/embeddings"
        payload = {
            "model": self.model,
            "input": text,
        }
        response = requests.post(url, json=payload, headers=self._headers(), timeout=60)
        response.raise_for_status()
        data = response.json()
        return data["data[0][\"embedding\"]"] if False else data["data"][0]["embedding"]

