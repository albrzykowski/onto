# Job Queue Service

A minimal, production-ready job queue system using FastAPI and Apache Pulsar.

## What it does

```
POST /jobs → Pulsar → Consumer → Process job
```

- Accepts job requests via HTTP POST
- Publishes to tenant-specific Pulsar topics
- Consumer dynamically discovers and processes all topics

## Quick Start

```bash
# Start Pulsar
docker run -d --name pulsar -p 6650:6650 -p 8080:8080 apachepulsar/pulsar:3.1.0 bin/pulsar standalone

# Install dependencies
pip install -r requirements.txt

# Run
python -m app.consumer &   # Job processor
python -m app.main          # API server
```

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /health` | Liveness check |
| `GET /ready` | Readiness (Pulsar connection) |
| `POST /jobs` | Create job |

## Example

```bash
curl -X POST http://localhost:8000/jobs \
  -H "Content-Type: application/json" \
  -d '{"tenant_id": "my-tenant", "payload": {"task": "process"}}'
```

Response:
```json
{"status": "accepted", "tenant_id": "my-tenant"}
```

## Configuration

Environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `PULSAR_URL` | `pulsar://localhost:6650` | Pulsar broker URL |
| `HOST` | `0.0.0.0` | Server host |
| `PORT` | `8000` | Server port |
| `LOG_LEVEL` | `INFO` | Logging level |

## Testing

```bash
pytest tests/ -v
```

- Unit tests: 17 (consumer, producer, routes)
- E2E tests: 5 (requires running server + Pulsar)

## Architecture

```
app/
├── api/routes.py      # FastAPI endpoints
├── consumer.py        # Pulsar consumer (17 lines)
├── queue/producer.py  # Pulsar producer (44 lines)
├── schemas/job.py    # Pydantic models
├── config.py         # Configuration
└── logger.py         # Logging setup

tests/
├── test_consumer.py
├── test_producer.py
├── test_routes.py
└── e2e_test.py
```

## Features

- Auto-generated job IDs (UUID) for idempotency
- Retry logic on send failure
- Dynamic topic discovery every 5 seconds
- Graceful shutdown
- Health/readiness checks
- Input validation

## Requirements

- Python 3.10+
- Pulsar broker