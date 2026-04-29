# General Purpose Grounded RAG Chat

A domain-agnostic Retrieval-Augmented Generation (RAG) chatbot with a full Django web UI.
Ingest any knowledge base — websites, PDFs, Markdown files — then ask questions and get cited, grounded answers powered by a local LLM running on Ollama.

---

## How It Works (Architecture)

```
Your Browser  ──►  localhost:8000  ──►  Django (Docker)
                                              │
                          ┌───────────────────┼───────────────────┐
                          ▼                   ▼                   ▼
                    PostgreSQL          Ollama (host)        File uploads
                    (Docker)       host.docker.internal      /media/
                    pgvector            :11434
                    embeddings +     ┌──────────────┐
                    conversations    │ llama3.2     │  ← chat & reasoning
                                     │ nomic-embed  │  ← turns text→vector
                                     └──────────────┘
```

**Every chat message triggers up to 4 Ollama calls:**

| Step | What happens | Ollama model |
|---|---|---|
| 1. Query rewrite | "show me that again" → standalone question | llama3.2 |
| 2. HyDE | LLM drafts a hypothetical answer to embed | llama3.2 |
| 3. Embed | Hypothetical answer converted to a 768-dim vector | nomic-embed-text |
| 4. Vector search | pgvector finds the 5 most similar stored chunks | — (database) |
| 5. CRAG grade | LLM scores each chunk 0–1 for relevance, drops weak ones | llama3.2 |
| 6. Final answer | LLM answers strictly from the kept chunks | llama3.2 |

> **Ollama must be running on your host machine the entire time.** Docker cannot start Ollama — they are separate processes.

---

## Prerequisites

Install these **once** on your machine before anything else.

| Tool | What it does | Download |
|---|---|---|
| **Docker Desktop** | Runs Django + PostgreSQL in containers | https://docs.docker.com/get-docker/ |
| **Ollama** | Runs LLM and embedding models locally | https://ollama.com/download |

After installing, verify both are available:
```powershell
docker --version        # Docker version 27.x.x …
ollama --version        # ollama version 0.x.x
```

---

## Terminal Guide — What Runs Where

You will use **two PowerShell terminals** at the same time. Keep them both open while using the app.

```
┌─────────────────────────────────┐   ┌─────────────────────────────────┐
│  Terminal 1 — Ollama (host)     │   │  Terminal 2 — Docker            │
│                                 │   │                                 │
│  ollama serve                   │   │  docker compose up              │
│                                 │   │  (or docker compose up --build) │
│  ← Keep this open always.       │   │                                 │
│    If it closes, chat breaks.   │   │  ← Shows Django + DB logs.      │
│                                 │   │    Keep open while using app.   │
└─────────────────────────────────┘   └─────────────────────────────────┘
```

A **third terminal** is used only for one-off management commands like checking logs or deleting data.

---

## First-Time Setup

Do these steps **once** when you set up the project for the first time.

### Step 1 — Pull the AI models (Terminal 1)

Open PowerShell and run:

```powershell
ollama pull llama3.2
ollama pull nomic-embed-text
```

This downloads ~2–4 GB total. Wait for both to finish before continuing.

Verify they downloaded:
```powershell
ollama list
```
You should see both `llama3.2` and `nomic-embed-text` in the list.

### Step 2 — Configure environment

In your project folder, copy the example config:

```powershell
cd "D:\My Apps\RAG AI Chatbot\api-support-ai-chatbot"
copy env.example .env
```

The defaults in `.env` work as-is for local Ollama on Windows. You only need to edit one thing for security:

```
# .env — open in Notepad or VS Code
DJANGO_SECRET_KEY=replace-me-with-a-secure-key   ← change this to any long random string
```

Everything else can stay as-is for local development.

### Step 3 — Start Ollama (Terminal 1 — keep open)

```powershell
ollama serve
```

You will see:
```
time=... level=INFO source=... msg="Listening on 127.0.0.1:11434"
```

**Leave this terminal open.** If you close it, the app stops working.

### Step 4 — Build and start Docker (Terminal 2 — keep open)

```powershell
cd "D:\My Apps\RAG AI Chatbot\api-support-ai-chatbot"
docker compose up --build
```

The `--build` flag is only needed the first time (or after you change code/Dockerfile).
It will:
- Build the Django Docker image (~2–3 min first time)
- Start PostgreSQL
- **Automatically run database migrations** (the entrypoint handles this)
- **Automatically collect static files** (CSS/JS)
- Start the Django development server

You should see output like:
```
web-1  | ==> Running database migrations...
web-1  | Operations to perform: Apply all migrations
web-1  | Running migrations: Applying ...OK
web-1  | ==> Collecting static files...
web-1  | ==> Starting Django development server...
web-1  | Starting development server at http://0.0.0.0:8000/
```

**Leave this terminal open.** Django logs appear here as you use the app.

### Step 5 — Open the app

Visit **http://localhost:8000** in your browser.

You will see the chat UI. No sources are ingested yet — you cannot chat until you add one.

### Step 6 — Add your first source

Go to **http://localhost:8000/sources/**

Choose a tab:

| Tab | What to provide | Use case |
|---|---|---|
| **URL** | A public web URL | Documentation sites, blog posts, your portfolio |
| **PDF** | Upload a `.pdf` file | Guides, manuals, whitepapers |
| **Markdown** | Upload a `.md` file | README files, notes, project docs |

Fill in a **Name** (e.g. `My Portfolio`) and the URL or file, then click **Ingest**.

Ingestion can take 10–60 seconds depending on the size of the content (Ollama needs to embed every chunk).

When done, the source appears in the table with a **Delete** button.

### Step 7 — Chat

Go to **http://localhost:8000**

1. Select your source in the left sidebar (hold Ctrl for multiple)
2. Type a question and press **Send** or **Ctrl+Enter**

The assistant will answer strictly from your ingested documents, with clickable citations.

---

## Daily Use (After First Setup)

Every time you want to use the app:

**Terminal 1 — Start Ollama:**
```powershell
ollama serve
```

**Terminal 2 — Start Docker:**
```powershell
cd "D:\My Apps\RAG AI Chatbot\api-support-ai-chatbot"
docker compose up
```

(No `--build` needed for regular use — only after code changes.)

Open **http://localhost:8000** and chat.

**To stop everything:** press `Ctrl+C` in Terminal 2, then `Ctrl+C` in Terminal 1.

---

## Management Commands (Terminal 3 — as needed)

These are one-off commands. Open a third PowerShell for them.

```powershell
cd "D:\My Apps\RAG AI Chatbot\api-support-ai-chatbot"

# Check what's running
docker compose ps

# View live Django logs (last 50 lines)
docker compose logs web --tail=50 --follow

# Run migrations manually (only needed if you changed models.py)
docker compose exec web python manage.py migrate

# Collect static files manually (only needed after CSS/JS changes)
docker compose exec web python manage.py collectstatic --noinput

# Open a Django shell (for debugging)
docker compose exec web python manage.py shell

# Check Ollama is reachable from inside Docker
docker compose exec web python -c "import requests; r=requests.get('http://host.docker.internal:11434/api/tags'); print(r.json())"

# Stop and remove containers (keeps database data)
docker compose down

# Stop and wipe ALL data including the database (full reset)
docker compose down -v
```

---

## After Code Changes

If you edit Python files (`.py`), the Django dev server **auto-reloads** — no restart needed.

If you change any of the following, rebuild:

| Changed file | Command needed |
|---|---|
| `Dockerfile` | `docker compose up --build` |
| `requirements.txt` | `docker compose up --build` |
| `models.py` | `docker compose exec web python manage.py migrate` |
| `.env` | `docker compose down && docker compose up` |
| CSS / JS | `docker compose exec web python manage.py collectstatic --noinput` |

---

## Deleting a Source

Go to **http://localhost:8000/sources/**

Every row in the sources table has a **Delete** button in the rightmost column.
Clicking it shows a confirmation dialog. Confirming removes the source **and all its documents and embedded chunks** from the database permanently.

---

## Troubleshooting

### "Something went wrong (HTTP 500)" in chat

This always means an error inside Django. Check the logs in Terminal 2:

```powershell
docker compose logs web --tail=30
```

Common causes:

| Log message | Fix |
|---|---|
| `ConnectionRefusedError` or `Cannot connect to LLM` | Ollama is not running — start it with `ollama serve` in Terminal 1 |
| `sentence-transformers/nomic-embed-text is not a valid model identifier` | Your `.env` has `EMBEDDING_BACKEND=local` — change it to `EMBEDDING_BACKEND=openai`, then run `docker compose down && docker compose up` |
| `RepositoryNotFoundError` | Same as above |
| Any other error | Copy the full traceback from the logs and investigate |

### "The language model is unavailable" (HTTP 503) in chat

Ollama is not running or unreachable. Check:

1. Is `ollama serve` running in Terminal 1?
2. Test from inside Docker: `docker compose exec web python -c "import requests; r=requests.get('http://host.docker.internal:11434/api/tags'); print(r.json())"`
3. On Windows, `host.docker.internal` resolves to your host from inside Docker — this is correct and should not be changed.

### Chat returns "I don't have this information"

This is not an error — it means CRAG graded all retrieved chunks as below the relevance threshold. This happens when:
- No source is selected in the sidebar
- The question is unrelated to your ingested content
- You haven't ingested any sources yet

### Sources table is empty after ingest

The ingest may have partially succeeded. Check:
- The result message in the UI (shows documents + chunks created)
- Logs in Terminal 2 for any errors during embedding

### Static files (CSS/JS) not loading — page looks unstyled

```powershell
docker compose exec web python manage.py collectstatic --noinput
docker compose restart web
```

### `.env` changes have no effect

`docker compose restart web` does **not** re-read `.env`. You must recreate the container:

```powershell
docker compose down
docker compose up
```

### Port 8000 already in use

Something else is using port 8000. Find and kill it, or change the port in `docker-compose.yml`:
```yaml
ports:
  - "8001:8000"   # change left side only
```
Then access the app at `http://localhost:8001`.

---

## Switching to a Cloud API (OpenAI, Anthropic, etc.)

You don't need Ollama if you use a cloud LLM. Update `.env`:

```env
LLM_API_KEY=sk-...your-key...
LLM_API_BASE_URL=https://api.openai.com/v1
LLM_MODEL_NAME=gpt-4o-mini
EMBEDDING_BACKEND=openai
EMBEDDING_MODEL_NAME=text-embedding-3-small
VECTOR_DIMENSIONS=1536
```

Then recreate the container:
```powershell
docker compose down
docker compose up
```

With a cloud API, Terminal 1 (Ollama) is no longer needed.

---

## Environment Variables Reference

| Variable | Default | Description |
|---|---|---|
| `DJANGO_SECRET_KEY` | `replace-me` | Django secret key — change this |
| `DJANGO_DEBUG` | `true` | Set `false` in production |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1` | Comma-separated allowed hosts |
| `DB_NAME` | `rag_support` | PostgreSQL database name |
| `DB_USER` | `rag_user` | PostgreSQL user |
| `DB_PASSWORD` | `rag_password` | PostgreSQL password |
| `DB_HOST` | `db` | PostgreSQL host (Docker service name — do not change) |
| `LLM_API_KEY` | `ollama` | API key (Ollama ignores this value) |
| `LLM_API_BASE_URL` | `http://host.docker.internal:11434/v1` | OpenAI-compatible base URL |
| `LLM_MODEL_NAME` | `llama3.2` | Chat/reasoning model |
| `EMBEDDING_BACKEND` | `openai` | `openai` = use the API at `LLM_API_BASE_URL` (works with Ollama); `local` = sentence-transformers (advanced) |
| `EMBEDDING_MODEL_NAME` | `nomic-embed-text` | Embedding model (must be pulled in Ollama) |
| `VECTOR_DIMENSIONS` | `1536` | Must match `VectorField(dimensions=N)` in `models.py` |
| `RAG_USE_HYDE` | `true` | Enable Hypothetical Document Embeddings (better retrieval, slower) |
| `RAG_USE_CRAG` | `true` | Enable Corrective RAG grading (filters irrelevant chunks) |
| `RAG_CRAG_THRESHOLD` | `0.6` | Minimum relevance score 0.0–1.0 to keep a chunk |
| `URL_CRAWL_DEFAULT_DEPTH` | `2` | BFS crawl depth for URL ingest (0 = single page) |

**Speed tip:** Set `RAG_USE_HYDE=false` and `RAG_USE_CRAG=false` to cut LLM calls from 4 to 1 per query (much faster for demos, slightly less accurate).

---

## Project Structure

```
api-support-ai-chatbot/
├── docker-compose.yml          # Web + PostgreSQL services
├── Dockerfile                  # Django image (runs migrate + collectstatic on start)
├── entrypoint.sh               # Auto-runs migrations and collectstatic before server starts
├── requirements.txt            # Python dependencies
├── env.example                 # Copy to .env — all supported variables with defaults
├── .env                        # Your local config (not committed to git)
└── backend/
    ├── manage.py
    ├── config/
    │   ├── settings.py         # Django settings (reads from .env)
    │   └── urls.py             # Root URL routing
    ├── templates/              # Django HTML templates
    │   ├── base.html
    │   ├── chat.html           # / — chat UI with source selector + citation chips
    │   ├── sources.html        # /sources/ — ingest URLs, PDFs, Markdown; delete sources
    │   └── setup.html          # /setup/ — setup guide
    ├── static/
    │   ├── css/styles.css
    │   └── js/
    │       ├── chat.js         # Chat UI logic (send, render, citations)
    │       └── sources.js      # Source table (load, delete) + ingest forms
    └── api_support/
        ├── models.py           # Source, Document, DocumentChunk, Conversation, Message
        ├── views.py            # API views
        ├── serializers.py      # DRF serializers
        ├── urls.py             # API URL routing (/api/...)
        ├── frontend_urls.py    # Frontend URL routing (/, /sources/, /setup/)
        ├── frontend_views.py   # TemplateView classes
        ├── migrations/
        └── services/
            ├── rag_pipeline.py         # Full pipeline: rewrite → HyDE → CRAG → answer
            ├── base_ingestion.py       # Shared embed-and-store logic
            ├── url_ingestion.py        # BFS web crawler (httpx + trafilatura)
            ├── pdf_ingestion.py        # PDF page extractor (pypdf)
            ├── markdown_ingestion.py   # Markdown splitter (by ## heading)
            ├── ingestion.py            # Legacy JSON ingest
            ├── embedding.py            # Ollama or API-based text embeddings
            ├── vector_store.py         # pgvector cosine similarity search
            └── llm_client.py           # OpenAI-compatible chat completions client
```

---

## API Reference

| Method | Path | Description |
|---|---|---|
| `GET` | `/` | Chat UI |
| `GET` | `/sources/` | Sources management (ingest + delete) |
| `GET` | `/setup/` | Setup guide |
| `POST` | `/api/chat/` | Ask a question |
| `GET` | `/api/sources/` | List all sources |
| `DELETE` | `/api/sources/<id>/` | Delete a source (cascades to documents + chunks) |
| `POST` | `/api/sources/ingest/url/` | Crawl and ingest a URL |
| `POST` | `/api/sources/ingest/file/` | Ingest a PDF or Markdown file |
| `POST` | `/api/docs/ingest/` | Legacy bulk JSON ingest |

**Example — chat via API:**
```powershell
curl -X POST http://localhost:8000/api/chat/ `
  -H "Content-Type: application/json" `
  -d '{"query": "What projects has Pavitra worked on?"}'
```

**Example — ingest a URL:**
```powershell
curl -X POST http://localhost:8000/api/sources/ingest/url/ `
  -H "Content-Type: application/json" `
  -d '{"name": "My Portfolio", "url": "https://example.com", "crawl_depth": 2}'
```

**Chat response shape:**
```json
{
  "answer": "...",
  "confidence": "high",
  "conversation_id": 1,
  "sources": [
    {
      "document_title": "Projects",
      "snippet": "...",
      "citation_url": "https://example.com#:~:text=...",
      "chunk_index": 0,
      "document_id": 3
    }
  ]
}
```

`confidence` values: `"high"` (all chunks passed CRAG) | `"low"` (partial) | `"none"` (no relevant chunks found — answer is "I don't have this information")
