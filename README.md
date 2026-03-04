## RAG API Support Chatbot

### Overview

This project is a **Retrieval-Augmented Generation (RAG) API Support Chatbot** built with:

- **Django + Django REST Framework** for the HTTP API.
- **PostgreSQL + pgvector** as the vector database for semantic search.
- A **local or cloud LLM** exposed via an OpenAI-compatible HTTP API (Ollama by default in this setup).
- **Docker + docker-compose** for local development and deployment.

The chatbot is designed to help users who struggle to use APIs correctly. You ingest your **API documentation, examples, and FAQs**, and then ask questions such as:

- “How do I authenticate to this API?”
- “Why am I getting a 401 error on this endpoint?”
- “Show me an example request to create a new resource.”

The app retrieves the most relevant documentation snippets and uses an LLM to generate a grounded answer with references.

---

## Features

- **RAG-based Q&A** over your own API docs.
- **REST endpoints** for:
  - Chat: `POST /api/chat/`
  - Doc ingestion: `POST /api/docs/ingest/`
- **Vector search** using PostgreSQL + pgvector.
- **Conversation tracking** (conversation IDs and message history).
- **Dockerized stack**: one command to start app + database.
- **Configurable LLM provider** via environment variables (local Ollama or any OpenAI-compatible cloud API).

For a deeper architectural explanation, see `ARCHITECTURE.md`.

---

## Interview-Ready Explanation — How This Chatbot Works

- **Problem it solves**: Developers and support engineers often struggle to use complex APIs correctly. They jump between docs, examples, and tickets to answer questions like “How do I authenticate?”, “Why am I getting 401?”, or “What does this error code mean?”. This chatbot centralizes that knowledge and answers those questions conversationally.

- **High-level idea**: It is a **RAG (Retrieval-Augmented Generation) system**. Instead of letting the LLM “hallucinate”, it:
  - Stores your API docs as **semantic embeddings** in **PostgreSQL + pgvector**.
  - For each question, retrieves the most relevant chunks.
  - Builds a context-rich prompt and asks the LLM to answer strictly based on that context.

- **Main components (backend only)**:
  - **Django REST API** exposes:
    - `POST /api/docs/ingest/` – ingest raw API docs (titles + content).
    - `POST /api/chat/` – ask questions and get answers plus citations.
  - **Vector store (PostgreSQL + pgvector)** stores:
    - `Document` and `DocumentChunk` rows.
    - A `VectorField` embedding for each chunk so we can do similarity search.
  - **LLM layer (LLMClient + EmbeddingService)**:
    - Talks to an OpenAI-compatible API (Ollama by default) for chat completions and (optionally) embeddings.
  - **RAG pipeline**:
    - Computes embeddings for queries, retrieves the top-k relevant chunks, builds the prompt, calls the LLM, and returns the final answer and sources.

- **Document ingestion flow (interview summary)**:
  1. You send docs either via `POST /api/docs/ingest/` or the `ingest_docs` management command.
  2. The service splits long docs into smaller **chunks**.
  3. Each chunk is turned into an **embedding vector**.
  4. Chunks + embeddings are stored in Postgres with pgvector, ready for similarity search.

- **Question answering flow (interview summary)**:
  1. Client calls `POST /api/chat/` with a natural-language question.
  2. The question is embedded and used to **search similar chunks** in the vector store.
  3. Retrieved chunks are compiled into a **context section** plus the user’s question.
  4. That prompt is sent to the LLM (Ollama / OpenAI-style API).
  5. The chatbot returns:
     - A natural-language **answer** grounded in the docs.
     - **Sources**: which document titles and snippets were used.
     - A `conversation_id` so follow-up questions keep context.

- **Why this design is production-friendly**:
  - Clear separation of concerns (Django views, services, vector store, LLM client).
  - Swappable LLM provider (just change env vars; Ollama or any OpenAI-compatible endpoint).
  - Uses standard infrastructure (PostgreSQL + pgvector) instead of a proprietary vector DB.
  - Exposes a clean REST API that any UI (web, desktop, Postman, support tools) can call.

---

## Tech Stack

- **Backend**: Django 5, Django REST Framework.
- **Database**: PostgreSQL 16 + `pgvector`.
- **Vector embeddings**:
  - Local `sentence-transformers` model (e.g. `BAAI/bge-small-en`) when `EMBEDDING_BACKEND=local`.
  - Or a cloud embeddings endpoint via OpenAI-compatible API.
- **LLM**:
  - OpenAI-compatible chat completions API.
  - In this repo’s default setup, that endpoint is provided by **Ollama** running locally.
- **Containerization**: Docker, docker-compose.
- **Language**: Python 3.11.

---

## Project Structure

At the top level:

- `README.md` – This guide.
- `ARCHITECTURE.md` – High-level and low-level architecture documentation.
- `docker-compose.yml` – Orchestrates Django and PostgreSQL+pgvector.
- `Dockerfile` – Builds the Django service image.
- `env.example` – Example environment variables file.
- `requirements.txt` – Python dependencies.
- `backend/` – Django project and app code.
  - `manage.py`
  - `config/` – Django project settings and URLs.
  - `api_support/` – Main app containing models, services, and API views.

---

## Prerequisites (Local Ollama Setup)

Before you run the project in the **Ollama-based Docker setup**, make sure you have:

- **Docker Desktop** installed and running on your machine (Windows 10+).
- **Docker Compose** (included with modern Docker Desktop).
- **Ollama** installed and running on your host machine.
- (Optional) **Postman** or a similar API client (used below in the examples).

> Note: PostgreSQL runs inside Docker via `docker-compose.yml` (with `pgvector` available through the Python library). You do **not** need a separate local PostgreSQL instance for this setup.

---

## Configuration (.env) for This Project

All configuration is done through environment variables. Start by creating your `.env` file in the project root:

```bash
cd "d:\My Apps\RAG AI Chatbot\api-support-ai-chatbot"
copy env.example .env
```

Open `.env` and set at least:

- **Django**:
  - `DJANGO_SECRET_KEY=your-generated-secret-key`
  - `DJANGO_DEBUG=true`
  - `DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1`
- **Database** (matching `docker-compose.yml`):
  - `DB_NAME=rag_support`
  - `DB_USER=rag_user`
  - `DB_PASSWORD=rag_password`
  - `DB_HOST=db`
  - `DB_PORT=5432`
- **LLM / Embeddings (Ollama + local embeddings)**:
  - `LLM_API_KEY=ollama` (placeholder; Ollama itself does not require a key).
  - `LLM_API_BASE_URL=http://host.docker.internal:11434/v1`
  - `LLM_MODEL_NAME=llama3.2:1b`
  - `EMBEDDING_MODEL_NAME=BAAI/bge-small-en`
  - `EMBEDDING_BACKEND=local`

> **Alternative cloud LLM mode**: If you want to use a cloud provider instead of Ollama, change `LLM_API_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL_NAME`, and `EMBEDDING_MODEL_NAME` to your provider’s values (for example, OpenAI or an OpenAI-compatible proxy). The rest of the architecture stays the same.

---

## RAG AI Chatbot — Run Guide

### Scenario 1 — Running for the First Time (Fresh Setup)

**Prerequisites**

- Docker Desktop installed and running.
- Ollama installed and running.
- Project folder: `D:\My Apps\RAG AI Chatbot\api-support-ai-chatbot`.

**Step 1 — Pull Ollama models** (run in any terminal on your host):

```bash
ollama pull llama3.2:1b
ollama pull nomic-embed-text
```

**Step 2 — Set up `.env` file**

Copy `env.example` to `.env` and fill in the values listed in the **Configuration** section above.

**Step 3 — Build and start containers**

From the project folder terminal:

```bash
cd "D:\My Apps\RAG AI Chatbot\api-support-ai-chatbot"
docker-compose up --build -d
```

**Step 4 — Enable pgvector**

```bash
docker-compose exec db psql -U rag_user -d rag_support -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

**Step 5 — Run migrations**

```bash
docker-compose exec web python manage.py migrate
```

**Step 6 — Copy and ingest sample docs**

Copy the sample docs JSON into the running `web` container:

```bash
docker cp upload_doc/sample_docs.json api-support-ai-chatbot-web-1:/app/sample_docs.json
```

Ingest those docs into the vector store:

```bash
docker-compose exec web python manage.py ingest_docs "AcmePay API" /app/sample_docs.json
```

**Step 7 — Test chat in Postman**

- Method: `POST`
- URL: `http://localhost:8000/api/chat/`
- Headers: `Content-Type: application/json`
- Body (raw JSON):

```json
{
  "query": "How do I authenticate to the AcmePay API?"
}
```

You should receive an answer plus citations to the ingested docs.

---

### Scenario 2 — Starting Again After Shutdown (Daily Use)

Once the containers have been built and migrations/docs have been ingested, daily usage is simpler.

**Step 1 — Open Docker Desktop**

Ensure Docker Desktop is fully running (green icon in the taskbar).

**Step 2 — Start containers**

From the project folder:

```bash
cd "D:\My Apps\RAG AI Chatbot\api-support-ai-chatbot"
docker-compose up -d
```

**Step 3 — Verify containers are running**

```bash
docker ps
```

You should see at least:

- `api-support-ai-chatbot-web-1` – Up
- `api-support-ai-chatbot-db-1` – Up

**Step 4 — Send a chat request**

Use Postman (or curl) to call:

- Method: `POST`
- URL: `http://localhost:8000/api/chat/`
- Headers: `Content-Type: application/json`

Body:

```json
{
  "query": "How do I authenticate to the AcmePay API?"
}
```

That’s it – **no migrations, rebuilds, or re-ingestion are needed** unless you change the schema or docs.

---

### Postman Setup (One Time)

1. Open Postman → **New** → **HTTP Request**.
2. Set method to **POST**.
3. Set URL to `http://localhost:8000/api/chat/`.
4. Click **Body** → **raw** → select **JSON**.
5. Paste a payload such as:

```json
{
  "query": "your question here"
}
```

6. Click **Send**.
7. Save this request into a **Collection** so you can reuse it for future testing.

---

## Using the API Support Chatbot

### Step 1: Ingest API Documentation

You must ingest some API docs before the chatbot can answer questions usefully.

#### Option A: Ingest via REST API

Send a `POST` request to `http://localhost:8000/api/docs/ingest/`:

```bash
curl -X POST http://localhost:8000/api/docs/ingest/ ^
  -H "Content-Type: application/json" ^
  -d "{
    \"source_name\": \"Sample Payments API\",
    \"docs\": [
      {
        \"title\": \"Authentication\",
        \"content\": \"To authenticate, send your API key in the Authorization header as a Bearer token...\"
      },
      {
        \"title\": \"Create Charge\",
        \"content\": \"To create a charge, POST /charges with fields amount, currency, and source...\"
      }
    ]
  }"
```

Example JSON body:

```json
{
  "source_name": "Sample Payments API",
  "docs": [
    {
      "title": "Authentication",
      "content": "To authenticate, send your API key in the Authorization header as a Bearer token..."
    },
    {
      "title": "Create Charge",
      "content": "To create a charge, POST /charges with fields amount, currency, and source..."
    }
  ]
}
```

The response will look like:

```json
{
  "summaries": [
    { "document_id": 1, "chunks_created": 1 },
    { "document_id": 2, "chunks_created": 1 }
  ]
}
```

#### Option B: Ingest via Management Command

1. Create a JSON file, e.g. `docs.json`:

```json
[
  { "title": "Authentication", "content": "To authenticate, send your API key..." },
  { "title": "Errors", "content": "Common error codes are 400, 401, 403..." }
]
```

2. Run the management command inside the `web` container:

```bash
docker-compose exec web python manage.py ingest_docs "My API Docs" /app/backend/docs.json
```

> Note: Make sure `docs.json` is available inside the container (e.g. by mounting a volume or copying it into `backend/` and rebuilding).

---

### Step 2: Ask Questions (Chat Endpoint)

Once docs are ingested, you can query the chatbot.

#### Basic Question

```bash
curl -X POST http://localhost:8000/api/chat/ ^
  -H "Content-Type: application/json" ^
  -d "{
    \"query\": \"How do I authenticate to this API?\"
  }"
```

Example response:

```json
{
  "answer": "To authenticate, include your API key in the Authorization header as a Bearer token...",
  "sources": [
    {
      "document_id": 1,
      "document_title": "Authentication",
      "chunk_index": 0,
      "snippet": "To authenticate, send your API key..."
    }
  ],
  "conversation_id": 1
}
```

#### Follow-up Question (Conversation Continuation)

Use the `conversation_id` from the previous response:

```bash
curl -X POST http://localhost:8000/api/chat/ ^
  -H "Content-Type: application/json" ^
  -d "{
    \"query\": \"Can you show me a sample curl command?\",
    \"conversation_id\": 1
  }"
```

The chatbot will take previous messages into account when forming its reply.

---

## Typical Problem-Solving Scenarios

Here are some concrete examples of how this chatbot can help you use APIs correctly:

- **“I keep getting 401 Unauthorized.”**
  - You paste your request and the error.
  - The chatbot checks the authentication section in your docs and explains:
    - Whether your header format is wrong.
    - If you are missing required scopes or tokens.
    - How to correct your curl command or code.
- **“How do I create a new order?”**
  - The chatbot retrieves docs on the “Create Order” endpoint:
    - Returns the correct URL, HTTP method, and required fields.
    - Provides a step-by-step example request.
- **“What does error code 422 mean in this API?”**
  - The chatbot finds the error handling documentation:
    - Explains the meaning of 422 for this specific API.
    - Suggests how to fix common validation issues.

In all cases, the response includes **sources** so you can see exactly which part of your docs were used.

---

## Local Development Without Docker (Optional)

You can also run the project directly on your host if you prefer:

1. Create and activate a virtual environment:

```bash
cd "d:\My Apps\RAG AI Chatbot\api-support-ai-chatbot"
python -m venv .venv
.venv\Scripts\activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Ensure PostgreSQL is running and accessible, and your `.env` points to it (adjust `DB_HOST`, `DB_PORT`).

4. Apply migrations:

```bash
cd backend
python manage.py migrate
```

5. Run the server:

```bash
python manage.py runserver
```

The API will be available at `http://localhost:8000/` just like in the Docker setup.

---

## Tools and Libraries Explained

- **Django**: Provides the web framework, ORM, and admin panel.
- **Django REST Framework**: Simplifies building JSON-based APIs with serializers and API views.
- **PostgreSQL**: Relational database that stores documents, chunks, and chat history.
- **pgvector**:
  - Adds a `VectorField` type to Django models to store embeddings.
  - Provides functions (like `CosineDistance`) to search for similar vectors.
  - This is how we implement semantic search for relevant documentation chunks.
- **Cloud LLM (OpenAI-compatible)**:
  - **Embeddings**: Transform text into numerical vectors, so similar texts are close in vector space.
  - **Chat Completions**: Generate natural language answers based on a prompt that includes retrieved context.
- **Docker / docker-compose**:
  - Encapsulate the Python environment and database.
  - Ensure consistency between machines (no “works on my machine” issues).

---

## How to Extend This Project

- **Add a simple web UI**:
  - Create a small single-page app or template that calls the `/api/chat/` endpoint.
- **Integrate with support tools**:
  - Build a Slack bot or internal web widget that forwards questions to the API.
- **Improve retrieval quality**:
  - Replace the simple chunker with a tokenizer-aware chunker.
  - Use metadata filters in the vector search (e.g. filter by API version or product).
- **Change LLM provider**:
  - Update environment variables to point to a different OpenAI-compatible API.
  - Or rewrite `EmbeddingService` and `LLMClient` to target a new provider.

---

## Troubleshooting

- **Docker container fails to connect to database**:
  - Make sure `db` service is running and healthy.
  - Confirm `DB_HOST=db` and `DB_PORT=5432` in `.env`.
- **LLM calls failing (401, 429, etc.)**:
  - Check `LLM_API_KEY` and `LLM_API_BASE_URL`.
  - Check provider dashboard for quota/rate limits.
- **No useful answers / “I don’t know”**:
  - Ensure you have ingested relevant documentation.
  - Check that embeddings calls succeed (no errors in logs).
  - Consider adding more detailed examples and error reference docs.

If you want, we can next add a small HTML/JS chat frontend or additional tooling specific to your APIs. For now, you have a complete RAG backend that you can start using and experimenting with via REST.

