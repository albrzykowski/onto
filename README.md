# on:to

Production-ready pipeline to create ontology from documents.

![Ruff](https://github.com/albrzykowski/onto/actions/workflows/lint.yml/badge.svg)
![Tests](https://github.com/albrzykowski/onto/actions/workflows/tests.yml/badge.svg)

## What is this?

on:to is a document processing pipeline that extracts structured ontology from text documents. It uses:

- **Apache Pulsar** - Message queue for async processing
- **Qdrant** - Vector database for semantic search & entity resolution
- **PostgreSQL** - Persistent storage for resolved entities
- **LLM** - OpenAI-compatible API for ontology extraction

## Quick Start (Docker)

Everything runs in Docker - no Python setup required:

```bash
# 1. Create .env with your API key
echo "OPENAI_API_KEY=your-key" > .env

# 2. Start all services (Pulsar, Qdrant, PostgreSQL, Consumer, API)
docker compose up -d

# 3. Send a document
curl -X POST http://localhost:8000/documents \
  -H "Content-Type: application/json" \
  -d '{"tenant_id": "my-tenant", "content": "John works at Acme Corp."}'
```

The docker-compose includes:
- `pulsar` - Message queue
- `qdrant` - Vector database  
- `postgres` - PostgreSQL
- `consumer` - Background worker (processes messages)
- `api` - HTTP API server

## Quick Start (Local Development)

For development with hot-reload:

```bash
# 1. Start infrastructure only (Pulsar, Qdrant, PostgreSQL)
docker compose -f docker-compose.dev.yml up -d pulsar qdrant postgres

# 2. Install Python deps
pip install -r requirements.txt

# 3. Create .env with your API key
echo "OPENAI_API_KEY=your-key" > .env

# 4. Run consumer and API
python -m app.queue.consumer &
python -m app.main
```

## Setup

### Prerequisites

- Python 3.10+
- Docker & Docker Compose
- OpenAI API key (or compatible LLM)

### Installation

```bash
pip install -r requirements.txt
```

### Environment Variables

| Variable            | Required | Default                       | Description                    |
|--------------------|----------|-------------------------------|--------------------------------|
| `OPENAI_API_KEY`    | Yes      | -                             | API key for LLM                  |
| `OPENAI_BASE_URL`  | No       | `https://api.openai.com/v1`    | Custom LLM endpoint           |
| `OPENAI_MODEL`     | No       | `gpt-4o-mini`                 | Model name                     |
| `PULSAR_URL`       | No       | `pulsar://localhost:6650`      | Pulsar broker URL               |
| `PULSAR_ADMIN`     | No       | `http://localhost:8080`       | Pulsar admin URL              |
| `TOPIC_PREFIX`     | No       | `persistent://public/default` | Topic prefix for tenants       |
| `QDRANT_HOST`      | No       | `localhost`                   | Qdrant host                   |
| `QDRANT_PORT`      | No       | `6333`                        | Qdrant port                   |
| `POSTGRES_HOST`    | No       | `localhost`                   | PostgreSQL host               |
| `POSTGRES_PORT`    | No       | `5432`                        | PostgreSQL port               |
| `POSTGRES_USER`    | No       | `postgres`                    | PostgreSQL user              |
| `POSTGRES_PASSWORD`| No       | `postgres`                    | PostgreSQL password          |
| `POSTGRES_DB`      | No       | `onto`                        | Database name                |
| `HOST`             | No       | `0.0.0.0`                     | API server host               |
| `PORT`             | No       | `8000`                        | API server port              |

## Usage

### Docker (Production)

```bash
# Start all services
docker compose up -d

# View logs
docker compose logs -f

# Stop
docker compose down
```

### Local Development

```bash
# Start infrastructure only
docker compose -f docker-compose.dev.yml up -d pulsar qdrant postgres

# Set your API key
export OPENAI_API_KEY="sk-..."

# Start the consumer (worker that processes messages)
python -m app.queue.consumer &

# Start the API server
python -m app.main
```

### Sending Documents

Send documents to the pipeline via the API:

```bash
curl -X POST http://localhost:8000/documents \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_id": "my-tenant",
    "content": "John works at Acme Corp as a software engineer."
  }'
```

Response:
```json
{
  "job_id": "abc-123",
  "status": "queued",
  "tenant_id": "my-tenant"
}
```

### Checking Status

```bash
# Health check
curl http://localhost:8000/health

# Readiness check
curl http://localhost:8000/ready
```

## API Endpoints

| Method   | Endpoint         | Description                      |
|----------|------------------|----------------------------------|
| `GET`    | `/health`        | Liveness probe                   |
| `GET`    | `/ready`         | Readiness probe (Pulsar check)   |
| `POST`   | `/documents`     | Submit document for processing   |

### POST /documents

Submit a document for ontology extraction.

**Request:**
```json
{
  "tenant_id": "tenant-abc",
  "content": "Your text content here..."
}
```

**Response:**
```json
{
  "job_id": "job-xyz",
  "status": "queued",
  "tenant_id": "tenant-abc"
}
```

**Error Responses:**
- `400` - Invalid request body
- `422` - Validation error
- `503` - Pulsar not ready

## How It Works

1. **Producer** sends documents to Pulsar topic per tenant
2. **Consumer** reads messages and processes them
3. **LLMProcessor** extracts ontology entities using LLM
4. **EntityResolver** performs hybrid deduplication:
   - Embeds extracted entities in Qdrant
   - Searches for similar existing entities
   - Merges if confidence ≥ 0.85
   - Creates new entity if no match
5. **PostgreSQL** stores resolved entities

## Testing

```bash
# Run unit tests
pytest tests/ -v

# Run BDD tests (requires services)
docker-compose -f docker-compose.dev.yml up -d
behave tests/bdd/features/
docker-compose -f docker-compose.dev.yml down
```

## Project Structure

```
app/
├── api/
│   └── routes.py          # FastAPI routes
├── jobs/
│   └── store.py           # Job status tracking
├── queue/
│   ├── producer.py        # Pulsar producer
│   └── consumer.py        # Pulsar consumer
├── pipeline/
│   └── llm_processor.py  # LLM processing
├── resolver/
│   ├── entity_resolver.py # Entity resolution
│   ├── entity_retrieval.py # Entity retrieval
│   ├── qdrant_client.py   # Qdrant client
│   ├── postgres_repo.py   # PostgreSQL repo
│   └── models.py          # Data models
├── schemas/
│   └── document.py        # Request schemas
├── config.py              # Configuration
├── logger.py              # Logging
└── main.py                # App entrypoint

tests/
├── unit/                  # Unit tests
└── bdd/
    └── features/          # BDD test scenarios
```

## Features

- Retry logic on send failure
- Dynamic topic discovery
- Configurable Pulsar admin URL
- Custom topic prefix support
- Graceful shutdown
- Health checks
- Input validation
- Entity resolution with Qdrant + PostgreSQL
- Hybrid deduplication (confidence ≥ 0.85 → merge)
