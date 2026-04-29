# General Purpose Grounded RAG Chat

A domain-agnostic Retrieval-Augmented Generation (RAG) chatbot with a full Django web UI. Ingest any knowledge base — websites, PDFs, Markdown files — then ask questions and get cited, grounded answers from a local LLM.

---

## What This Is

Most chatbots either hallucinate facts or answer only from their training data. This project wires a local LLM to *your* documents using three layered RAG techniques:

| Technique | What it does |
|---|---|
| **HyDE** (Hypothetical Document Embeddings) | LLM drafts a hypothetical answer first; that draft is embedded instead of the raw query. Dramatically improves retrieval on content-heavy docs where question style ≠ document style. |
| **CRAG** (Corrective RAG) | After retrieval, each chunk is graded for relevance. Irrelevant chunks are discarded. If nothing passes the threshold, the model says "I don't have this" instead of fabricating an answer. |
| **Conversation memory** | Multi-turn chat with automatic query rewriting — "show me a code example for that" correctly resolves "that" from the prior turn. |

Everything runs locally: Django + PostgreSQL/pgvector + Ollama. No external APIs required.

---

## Features

- **Multi-source knowledge bases** — ingest URLs (with BFS crawling), PDFs, and Markdown files as named sources
- **Scoped retrieval** — chat against one source, a subset, or all sources simultaneously
- **Deep-link citations** — every answer comes with clickable citations: text fragments for web pages, `#page=N` for PDFs, heading anchors for Markdown
- **Web UI** — chat page, sources management page, setup guide — no Node.js, pure Django templates + vanilla JS
- **Markdown rendering** in the chat UI (marked.js)
- **REST API** — all functionality exposed as JSON endpoints; easy to integrate into other apps
- **Configurable pipeline** — toggle HyDE, CRAG, and crawl depth via `.env`; swap LLM models without code changes

---

## Tech Stack

| Layer | Technology |
|---|---|
| Web framework | Django 5, Django REST Framework |
| Vector database | PostgreSQL 16 + pgvector |
| Local LLM | Ollama (`llama3.2` default) |
| Embeddings | Ollama `nomic-embed-text` (local, 768-dim → padded to 1536) |
| URL crawling | httpx + trafilatura + BeautifulSoup4 |
| PDF extraction | pypdf |
| Containerisation | Docker + docker-compose |
| Frontend | Django templates + vanilla JS + marked.js (CDN) |

---

## Project Structure

```
api-support-ai-chatbot/
├── docker-compose.yml          # Web + PostgreSQL services
├── Dockerfile                  # Django image
├── requirements.txt            # Python dependencies
├── env.example                 # All supported environment variables
├── backend/
│   ├── manage.py
│   ├── config/
│   │   ├── settings.py         # Django settings (reads from .env)
│   │   └── urls.py             # Root URL routing
│   ├── templates/              # Django HTML templates
│   │   ├── base.html
│   │   ├── chat.html           # / — chat UI
│   │   ├── sources.html        # /sources/ — manage knowledge bases
│   │   └── setup.html          # /setup/ — setup guide
│   ├── static/
│   │   ├── css/styles.css
│   │   └── js/
│   │       ├── chat.js
│   │       └── sources.js
│   └── api_support/
│       ├── models.py           # Source, Document, DocumentChunk, Conversation, Message
│       ├── views.py            # API views
│       ├── serializers.py      # DRF serializers
│       ├── urls.py             # API URL routing (/api/...)
│       ├── frontend_urls.py    # Frontend URL routing (/, /sources/, /setup/)
│       ├── frontend_views.py   # TemplateView classes
│       ├── migrations/
│       └── services/
│           ├── rag_pipeline.py     # Query rewrite → HyDE → CRAG → answer
│           ├── base_ingestion.py   # Shared embed-and-store logic
│           ├── url_ingestion.py    # BFS web crawler
│           ├── pdf_ingestion.py    # PDF page extractor
│           ├── markdown_ingestion.py
│           ├── ingestion.py        # Legacy JSON ingest (backwards compat)
│           ├── embedding.py        # Local or API embeddings
│           ├── vector_store.py     # pgvector similarity search
│           └── llm_client.py       # OpenAI-compatible chat completions
```

---

## Quick Start

### Prerequisites

1. **Docker Desktop** — [docs.docker.com/get-docker](https://docs.docker.com/get-docker/)
2. **Ollama** — [ollama.com/download](https://ollama.com/download)

### Step 1 — Pull models (run on host, not in Docker)

```bash
ollama pull llama3.2
ollama pull nomic-embed-text
```

### Step 2 — Configure

```bash
cp env.example .env
# The defaults in env.example work as-is for local Ollama.
# Edit DJANGO_SECRET_KEY to a random string for any non-toy use.
```

### Step 3 — Start

```bash
docker compose up --build
```

First run installs Python packages, runs migrations, and starts the server. Subsequent starts skip the build:

```bash
docker compose up
```

### Step 4 — Open the app

Visit **http://localhost:8000**

You'll see the chat UI. No sources are ingested yet — go to **Sources** to add one.

### Step 5 — Collect static (only needed once after a code change)

```bash
docker compose exec web python manage.py collectstatic --noinput
```

---

## Daily Use (After First Setup)

```bash
# Start Docker Desktop (if not already running)
docker compose up
# Open http://localhost:8000
```

That's it. No re-ingestion or re-migration unless you changed the schema or deleted your volumes.

---

## Adding Sources

### Via the UI

Go to **http://localhost:8000/sources/** and use one of the three tabs:

| Tab | Accepts | Notes |
|---|---|---|
| **URL** | Any public URL | Crawls same-domain links up to the set depth (default 2), max 50 pages |
| **PDF** | `.pdf` files | Extracts text page by page; citation links to `#page=N` |
| **Markdown** | `.md` files | Splits by `##` headings; citation links to heading anchors |

### Via the API

**Ingest a URL:**
```bash
curl -X POST http://localhost:8000/api/sources/ingest/url/ \
  -H "Content-Type: application/json" \
  -d '{"name": "My Portfolio", "url": "https://example.com", "crawl_depth": 2}'
```

**Ingest a PDF:**
```bash
curl -X POST http://localhost:8000/api/sources/ingest/file/ \
  -F "name=Cisco ISE Guide" \
  -F "file=@/path/to/guide.pdf"
```

**Ingest JSON docs (legacy bulk format):**
```bash
curl -X POST http://localhost:8000/api/docs/ingest/ \
  -H "Content-Type: application/json" \
  -d '{
    "source_name": "My API Docs",
    "docs": [
      {"title": "Authentication", "content": "Use Bearer tokens in the Authorization header."}
    ]
  }'
```

---

## Chatting

### Via the UI

Select a knowledge base from the sidebar (hold Ctrl/⌘ for multiple), type your question, and press **Send** or **Ctrl+Enter**.

Each assistant message shows:
- **Confidence badge** — `⚠ Low confidence` or `✗ Not found` when CRAG grades chunks as weak
- **Citation chips** — click to expand snippet + "Open source ↗" deep-link

### Via the API

```bash
curl -X POST http://localhost:8000/api/chat/ \
  -H "Content-Type: application/json" \
  -d '{"query": "What projects has Pavitra worked on?"}'
```

Scope to specific sources:
```bash
curl -X POST http://localhost:8000/api/chat/ \
  -H "Content-Type: application/json" \
  -d '{"query": "What is the authentication flow?", "source_ids": [1, 2]}'
```

Multi-turn (pass `conversation_id` from previous response):
```bash
curl -X POST http://localhost:8000/api/chat/ \
  -H "Content-Type: application/json" \
  -d '{"query": "Show me a code example for that", "conversation_id": 5}'
```

**Response shape:**
```json
{
  "answer": "...",
  "confidence": "high",
  "sources": [
    {
      "document_title": "Projects",
      "snippet": "...",
      "citation_url": "https://example.com#:~:text=...",
      "chunk_index": 0,
      "document_id": 3
    }
  ],
  "conversation_id": 1
}
```

`confidence` values: `"high"` | `"low"` | `"none"` (none = not found in indexed sources, no fabricated answer)

---

## API Reference

| Method | Path | Description |
|---|---|---|
| `GET` | `/` | Chat UI |
| `GET` | `/sources/` | Sources management UI |
| `GET` | `/setup/` | Setup guide UI |
| `POST` | `/api/chat/` | Ask a question |
| `GET` | `/api/sources/` | List all sources |
| `DELETE` | `/api/sources/<id>/` | Delete a source (cascades to docs + chunks) |
| `POST` | `/api/sources/ingest/url/` | Ingest a URL (crawls same-domain links) |
| `POST` | `/api/sources/ingest/file/` | Ingest a PDF or Markdown file (multipart) |
| `POST` | `/api/docs/ingest/` | Legacy bulk JSON ingest |

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `DJANGO_SECRET_KEY` | (required) | Django secret key |
| `DJANGO_DEBUG` | `true` | Set to `false` in production |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1` | Comma-separated allowed hosts |
| `DB_NAME` | `rag_support` | PostgreSQL database name |
| `DB_USER` | `rag_user` | PostgreSQL user |
| `DB_PASSWORD` | `rag_password` | PostgreSQL password |
| `DB_HOST` | `db` | PostgreSQL host (Docker service name) |
| `LLM_API_KEY` | `ollama` | API key (Ollama ignores this) |
| `LLM_API_BASE_URL` | `http://host.docker.internal:11434/v1` | OpenAI-compatible base URL |
| `LLM_MODEL_NAME` | `llama3.2` | Chat model to use |
| `EMBEDDING_BACKEND` | `local` | `local` (sentence-transformers) or `openai` |
| `EMBEDDING_MODEL_NAME` | `nomic-embed-text` | Embedding model name |
| `VECTOR_DIMENSIONS` | `1536` | Must match `VectorField(dimensions=N)` in models |
| `RAG_USE_HYDE` | `true` | Enable Hypothetical Document Embeddings |
| `RAG_USE_CRAG` | `true` | Enable Corrective RAG grading |
| `RAG_CRAG_THRESHOLD` | `0.6` | Minimum relevance score to keep a chunk |
| `URL_CRAWL_DEFAULT_DEPTH` | `2` | Default BFS crawl depth for URL ingest |

**Tip — disable HyDE and CRAG for faster demos:**
```
RAG_USE_HYDE=false
RAG_USE_CRAG=false
```
Then `docker compose restart web`.

---

## RAG Pipeline — How It Works

```
User question
    │
    ▼
1. Query rewrite (if multi-turn)
   LLM rewrites "show me a curl for that" → "show me a curl example for the auth endpoint"
    │
    ▼
2. HyDE — Hypothetical Document Embedding
   LLM drafts a 2-3 sentence hypothetical answer → embed that text
   (matches doc style better than embedding the raw question)
    │
    ▼
3. Vector search  (pgvector cosine similarity, top_k=5)
   Filter by source_ids if provided
    │
    ▼
4. CRAG — Corrective RAG grading
   One batched LLM call: "score these 5 chunks 0.0–1.0"
   Discard chunks below threshold (0.6)
   → confidence = "none"  if 0 chunks pass  → return "not found", stop
   → confidence = "low"   if partial
   → confidence = "high"  if all pass
    │
    ▼
5. Final answer
   LLM answers strictly from the kept chunks
   Citations built from chunk metadata (source_url, page_number, anchor)
    │
    ▼
6. Persist to Conversation + Message rows
    │
    ▼
RAGResponse(answer, sources, conversation_id, confidence)
```

**LLM call budget per query:** 3–4 calls (rewrite + HyDE + CRAG batch + final answer).

---

## Switching LLM Models

The model is fully configurable via `.env` — no code changes needed.

**Try a larger model:**
```bash
ollama pull llama3.2:3b
# or
ollama pull mistral
```
Then in `.env`:
```
LLM_MODEL_NAME=llama3.2:3b
```
Restart: `docker compose restart web`

**Use a cloud API instead of Ollama:**
```
LLM_API_KEY=sk-...
LLM_API_BASE_URL=https://api.openai.com/v1
LLM_MODEL_NAME=gpt-4o-mini
EMBEDDING_BACKEND=openai
EMBEDDING_MODEL_NAME=text-embedding-3-small
VECTOR_DIMENSIONS=1536
```

---

## Troubleshooting

**"Cannot connect to the LLM" error in chat**
- Run `ollama serve` on your host (outside Docker).
- Confirm the model is pulled: `ollama list`
- On Windows, `host.docker.internal` resolves to your host machine from inside Docker — this is the correct value for `LLM_API_BASE_URL`.

**Chat returns 500 / blank response**
- Check container logs: `docker compose logs web`
- If you see `ConnectionRefusedError`, Ollama is not running.

**Sources table is empty after ingest**
- Check the ingest result message in the UI — it shows docs/chunks created.
- Confirm the source appears in `GET /api/sources/`.

**Embedding dimension mismatch warning on startup**
- Your embedding model outputs more dimensions than `VECTOR_DIMENSIONS`. Update `VECTOR_DIMENSIONS` in `.env` to match, then re-create the DB volume and re-ingest:
  ```bash
  docker compose down -v
  docker compose up --build
  docker compose exec web python manage.py migrate
  ```

**URL ingest is slow / seems stuck**
- The crawler adds a 0.5 s polite delay between pages and is capped at 50 pages. A depth-2 crawl of a 50-page site takes up to ~25 s. This is normal.

**Static files (CSS/JS) not loading**
```bash
docker compose exec web python manage.py collectstatic --noinput
docker compose restart web
```

---

## Known Limitations (v1)

- **No streaming** — answers arrive as one block after the full LLM round-trip (~3–8 s on local hardware). SSE support planned.
- **No embedding cache** — re-ingesting the same URL re-computes all embeddings.
- **URL crawler does not parse `robots.txt`** — only use on sites you own or have permission to crawl.
- **No authentication** on ingest/delete endpoints — localhost use only.

---

## Portfolio Integration (Future)

To embed this chatbot on an external site like `pavitramandal.online`:

**Option A — iframe widget** (no CORS needed):
Deploy Django publicly, then embed:
```html
<iframe src="https://your-domain.com/widget/" style="width:400px;height:600px;border:none;"></iframe>
```

**Option B — API-only** (Next.js or any frontend):
Your portfolio's JS calls `POST /api/chat/` directly with `source_ids=[<portfolio-source-id>]`. Add CORS headers (`django-cors-headers`) and an API key check to the `ChatView`.

Both options work today with zero architectural changes.
