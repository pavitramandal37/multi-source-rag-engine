## RAG API Support Chatbot

### Overview

This project is a **Retrieval-Augmented Generation (RAG) API Support Chatbot** built with:

- **Django + Django REST Framework** for the HTTP API.
- **PostgreSQL + pgvector** as the vector database for semantic search.
- A **cloud LLM** (OpenAI-compatible API) for embeddings and answer generation.
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
- **Configurable LLM provider** via environment variables (OpenAI-compatible).

For a deeper architectural explanation, see `ARCHITECTURE.md`.

---

## Tech Stack

- **Backend**: Django 5, Django REST Framework.
- **Database**: PostgreSQL 16 + `pgvector`.
- **Vector embeddings**: Cloud LLM embeddings endpoint.
- **LLM**: OpenAI-compatible chat completions API.
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

## Prerequisites

Before you run the project, make sure you have:

- **Docker Desktop** installed and running on your machine (Windows 10+).
- **Docker Compose** (included with modern Docker Desktop).
- A valid **LLM API key** (for an OpenAI-compatible API), for example:
  - OpenAI account with an API key.
  - Or a compatible proxy/host that exposes `chat/completions` and `embeddings` endpoints.

> Note: You mentioned PostgreSQL is already installed on your system. This project uses a **Dockerized PostgreSQL** by default (with pgvector extension via Python library). You don’t need to configure your local PostgreSQL unless you specifically want to connect to it instead of the container.

---

## Configuration

All configuration is done through environment variables. Start by creating your `.env` file:

```bash
cd "d:\My Apps\RAG AI Chatbot\API Support"
copy env.example .env
```

Open `.env` and set at least:

- **Django**:
  - `DJANGO_SECRET_KEY` – set to a random string in production.
  - `DJANGO_DEBUG` – `true` for local development; `false` in production.
  - `DJANGO_ALLOWED_HOSTS` – comma-separated hostnames (for dev, `localhost,127.0.0.1` is fine).
- **Database**:
  - `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`.
  - Defaults are fine when using `docker-compose.yml` as-is.
- **LLM / OpenAI-compatible API**:
  - `LLM_API_KEY` – your API key.
  - `LLM_API_BASE_URL` – typically `https://api.openai.com/v1` or your provider’s base URL.
  - `LLM_MODEL_NAME` – e.g. `gpt-4.1-mini`.
  - `EMBEDDING_MODEL_NAME` – e.g. `text-embedding-3-small`.

---

## Running the Project with Docker (Recommended)

### 1. Build the images

From the project root (`d:\My Apps\RAG AI Chatbot\API Support`):

```bash
docker-compose build
```

This will:

- Build the `web` image using the `Dockerfile` (installs Python dependencies).
- Pull the `postgres:16` image for the `db` service.

### 2. Start the services

```bash
docker-compose up
```

This will:

- Start the `db` service (PostgreSQL).
- Start the `web` service (Django) on port `8000`.

You should see Django starting up in the logs. Once it is ready, the API will be accessible at:

- `http://localhost:8000/`
- Chat endpoint: `http://localhost:8000/api/chat/`
- Ingestion endpoint: `http://localhost:8000/api/docs/ingest/`

### 3. Apply migrations

In a separate terminal, run:

```bash
docker-compose exec web python manage.py migrate
```

This creates the required tables in the PostgreSQL database, including the ones used for documents, chunks, and conversations.

> Optionally, create an admin superuser for the Django admin:
>
> ```bash
> docker-compose exec web python manage.py createsuperuser
> ```

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
cd "d:\My Apps\RAG AI Chatbot\API Support"
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

