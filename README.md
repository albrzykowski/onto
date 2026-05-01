# on:to

Production-ready pipeline to create ontology from documents.

![Ruff](https://github.com/albrzykowski/onto/actions/workflows/lint.yml/badge.svg)
![Tests](https://github.com/albrzykowski/onto/actions/workflows/tests.yml/badge.svg)

## What is this?

on:to is a document processing pipeline that extracts structured ontology from text documents. It uses:

- **Apache Pulsar** - Message queue for async processing

## Quick Start (Docker)

Everything runs in Docker - no Python setup required:

```bash
# 1. Create .env with your API key
echo "OPENAI_API_KEY=your-key" > .env

# 2. Start all services (Pulsar, Consumer, API)
docker compose up -d

# 3. Send a document
curl -X POST http://localhost:8000/documents \
  -H "Content-Type: application/json" \
  -d '{"tenant_id": "my-tenant", "content": "John works at Acme Corp."}'
```

The docker-compose includes:
- `pulsar` - Message queue
- `consumer` - Background worker (logs messages)
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
| `PULSAR_URL`       | No       | `pulsar://localhost:6650`      | Pulsar broker URL               |
| `PULSAR_ADMIN`     | No       | `http://localhost:8080`       | Pulsar admin URL              |
| `TOPIC_PREFIX`     | No       | `persistent://public/default` | Topic prefix for tenants       |
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
  "status": "accepted",
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
  "status": "accepted",
  "tenant_id": "tenant-abc"
}
```

**Error Responses:**
- `400` - Invalid request body
- `422` - Validation error
- `503` - Pulsar not ready

## How It Works

1. **Producer** sends documents to Pulsar topic per tenant
2. **Consumer** reads messages and logs them to console

## Docker Networking

When running in Docker (via `docker-compose.dev.yml`), services use `host.docker.internal` to connect to Pulsar instead of container names. This is because the Pulsar container may not be reachable by hostname from other containers in certain Docker configurations. The `extra_hosts` directive maps `host.docker.internal` to the host gateway, allowing containers to access Pulsar on `localhost:6650` and `localhost:8080`.

## Testing

### Unit Tests
```bash
pytest tests/unit/ -v
ruff check app/
```

### BDD Tests
Each scenario runs on a fresh Docker environment (clean after every scenario, start before every scenario).

**Prerequisites:** `pip install behave`

```bash
# 1. Run tests - environment.py automatically handles cleanup/start
behave tests/bdd/features/ | tee /dev/null

# 2. Verify pass: check exit code (should be 0) and output shows "X scenarios passed, 0 failed"
echo $?
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
│   └── consumer.py        # Pulsar consumer (logs messages)
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
