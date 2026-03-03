from dataclasses import dataclass
from typing import Any, Dict, List, Sequence

from api_support.models import Conversation, Message
from api_support.services.embedding import EmbeddingService
from api_support.services.llm_client import LLMClient
from api_support.services.vector_store import VectorStore


@dataclass
class RAGResponse:
    answer: str
    sources: List[Dict[str, Any]]
    conversation_id: int


class RAGPipeline:
    def __init__(
        self,
        embedding_service: EmbeddingService | None = None,
        llm_client: LLMClient | None = None,
        vector_store: VectorStore | None = None,
    ) -> None:
        self.embedding_service = embedding_service or EmbeddingService()
        self.llm_client = llm_client or LLMClient()
        self.vector_store = vector_store or VectorStore()

    def _build_system_prompt(self) -> str:
        return (
            "You are an API support assistant. "
            "You use the provided API documentation context to answer questions about how to use APIs, "
            "troubleshoot errors, and explain best practices. "
            "If the context is insufficient, say you are unsure instead of inventing details."
        )

    def _build_messages(
        self,
        question: str,
        retrieved_chunks: Sequence,
        conversation: Conversation | None,
    ) -> List[Dict[str, str]]:
        system_content = self._build_system_prompt()
        context_text = "\n\n".join(f"[{c.document.title}] {c.content}" for c in retrieved_chunks)
        user_prompt = (
            "Context:\n"
            f"{context_text or '[No relevant context found]'}\n\n"
            "User question:\n"
            f"{question}\n\n"
            "When answering:\n"
            "- Reference the relevant APIs from the context.\n"
            "- If you suggest requests, include example HTTP requests or curl commands.\n"
            "- If there is not enough information, clearly say that."
        )

        messages: List[Dict[str, str]] = [{"role": "system", "content": system_content}]

        if conversation is not None:
            for msg in conversation.messages.all():
                messages.append({"role": msg.role, "content": msg.content})

        messages.append({"role": "user", "content": user_prompt})
        return messages

    def answer(self, question: str, conversation_id: int | None = None, top_k: int = 5) -> RAGResponse:
        if conversation_id is not None:
            conversation = Conversation.objects.get(pk=conversation_id)
        else:
            conversation = Conversation.objects.create(title=question[:80])

        question_embedding = self.embedding_service.get_embedding(question)
        chunks = self.vector_store.search(question_embedding, top_k=top_k)

        messages = self._build_messages(question, chunks, conversation)
        answer_text = self.llm_client.chat(messages)

        Message.objects.create(conversation=conversation, role=Message.ROLE_USER, content=question)
        Message.objects.create(conversation=conversation, role=Message.ROLE_ASSISTANT, content=answer_text)

        sources = [
            {
                "document_id": c.document_id,
                "document_title": c.document.title,
                "chunk_index": c.chunk_index,
                "snippet": c.content[:300],
            }
            for c in chunks
        ]

        return RAGResponse(answer=answer_text, sources=sources, conversation_id=conversation.id)

