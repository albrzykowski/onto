# Job Queue Service

Minimal job queue with FastAPI + Pulsar.

## Quick Start

```bash
# Start Pulsar
docker run -d --name pulsar -p 6650:6650 -p 8080:8080 apachepulsar/pulsar:3.1.0 bin/pulsar standalone

# Run
python -m app.queue.consumer &
python -m app.main
```

## API

| Endpoint | Description |
|----------|-------------|
| `GET /health` | Liveness |
| `GET /ready` | Pulsar ready |
| `POST /jobs` | Create job |

```bash
curl -X POST http://localhost:8000/jobs \
  -H "Content-Type: application/json" \
  -d '{"tenant_id": "my-tenant", "payload": {"task": "process"}}'
```

## Config (env)

| Variable | Default |
|----------|---------|
| `PULSAR_URL` | `pulsar://localhost:6650` |
| `PULSAR_ADMIN` | `http://localhost:8080` |
| `TOPIC_PREFIX` | `persistent://public/default` |
| `HOST` | `0.0.0.0` |
| `PORT` | `8000` |
| `LOG_LEVEL` | `INFO` |

## Tests

```bash
pytest tests/ -v        # 15 unit tests
pytest tests_e2e/ -v    # 5 e2e (auto-skips if no server)
```

## Structure

```
app/
├── queue/
│   ├── producer.py  # Producer class
│   └── consumer.py  # Consumer class
├── api/routes.py
├── schemas/job.py
├── config.py
└── main.py
```

## Features

- Auto job ID (UUID) for idempotency
- Retry logic on send failure
- Dynamic topic discovery
- Configurable Pulsar admin URL
- Custom topic prefix support
- Graceful shutdown
- Health checks
- Input validation