import os

from django.apps import AppConfig


class ApiSupportConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "api_support"

    def ready(self) -> None:
        if os.getenv("SKIP_DIM_CHECK"):
            return
        from django.conf import settings
        if getattr(settings, "EMBEDDING_BACKEND", "local") != "local":
            return
        try:
            from sentence_transformers import SentenceTransformer
            model_dim = SentenceTransformer(settings.EMBEDDING_MODEL_NAME).get_sentence_embedding_dimension()
            vector_dim = settings.VECTOR_DIMENSIONS
            if model_dim > vector_dim:
                import warnings
                warnings.warn(
                    f"[RAG] Embedding model '{settings.EMBEDDING_MODEL_NAME}' outputs {model_dim} dims "
                    f"but VECTOR_DIMENSIONS={vector_dim}. "
                    "Embeddings will be truncated, losing information. "
                    "Increase VECTOR_DIMENSIONS or switch to a smaller model.",
                    stacklevel=2,
                )
        except Exception:
            pass  # model not yet downloaded or sentence-transformers not available

