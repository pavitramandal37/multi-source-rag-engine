from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, Iterable, List, Tuple

from api_support.models import Document, DocumentChunk, Source
from api_support.services.embedding import EmbeddingService
from api_support.services.vector_store import VectorStore


@dataclass
class IngestionResult:
    source_id: int
    documents_created: int
    chunks_created: int


class BaseIngestionService:
    def __init__(
        self,
        embedding_service: EmbeddingService | None = None,
        vector_store: VectorStore | None = None,
    ) -> None:
        self.embedding_service = embedding_service or EmbeddingService()
        self.vector_store = vector_store or VectorStore()

    def _embed_and_store(
        self,
        source: Source,
        chunks: List[Tuple[str, str, Dict]],
    ) -> IngestionResult:
        """
        Given a Source and list of (title, content, metadata) tuples,
        creates Document + DocumentChunk rows with embeddings.
        Groups consecutive chunks with the same title under one Document.
        """
        # Preserve insertion order while grouping by title
        title_order: List[str] = []
        title_groups: Dict[str, List[Tuple[str, Dict]]] = defaultdict(list)
        for title, content, meta in chunks:
            if title not in title_groups:
                title_order.append(title)
            title_groups[title].append((content, meta))

        docs_created = 0
        chunk_records: List[Tuple] = []

        for title in title_order:
            document = Document.objects.create(
                title=title,
                source=source,
                source_name=source.name,
            )
            docs_created += 1
            for idx, (content, meta) in enumerate(title_groups[title]):
                embedding = self.embedding_service.get_embedding(content)
                chunk_records.append((document.id, idx, content, meta, embedding))

        self.vector_store.upsert_chunks(chunk_records)

        return IngestionResult(
            source_id=source.id,
            documents_created=docs_created,
            chunks_created=len(chunk_records),
        )
