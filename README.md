# on:to

Production-ready pipeline to create ontology from documents. Submit jobs via REST API, processed asynchronously with Apache Pulsar. Features retry logic, dynamic topic discovery, health checks, and input validation.

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

## Tests

```bash
# Unit tests (no external deps required)
pytest tests/ -v        # 18 unit tests

# E2E tests (requires Pulsar + API running)
pytest tests_e2e/ -v    # 7 e2e
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
