import os
from typing import Any, Dict, List

import requests
from django.conf import settings


class LLMUnavailableError(Exception):
    """Raised when the LLM backend cannot be reached or returns a server error."""


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
        try:
            response = requests.post(url, json=payload, headers=self._headers(), timeout=180)
            response.raise_for_status()
        except requests.exceptions.ConnectionError:
            raise LLMUnavailableError(
                f"Cannot connect to the LLM at {self.base_url}. "
                "Make sure Ollama is running: run `ollama serve` on your host machine."
            )
        except requests.exceptions.Timeout:
            raise LLMUnavailableError(
                f"LLM request timed out after 180 s (model: {self.model}). "
                "The model may still be loading — try again in a moment."
            )
        except requests.exceptions.HTTPError as exc:
            raise LLMUnavailableError(
                f"LLM returned HTTP {exc.response.status_code} for model '{self.model}'. "
                "Check that the model is pulled: `ollama pull {self.model}`"
            ) from exc
        data = response.json()
        return data["choices"][0]["message"]["content"]

