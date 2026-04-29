# API Support AI Chatbot — System Documentation

> **Audience**: developers modifying or extending the system.
> **See also**: `docs/system-flow.svg` for a visual, interactive flowchart.

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Ingestion Pipeline](#2-ingestion-pipeline)
   - 2.1 URL Ingestion
   - 2.2 PDF Ingestion
   - 2.3 Markdown Ingestion
   - 2.4 JSON Ingestion
3. [RAG Query Pipeline](#3-rag-query-pipeline)
   - 3.1 Query Rewriting
   - 3.2 HyDE (Hypothetical Document Embeddings)
   - 3.3 Vector Search
   - 3.4 CRAG Grading
   - 3.5 Final LLM Generation
4. [Embedding Service](#4-embedding-service)
5. [Vector Store](#5-vector-store)
6. [LLM Client](#6-llm-client)
7. [Database Models](#7-database-models)
8. [API Endpoints](#8-api-endpoints)
9. [Configuration Reference](#9-configuration-reference)
10. [How-To: Changing Models & Tuning](#10-how-to-changing-models--tuning)
    - 10.1 Change the Embedding Model
    - 10.2 Change the LLM Model
    - 10.3 Tune Retrieval Quality
    - 10.4 Modify Chunking Strategy
    - 10.5 Modify the RAG Prompt

---

## 1. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         Django Backend                          │
│                                                                 │
│  ┌──────────────┐   REST API   ┌───────────────────────────┐   │
│  │  HTML / JS   │◄────────────►│  Views (views.py)         │   │
│  │  Frontend    │              │  ChatView, IngestURLView,  │   │
│  └──────────────┘              │  IngestFileView, ...       │   │
│                                └──────────┬────────────────┘   │
│                                           │                     │
│                    ┌──────────────────────▼──────────────┐     │
│                    │         RAGPipeline                  │     │
│                    │  rag_pipeline.py                     │     │
│                    │  1. Query rewrite                    │     │
│                    │  2. HyDE blending                    │     │
│                    │  3. Vector search                    │     │
│                    │  4. CRAG grading                     │     │
│                    │  5. LLM generation                   │     │
│                    └──────┬──────────────┬───────────────┘     │
│                           │              │                      │
│                ┌──────────▼───┐   ┌──────▼────────┐           │
│                │EmbeddingService│   │   LLMClient   │           │
│                │embedding.py  │   │  llm_client.py│           │
│                └──────────────┘   └───────────────┘           │
│                           │                                     │
│                    ┌──────▼──────────┐                         │
│                    │   VectorStore   │                         │
│                    │ vector_store.py │                         │
│                    │ pgvector/cosine │                         │
│                    └──────┬──────────┘                         │
│                           │                                     │
│                    ┌──────▼──────────┐                         │
│                    │  PostgreSQL DB  │                         │
│                    │  + pgvector     │                         │
│                    └─────────────────┘                         │
└─────────────────────────────────────────────────────────────────┘
```

**Technology stack**:
- Backend: Django 5 + Django REST Framework
- Database: PostgreSQL with `pgvector` extension
- Embedding: SentenceTransformers (local) or OpenAI-compatible API
- LLM: Any OpenAI-compatible API (Ollama, LM Studio, OpenAI, etc.)
- Frontend: Django templates + vanilla JS + `marked.js` for Markdown rendering

---

## 2. Ingestion Pipeline

All ingestion types share a common base (`BaseIngestionService._embed_and_store`) which:
1. Groups chunks by title into `Document` records
2. Calls `EmbeddingService.get_embedding()` on each chunk's content
3. Bulk-inserts `DocumentChunk` rows with the embedding vector

### 2.1 URL Ingestion

**File**: `backend/api_support/services/url_ingestion.py`  
**Entry point**: `URLIngestionService.ingest_url(name, url, crawl_depth=2, max_pages=50)`

**Process**:
1. BFS crawl starting from `url`, up to `crawl_depth` levels and `max_pages` pages
2. Same-domain links only; binary files (PDF, images, JS, CSS) are skipped
3. Each page is processed with `_split_by_headings(html, page_url)`:
   - **Primary**: `trafilatura.extract()` captures all visible text including emails, phone numbers, addresses, and link text
   - **Structure**: BeautifulSoup detects `h1/h2/h3` heading positions to create section boundaries
   - Resulting chunks: `(heading_title, section_text, metadata)`
4. Metadata per chunk:
   - `source_url` — the page URL
   - `heading` — the section heading
   - `anchor` — slugified heading for URL anchoring
   - `citation_url` — text fragment URL (`page#:~:text=first-sentence`) for precise browser highlighting

**Config knobs** (env vars):
```
URL_CRAWL_DEFAULT_DEPTH=2      # BFS depth
```

**Rate limiting**: 0.5 s per request (hard-coded in `ingest_url`, line ~144)

---

### 2.2 PDF Ingestion

**File**: `backend/api_support/services/pdf_ingestion.py`  
**Entry point**: `PDFIngestionService.ingest_pdf(name, file_obj)`

**Process**:
1. Extract text page-by-page using `PyPDF`
2. Short pages (<200 chars) are merged with the following page to avoid tiny chunks
3. One `DocumentChunk` per (merged) page
4. Metadata per chunk:
   - `page_number` — 1-based page number
   - `filename` — original filename
   - `citation_url` — `/media/uploads/{filename}#page={page_num}`

**Limitation**: Does not extract text from scanned PDFs (no OCR). Pages with only images yield empty text and are dropped.

---

### 2.3 Markdown Ingestion

**File**: `backend/api_support/services/markdown_ingestion.py`  
**Entry point**: `MarkdownIngestionService.ingest_markdown(name, file_obj)`

**Process**:
1. Split file at `## ` heading boundaries (level-2 headings)
2. Each section becomes one chunk with the heading as title
3. Metadata per chunk:
   - `heading` — the `## Heading` text
   - `anchor` — slugified heading
   - `filename` — original filename
   - `citation_url` — `#anchor-slug`

---

### 2.4 JSON Ingestion

**File**: `backend/api_support/services/ingestion.py`  
**Entry point**: `IngestionService.ingest_documents(documents, source_name)`  
**API endpoint**: `POST /api/docs/ingest/`

**Process**:
1. Accepts a JSON array of `{title, content}` objects
2. Content is split into ~500-token paragraphs
3. Each paragraph becomes one chunk under the document title

> **Note**: This is a legacy path that does not use the `Source` model's document-grouping capabilities. New sources should use the URL/PDF/Markdown endpoints.

---

## 3. RAG Query Pipeline

**File**: `backend/api_support/services/rag_pipeline.py`  
**Entry point**: `RAGPipeline.answer(question, conversation_id, top_k, source_ids)`

### 3.1 Query Rewriting

**Method**: `_rewrite_query(question, history)`

On multi-turn conversations, the user's follow-up question is rewritten into a self-contained query using the conversation history. This ensures the embedding search is not confused by pronouns or missing context.

Example:
- History: "Tell me about Pavitra's skills"
- Follow-up: "What about contact info?"
- Rewritten: "What is Pavitra's contact information?"

If the LLM is unavailable, the original question is used as-is (safe fallback).

---

### 3.2 HyDE (Hypothetical Document Embeddings)

**Method**: `_hypothetical_answer(question)`  
**Controlled by**: `RAG_USE_HYDE=true` (env var)

HyDE improves retrieval for queries where the question phrasing differs significantly from the indexed document language:

1. Ask the LLM to generate a short hypothetical answer to the question
2. Embed both the raw query and the hypothetical answer
3. Blend: `query_embedding = 0.7 × raw + 0.3 × hypothetical`
4. Normalise the blended vector before searching

The 70/30 blend keeps the search anchored to the actual query while giving the hypothetical answer some influence.

**System prompt** (line ~66):
```python
"You are a knowledgeable assistant. Generate a concise, factual answer based 
on what the source content is likely to say."
```

> **Why not pure HyDE?** A pure hypothetical answer can hallucinate off-topic language, pulling the embedding away from relevant chunks. The blend prevents this.

---

### 3.3 Vector Search

**Method**: `VectorStore.search(embedding, top_k, source_ids)`  
**Algorithm**: Cosine distance on pgvector `VectorField`

Retrieves the `top_k` most semantically similar `DocumentChunk` rows. If `source_ids` is provided (user selected specific knowledge base sources in the UI), only chunks from those sources are searched.

Default `top_k = 8` (increased from 5 to give CRAG more candidates to filter).

---

### 3.4 CRAG Grading

**Method**: `_crag_filter(query, chunks)`  
**Controlled by**: `RAG_USE_CRAG=true`, `RAG_CRAG_THRESHOLD=0.6` (env vars)

After vector search returns `top_k` chunks, CRAG (Corrective RAG) filters out low-relevance chunks using the LLM as a judge:

1. Build a batch prompt listing all chunks (first 600 chars each)
2. Ask the LLM to return a JSON float array: `[0.9, 0.1, 0.7, ...]`
3. Keep only chunks with score ≥ `RAG_CRAG_THRESHOLD`
4. Return confidence level:
   - `"high"` — all chunks passed
   - `"low"` — some chunks filtered
   - `"none"` — all chunks filtered → returns a "no information" response without calling the LLM again

If CRAG parse fails (malformed JSON from LLM), all chunks pass through (fail-open).

---

### 3.5 Final LLM Generation

**Method**: `_build_messages(question, retrieved_chunks, conversation)`

Builds the final message list for the LLM:
- System prompt: strict grounded-answer instruction
- Conversation history: all prior messages in the conversation
- User prompt: context blocks + question

Each context block looks like:
```
[Section Heading](citation_url)
<chunk content>
```

The LLM is instructed to answer **strictly from the provided context** and say so clearly if the context is insufficient.

---

## 4. Embedding Service

**File**: `backend/api_support/services/embedding.py`  
**Class**: `EmbeddingService`

Supports two backends:

| Backend | Description |
|---------|-------------|
| `local` | SentenceTransformers model loaded in-process (`_load_local_model`) |
| `openai` | OpenAI-compatible `/embeddings` API endpoint |

**Dimension adaptation** (`_adapt_dimension`):
- If the model outputs fewer dimensions than `VECTOR_DIMENSIONS`: pads with zeros
- If more: truncates
- This allows switching models without changing the database schema, at the cost of some information loss for truncated models

**Configuration** (env vars):
```
EMBEDDING_BACKEND=local          # "local" or "openai"
EMBEDDING_MODEL_NAME=nomic-embed-text  # model name
VECTOR_DIMENSIONS=768            # must match DB schema
LLM_API_KEY=...                  # used only for openai backend
LLM_API_BASE_URL=https://api.openai.com/v1  # used only for openai backend
```

---

## 5. Vector Store

**File**: `backend/api_support/services/vector_store.py`  
**Class**: `VectorStore`

Two operations:
- `upsert_chunks(chunks)` — bulk insert `DocumentChunk` rows via `bulk_create`
- `search(embedding, top_k, source_ids)` — cosine distance query via pgvector `CosineDistance` operator

The `DocumentChunk.embedding` field is a `pgvector.django.VectorField(dimensions=768)`.

**Important**: changing `VECTOR_DIMENSIONS` requires a database migration AND re-ingesting all documents. The old embeddings at the old dimension are incompatible.

---

## 6. LLM Client

**File**: `backend/api_support/services/llm_client.py`  
**Class**: `LLMClient`

Wraps any OpenAI-compatible chat completions API (`/chat/completions` endpoint). Used for:
- Query rewriting
- HyDE hypothetical answer generation
- CRAG grading
- Final answer generation

**Configuration** (env vars):
```
LLM_API_KEY=...
LLM_API_BASE_URL=http://localhost:11434/v1   # Ollama example
LLM_MODEL_NAME=llama3.2                      # model name
```

Raises `LLMUnavailableError` on connection failure; callers have graceful fallbacks.

---

## 7. Database Models

**File**: `backend/api_support/models.py`

```
Source (name, type, origin, created_at)
  └── Document (title, source_name, created_at)
        └── DocumentChunk (chunk_index, content, metadata JSON, embedding VectorField)

Conversation (title, created_at)
  └── Message (role: user|assistant, content, created_at)
```

| Model | Key fields | Notes |
|-------|-----------|-------|
| `Source` | `type` choices: url/pdf/markdown/json; `origin`: URL or filename | One per ingestion call |
| `Document` | Groups chunks by heading/section | Many per Source |
| `DocumentChunk` | `content`, `metadata` (JSON), `embedding` (768-d vector) | Many per Document |
| `Conversation` | Per chat session | Auto-created on first message |
| `Message` | `role` = user / assistant | Ordered by `created_at` |

---

## 8. API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/api/chat/` | Ask a question; returns `{answer, sources, conversation_id, confidence}` |
| `GET` | `/api/sources/` | List all ingested sources |
| `POST` | `/api/sources/ingest/url/` | Crawl and ingest a URL |
| `POST` | `/api/sources/ingest/file/` | Ingest PDF or Markdown file |
| `DELETE` | `/api/sources/<id>/` | Delete a source (cascades to documents + chunks) |
| `POST` | `/api/docs/ingest/` | Legacy: ingest raw JSON documents |
| `GET` | `/` | Chat UI page |
| `GET` | `/sources/` | Source management page |
| `GET` | `/setup/` | Setup guide page |

**Chat request body**:
```json
{
  "query": "What is Pavitra's email?",
  "conversation_id": null,
  "source_ids": [1, 2]
}
```

**Chat response body**:
```json
{
  "answer": "...",
  "conversation_id": 42,
  "confidence": "high",
  "sources": [
    {
      "document_id": 7,
      "document_title": "Contact",
      "chunk_index": 0,
      "snippet": "...",
      "citation_url": "https://example.com/contact#:~:text=...",
      "source_type": "url",
      "source_origin": "https://example.com"
    }
  ]
}
```

---

## 9. Configuration Reference

All settings are in `backend/config/settings.py` and read from environment variables.

| Env Var | Default | Description |
|---------|---------|-------------|
| `DJANGO_SECRET_KEY` | — | Django secret key (required in production) |
| `DJANGO_DEBUG` | `True` | Debug mode |
| `DJANGO_ALLOWED_HOSTS` | `*` | Allowed hostnames |
| `DB_HOST` | `localhost` | PostgreSQL host |
| `DB_PORT` | `5432` | PostgreSQL port |
| `DB_NAME` | `ragdb` | Database name |
| `DB_USER` | `raguser` | Database user |
| `DB_PASSWORD` | `ragpass` | Database password |
| `LLM_API_KEY` | `ollama` | API key for LLM / embedding API |
| `LLM_API_BASE_URL` | `http://localhost:11434/v1` | OpenAI-compatible base URL |
| `LLM_MODEL_NAME` | `llama3.2` | Chat model name |
| `EMBEDDING_BACKEND` | `local` | `local` or `openai` |
| `EMBEDDING_MODEL_NAME` | `nomic-embed-text` | Embedding model name |
| `VECTOR_DIMENSIONS` | `768` | Embedding dimensions (must match DB schema) |
| `RAG_USE_HYDE` | `True` | Enable Hypothetical Document Embeddings |
| `RAG_USE_CRAG` | `True` | Enable CRAG relevance grading |
| `RAG_CRAG_THRESHOLD` | `0.6` | Minimum relevance score (0.0–1.0) |
| `URL_CRAWL_DEFAULT_DEPTH` | `2` | BFS depth for URL crawling |

---

## 10. How-To: Changing Models & Tuning

### 10.1 Change the Embedding Model

**Step 1 — Pick a model and note its native dimension**:

| Model | Dimension | Backend |
|-------|-----------|---------|
| `nomic-embed-text` (Ollama) | 768 | local |
| `BAAI/bge-small-en` (HuggingFace) | 384 | local |
| `BAAI/bge-large-en-v1.5` | 1024 | local |
| `text-embedding-3-small` (OpenAI) | 1536 | openai |
| `text-embedding-3-large` (OpenAI) | 3072 | openai |

**Step 2 — If changing the dimension**, create a new migration:
```bash
# Inside the backend container / virtualenv:
python manage.py makemigrations --name alter_embedding_dim api_support
# Edit the generated migration to change VectorField(dimensions=NEW_DIM)
python manage.py migrate
```
Also update `VECTOR_DIMENSIONS` in `.env`.

**Step 3 — Re-ingest all documents** (existing embeddings are incompatible):
```bash
# Delete all sources in the UI or via DB:
# DELETE FROM api_support_documentchunk;
# DELETE FROM api_support_document;
# DELETE FROM api_support_source;
# Then re-add sources via the Sources page.
```

**Step 4 — Update `.env`**:
```
EMBEDDING_BACKEND=local               # or "openai"
EMBEDDING_MODEL_NAME=BAAI/bge-large-en-v1.5
VECTOR_DIMENSIONS=1024
```

> **Dimension adaptation note**: If you do NOT update the migration and the model dimension differs from `VECTOR_DIMENSIONS`, `EmbeddingService._adapt_dimension()` will pad/truncate automatically. Padding zeros degrades search quality significantly for large mismatches. Only use it for minor differences.

---

### 10.2 Change the LLM Model

Edit `.env`:
```
LLM_API_BASE_URL=http://localhost:11434/v1   # Ollama
LLM_MODEL_NAME=mistral                       # any model pulled in Ollama
```
Or for OpenAI:
```
LLM_API_BASE_URL=https://api.openai.com/v1
LLM_API_KEY=sk-...
LLM_MODEL_NAME=gpt-4o-mini
```

No code changes or migrations needed.

> **Note**: CRAG grading requires the LLM to return valid JSON arrays. Smaller/quantised models sometimes produce malformed responses; in that case CRAG fails open (all chunks pass through).

---

### 10.3 Tune Retrieval Quality

**`top_k`** — how many chunks are retrieved before CRAG filters:
- File: `backend/api_support/services/rag_pipeline.py`, `answer()` method, `top_k=8`
- Increase if relevant chunks are being missed; decrease to reduce LLM token usage

**`RAG_CRAG_THRESHOLD`** — minimum relevance score to keep a chunk:
- Default: `0.6`; range: `0.0` (keep all) to `1.0` (keep only perfect matches)
- Lowering catches more relevant chunks but also more noise
- Raising improves precision but risks filtering relevant chunks

**`RAG_USE_HYDE`** — enable/disable HyDE blending:
- Helps when query language differs from document language
- Disable (`RAG_USE_HYDE=False`) if queries are already in the same language as documents

**`RAG_USE_CRAG`** — enable/disable CRAG grading:
- Disable (`RAG_USE_CRAG=False`) for faster responses; all `top_k` chunks pass to the LLM

**HyDE blend ratio** — code only (line ~203 in `rag_pipeline.py`):
```python
blended = 0.7 * raw_emb + 0.3 * hyde_emb
```
Increase the HyDE weight (e.g., 0.4) for queries where document language differs greatly.

---

### 10.4 Modify Chunking Strategy

**URL chunking** (`url_ingestion.py`, `_split_by_headings`):
- Currently: trafilatura full-text extraction + split at h1/h2/h3 heading boundaries
- To change chunk size: after splitting by headings, further split long sections by paragraph count
- To add h4/h5 support: add `"h4", "h5"` to the `soup.find_all(["h1", "h2", "h3"])` call

**PDF chunking** (`pdf_ingestion.py`):
- Currently: one chunk per page (short pages <200 chars merged with next)
- To use fixed-size chunking: replace page loop with a sliding-window character splitter
- Change merge threshold: modify the `200` constant in the short-page merging logic

**Markdown chunking** (`markdown_ingestion.py`):
- Currently: split at `## ` level-2 headings
- To also split at `### `: add `"### "` to the heading regex pattern

---

### 10.5 Modify the RAG Prompt

**System prompt** (`rag_pipeline.py`, `_build_system_prompt`):
```python
def _build_system_prompt(self) -> str:
    return (
        "You are a grounded RAG assistant. "
        "Answer the user's question STRICTLY based on the provided context. "
        "Do not invent facts not present in the context. "
        "If the context is insufficient, say so clearly."
    )
```
To make it domain-specific (e.g., customer support):
```python
return (
    "You are a helpful customer support assistant for Acme Corp. "
    "Answer questions strictly from the provided documentation. "
    "Be concise and friendly. If the answer is not in the context, say "
    "'I don't have that information — please contact support@acme.com'."
)
```

**CRAG grading prompt** (`rag_pipeline.py`, `_CRAG_BATCH_PROMPT`):
- The prompt asks for float scores 0.0–1.0. Do not change the output format.
- You can add domain context: e.g., replace "Query:" with "Customer question:"

**HyDE prompt** (`rag_pipeline.py`, `_HYDE_SYSTEM` / `_HYDE_USER`):
- Tune the persona to match your document type
- For technical docs: restore "technical documentation writer" framing
- For customer FAQs: "You are a customer support specialist"
