from dataclasses import dataclass
from typing import Iterable, List

from api_support.models import Document
from api_support.services.embedding import EmbeddingService
from api_support.services.vector_store import VectorStore


@dataclass
class IngestedDocumentSummary:
    document_id: int
    chunks_created: int


class IngestionService:
    def __init__(self, embedding_service: EmbeddingService | None = None, vector_store: VectorStore | None = None) -> None:
        self.embedding_service = embedding_service or EmbeddingService()
        self.vector_store = vector_store or VectorStore()

    def _simple_chunk(self, text: str, max_tokens_approx: int = 500) -> List[str]:
        """
        Very simple chunking by paragraph count / character length.
        In a real system you would use token-aware chunking.
        """
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        chunks: List[str] = []
        current = ""
        for para in paragraphs:
            if len(current) + len(para) > max_tokens_approx * 4 and current:
                chunks.append(current)
                current = para
            else:
                current = f"{current}\n\n{para}" if current else para
        if current:
            chunks.append(current)
        return chunks

    def ingest_documents(self, source_name: str, docs: Iterable[dict]) -> List[IngestedDocumentSummary]:
        """
        docs: iterable of {\"title\": str, \"content\": str}
        """
        summaries: List[IngestedDocumentSummary] = []
        for doc in docs:
            title = doc.get("title") or source_name
            content = doc.get("content") or ""
            document = Document.objects.create(title=title, source_name=source_name)
            raw_chunks = self._simple_chunk(content)
            chunk_records = []
            for idx, chunk_text in enumerate(raw_chunks):
                embedding = self.embedding_service.get_embedding(chunk_text)
                chunk_records.append((document.id, idx, chunk_text, {"source_name": source_name}, embedding))

            self.vector_store.upsert_chunks(chunk_records)
            summaries.append(IngestedDocumentSummary(document_id=document.id, chunks_created=len(chunk_records)))
        return summaries

