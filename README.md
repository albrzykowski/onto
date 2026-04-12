# on:to

Production-ready pipeline to create ontology from documents.

![Ruff](https://github.com/albrzykowski/onto/actions/workflows/lint.yml/badge.svg)
![Tests](https://github.com/albrzykowski/onto/actions/workflows/tests.yml/badge.svg)

## Quick Start

```bash
# Start Pulsar
docker run -d --name pulsar -p 6650:6650 -p 8080:8080 apachepulsar/pulsar:3.1.0 bin/pulsar standalone

# Run
python -m app.queue.consumer &
python -m app.main
```

## API

| Endpoint         | Description      |
|-----------------|------------------|
| `GET /health`   | Liveness         |
| `GET /ready`    | Pulsar ready      |
| `POST /documents` | Create document |

```bash
curl -X POST http://localhost:8000/documents \
  -H "Content-Type: application/json" \
  -d '{"tenant_id": "my-tenant", "content": "text content here"}'
```

## Config (env)

| Variable       | Default                       |
|----------------|-------------------------------|
| `PULSAR_URL`   | `pulsar://localhost:6650`     |
| `PULSAR_ADMIN` | `http://localhost:8080`       |
| `TOPIC_PREFIX` | `persistent://public/default` |
| `HOST`         | `0.0.0.0`                     |
| `PORT`         | `8000`                        |
| `LOG_LEVEL`    | `INFO`                        |
| `QDRANT_HOST`  | `localhost`                  |
| `QDRANT_PORT`  | `6333`                       |
| `POSTGRES_HOST`| `localhost`                  |
| `POSTGRES_PORT`| `5432`                       |
| `POSTGRES_USER`| `postgres`                   |
| `POSTGRES_PASSWORD`| `postgres`                 |
| `POSTGRES_DB`  | `onto`                       |

## Tests

```bash
# Unit tests (no external deps required)
pytest tests/ -v        # 32 unit tests

# E2E tests (requires Pulsar + API running)
pytest tests_e2e/ -v -m e2e    # 10 e2e
```

### E2E Test Environment

Start services manually:
```bash
# Option 1: Docker
docker run -d --name pulsar -p 6650:6650 -p 8080:8080 apachepulsar/pulsar:3.1.0
python -m app.queue.consumer &
python -m app.main

# Option 2: docker-compose (if available)
docker compose -f docker-compose.e2e.yml up -d
pytest tests_e2e/ -v
docker compose -f docker-compose.e2e.yml down
```

## Structure

```
app/
├── queue/
│   ├── producer.py  # Producer class
│   └── consumer.py  # Consumer class
├── api/routes.py
├── pipeline/
│   └── llm_processor.py  # LLMProcessor class
├── resolver/
│   ├── entity_resolver.py  # Entity resolution logic
│   ├── qdrant_client.py   # Qdrant wrapper
│   ├── postgres_repo.py    # PostgreSQL repository
│   └── models.py          # Data models
├── schemas/document.py
├── config.py
└── main.py
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
