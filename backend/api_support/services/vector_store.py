from typing import Iterable, List, Tuple

from pgvector.django import CosineDistance

from api_support.models import DocumentChunk


class VectorStore:
    def upsert_chunks(self, chunks: Iterable[Tuple[int, int, str, dict, list[float]]]) -> None:
        """
        Each item is (document_id, chunk_index, content, metadata, embedding).
        """
        instances: list[DocumentChunk] = []
        for document_id, chunk_index, content, metadata, embedding in chunks:
            instances.append(
                DocumentChunk(
                    document_id=document_id,
                    chunk_index=chunk_index,
                    content=content,
                    metadata=metadata,
                    embedding=embedding,
                )
            )
        DocumentChunk.objects.bulk_create(instances)

    def search(
        self,
        embedding: List[float],
        top_k: int = 5,
        source_ids: List[int] | None = None,
    ) -> List[DocumentChunk]:
        qs = DocumentChunk.objects.select_related("document__source")
        if source_ids:
            qs = qs.filter(document__source_id__in=source_ids)
        return list(qs.order_by(CosineDistance("embedding", embedding))[:top_k])
