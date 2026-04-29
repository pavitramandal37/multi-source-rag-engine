import json
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Sequence

import numpy as np

from django.conf import settings

from api_support.models import Conversation, Message
from api_support.services.embedding import EmbeddingService
from api_support.services.llm_client import LLMClient, LLMUnavailableError
from api_support.services.vector_store import VectorStore


@dataclass
class RAGResponse:
    answer: str
    sources: List[Dict[str, Any]]
    conversation_id: int
    confidence: str = "high"  # "high" | "low" | "none"


_CONVERSATIONAL_RE = re.compile(
    r"^\s*("
    r"hi+[!.]*|hello+[!.]*|hey+[!.]*|howdy[!.]*|greetings[!.]*|"
    r"good\s+(morning|afternoon|evening|day)[!.]*|"
    r"who\s+are\s+you\??|what\s+are\s+you\??|"
    r"what\s+can\s+you\s+(do|help)\??|"
    r"can\s+you\s+help(\s+me)?\??|"
    r"thank(s|\s+you)[!.]*|bye[!.]*|goodbye[!.]*"
    r")\s*$",
    re.IGNORECASE,
)

_CONVERSATIONAL_REPLY = (
    "Hi! I'm an AI assistant here to help you find information from the indexed knowledge base. "
    "Feel free to ask me anything — I'll search through the available sources and give you an accurate answer."
)

_CITED_RE = re.compile(r"(?im)^\s*CITED\s*:\s*\[([^\]]*)\]\s*$")
_NO_INFO_RE = re.compile(
    r"(?i)(i\s+don'?t\s+have|not\s+found\s+in\s+the\s+(provided\s+)?context|"
    r"context\s+(is\s+)?insufficient|no\s+(relevant\s+)?information\s+(is\s+)?available)"
)
_MAX_CITATIONS = 3


def _parse_cited(answer_text: str) -> tuple[str, list[int] | None]:
    """Strip the CITED: line and return (clean_answer, indices_1based_or_None)."""
    match = _CITED_RE.search(answer_text)
    if not match:
        return answer_text.rstrip(), None
    raw = match.group(1).strip()
    cleaned = _CITED_RE.sub("", answer_text).rstrip()
    if not raw:
        return cleaned, []
    indices: list[int] = []
    for token in raw.split(","):
        token = token.strip()
        if token.isdigit():
            indices.append(int(token))
    return cleaned, indices


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
        self.use_hyde = getattr(settings, "RAG_USE_HYDE", True)
        self.use_crag = getattr(settings, "RAG_USE_CRAG", True)
        self.crag_threshold = getattr(settings, "RAG_CRAG_THRESHOLD", 0.6)

    # ── Step 1: Query rewriting ───────────────────────────────────────────────

    def _rewrite_query(self, question: str, history: List[Dict]) -> str:
        """Rewrite a follow-up question as a self-contained query using conversation history."""
        if not history:
            return question
        messages = [
            {
                "role": "system",
                "content": (
                    "Given a conversation history and a follow-up question, "
                    "rewrite the follow-up as a self-contained question that "
                    "can be understood without the conversation history. "
                    "Output ONLY the rewritten question, nothing else."
                ),
            },
            *history,
            {
                "role": "user",
                "content": f"Follow-up question: {question}\n\nRewritten standalone question:",
            },
        ]
        try:
            return self.llm_client.chat(messages, temperature=0.0).strip() or question
        except LLMUnavailableError:
            return question  # fall back to the original question

    # ── Step 2: HyDE ─────────────────────────────────────────────────────────

    _HYDE_SYSTEM = (
        "You are a knowledgeable assistant. Generate a concise, factual answer "
        "based on what the source content is likely to say."
    )
    _HYDE_USER = (
        "Write a concise 2-3 sentence answer to the following question as if "
        "you found it in the relevant source material. "
        "Output ONLY the hypothetical answer, no preamble.\n\n"
        "Question: {question}"
    )

    def _hypothetical_answer(self, question: str) -> str:
        messages = [
            {"role": "system", "content": self._HYDE_SYSTEM},
            {"role": "user", "content": self._HYDE_USER.format(question=question)},
        ]
        try:
            return self.llm_client.chat(messages, temperature=0.3).strip() or question
        except LLMUnavailableError:
            return question  # fall back: embed the raw query instead

    # ── Step 3: Batched CRAG grading ─────────────────────────────────────────

    _CRAG_BATCH_PROMPT = (
        "You are grading document chunks for relevance to a query.\n"
        "Query: {query}\n\n"
        "Chunks (numbered):\n"
        "{numbered_chunks}\n\n"
        "Respond with ONLY a JSON array of floats, one per chunk "
        "(1.0 = perfectly relevant, 0.0 = completely irrelevant).\n"
        "Example for 3 chunks: [0.9, 0.1, 0.7]\n"
        "No explanation, just the array."
    )

    def _grade_chunks(self, query: str, chunks: Sequence) -> List[float]:
        """Return a relevance score 0.0–1.0 for each chunk in one LLM call."""
        numbered = "\n".join(
            f"{i + 1}. {c.content[:600]}" for i, c in enumerate(chunks)
        )
        messages = [
            {
                "role": "user",
                "content": self._CRAG_BATCH_PROMPT.format(
                    query=query, numbered_chunks=numbered
                ),
            }
        ]
        raw = self.llm_client.chat(messages, temperature=0.0).strip()
        try:
            scores = json.loads(raw)
            if isinstance(scores, list) and len(scores) == len(chunks):
                return [max(0.0, min(1.0, float(s))) for s in scores]
        except (json.JSONDecodeError, ValueError, TypeError):
            pass
        except LLMUnavailableError:
            pass
        # Parse failure or LLM unavailable → pass all chunks through
        return [1.0] * len(chunks)

    def _crag_filter(self, query: str, chunks: Sequence) -> tuple:
        """
        Returns (filtered_chunks, confidence).
        confidence: "none" if all filtered out, "low" if partial, "high" if all pass.
        """
        scores = self._grade_chunks(query, chunks)
        passing = [c for c, s in zip(chunks, scores) if s >= self.crag_threshold]

        if not passing:
            return [], "none"
        if len(passing) == len(chunks):
            return passing, "high"
        return passing, "low"

    # ── Final answer assembly ─────────────────────────────────────────────────

    def _build_system_prompt(self) -> str:
        return (
            "You are a grounded RAG assistant. "
            "Answer the user's question STRICTLY based on the provided context. "
            "Do not invent facts not present in the context. "
            "If the context is insufficient, say so clearly.\n\n"
            "After your answer, on a NEW final line, output exactly: "
            "CITED: [<comma-separated chunk numbers you actually used>]\n"
            "Examples: 'CITED: [1]', 'CITED: [2,4]', or 'CITED: []' if you used none.\n"
            "Only list chunks whose content directly supports your answer. "
            "Do not list chunks you did not use."
        )

    def _build_messages(
        self,
        question: str,
        retrieved_chunks: Sequence,
        conversation: Conversation,
    ) -> List[Dict[str, str]]:
        context_parts = []
        for i, c in enumerate(retrieved_chunks, start=1):
            meta = c.metadata or {}
            citation_url = meta.get("citation_url", "")
            label = meta.get("heading") or c.document.title
            context_parts.append(f"[{i}] [{label}]({citation_url})\n{c.content}")
        context_text = "\n\n---\n\n".join(context_parts) or "[No relevant context found]"

        user_prompt = (
            f"Context:\n{context_text}\n\n"
            f"Question: {question}\n\n"
            "Answer strictly from the context above. "
            "Remember to end with a CITED: [...] line listing only the chunk "
            "numbers you actually used."
        )

        messages: List[Dict[str, str]] = [
            {"role": "system", "content": self._build_system_prompt()}
        ]
        for msg in conversation.messages.all():
            messages.append({"role": msg.role, "content": msg.content})
        messages.append({"role": "user", "content": user_prompt})
        return messages

    # ── Public entry point ────────────────────────────────────────────────────

    def answer(
        self,
        question: str,
        conversation_id: int | None = None,
        top_k: int = 8,
        source_ids: List[int] | None = None,
    ) -> RAGResponse:
        # 1. Load or create conversation
        if conversation_id is not None:
            conversation = Conversation.objects.get(pk=conversation_id)
        else:
            conversation = Conversation.objects.create(title=question[:80])

        history = [
            {"role": m.role, "content": m.content}
            for m in conversation.messages.all()
        ]

        # Handle conversational/greeting queries without RAG
        if _CONVERSATIONAL_RE.match(question.strip()):
            Message.objects.create(
                conversation=conversation, role=Message.ROLE_USER, content=question
            )
            Message.objects.create(
                conversation=conversation, role=Message.ROLE_ASSISTANT, content=_CONVERSATIONAL_REPLY
            )
            return RAGResponse(
                answer=_CONVERSATIONAL_REPLY,
                sources=[],
                conversation_id=conversation.id,
                confidence="high",
            )

        # 2. Query rewriting (multi-turn memory)
        standalone_query = self._rewrite_query(question, history)

        # 3. HyDE: blend raw query embedding with hypothetical answer embedding
        # Pure HyDE can hallucinate off-topic text; blending anchors the search.
        if self.use_hyde:
            hyde_text = self._hypothetical_answer(standalone_query)
            raw_emb = np.array(self.embedding_service.get_embedding(standalone_query))
            hyde_emb = np.array(self.embedding_service.get_embedding(hyde_text))
            blended = 0.7 * raw_emb + 0.3 * hyde_emb
            norm = np.linalg.norm(blended)
            query_embedding = (blended / norm if norm > 0 else blended).tolist()
        else:
            query_embedding = self.embedding_service.get_embedding(standalone_query)

        # 4. Vector search
        chunks = self.vector_store.search(
            query_embedding, top_k=top_k, source_ids=source_ids
        )

        # 5. CRAG grading (batched)
        confidence = "high"
        if self.use_crag and chunks:
            chunks, confidence = self._crag_filter(standalone_query, chunks)

        # 6. Early exit if zero chunks pass CRAG — no fabrication
        if not chunks:
            no_answer = "I don't have this information in the indexed sources."
            Message.objects.create(
                conversation=conversation, role=Message.ROLE_USER, content=question
            )
            Message.objects.create(
                conversation=conversation, role=Message.ROLE_ASSISTANT, content=no_answer
            )
            return RAGResponse(
                answer=no_answer,
                sources=[],
                conversation_id=conversation.id,
                confidence="none",
            )

        # 7. Final LLM call with grounded context
        messages = self._build_messages(standalone_query, chunks, conversation)
        raw_answer = self.llm_client.chat(messages)

        # 7a. Parse the CITED: trailer (LLM-declared citations)
        answer_text, cited_indices = _parse_cited(raw_answer)

        # 8. Persist conversation messages (clean answer, no CITED line)
        Message.objects.create(
            conversation=conversation, role=Message.ROLE_USER, content=question
        )
        Message.objects.create(
            conversation=conversation, role=Message.ROLE_ASSISTANT, content=answer_text
        )

        # 9. Build sources from LLM-declared citations only.
        #    - cited_indices == []        → LLM used no chunks → no sources
        #    - cited_indices is None      → LLM omitted the trailer → fall back to top retrieved chunk
        #    - "I don't have this info"   → suppress sources entirely
        sources: list[dict] = []
        if _NO_INFO_RE.search(answer_text):
            cited_chunks: list = []
        elif cited_indices == []:
            cited_chunks = []
        elif cited_indices is None:
            cited_chunks = chunks[:1]
        else:
            cited_chunks = [chunks[i - 1] for i in cited_indices if 1 <= i <= len(chunks)]

        seen_docs: set = set()
        for c in cited_chunks:
            if c.document_id in seen_docs:
                continue
            seen_docs.add(c.document_id)
            meta = c.metadata or {}
            src = c.document.source
            sources.append({
                "document_id": c.document_id,
                "document_title": c.document.title,
                "chunk_index": c.chunk_index,
                "snippet": c.content[:300],
                "citation_url": meta.get("citation_url", ""),
                "source_type": src.type if src else "",
                "source_origin": src.origin if src else "",
            })
            if len(sources) >= _MAX_CITATIONS:
                break

        return RAGResponse(
            answer=answer_text,
            sources=sources,
            conversation_id=conversation.id,
            confidence=confidence,
        )
