from typing import Iterable, List, Tuple

from pgvector.django import CosineDistance

from api_support.models import DocumentChunk


class VectorStore:
    def upsert_chunks(self, chunks: Iterable[Tuple[int, int, str, dict, list[float]]]) -> None:
        """
        Upsert chunks into the vector store.

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

    def search(self, embedding: List[float], top_k: int = 5) -> List[DocumentChunk]:
        return list(DocumentChunk.objects.order_by(CosineDistance("embedding", embedding))[:top_k])

