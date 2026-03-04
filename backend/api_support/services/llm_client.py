import os
from typing import Any, Dict, List

import requests
from django.conf import settings


class LLMClient:
    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
    ) -> None:
        self.api_key = api_key or getattr(settings, "LLM_API_KEY", "") or os.getenv("LLM_API_KEY", "")
        self.base_url = base_url or getattr(settings, "LLM_API_BASE_URL", "https://api.openai.com/v1")
        self.model = model or getattr(settings, "LLM_MODEL_NAME", "gpt-4.1-mini")

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def chat(self, messages: List[Dict[str, str]], temperature: float = 0.2) -> str:
        url = f"{self.base_url}/chat/completions"
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }
        response = requests.post(url, json=payload, headers=self._headers(), timeout=60)
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]

