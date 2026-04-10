# AGENTS.md

## Commands

```bash
# Lint
ruff check app/

# Typecheck
mypy app/

# Test (15 unit tests)
pytest tests/ -v

# Run (requires Pulsar running)
docker-compose up -d  # or: docker run -d --name pulsar -p 6650:6650 -p 8080:8080 apachepulsar/pulsar:3.1.0 bin/pulsar standalone
python -m app.main
```

## Run Order

Consumer must start before API (or concurrently): `python -m app.queue.consumer & python -m app.main`

## Environment

| Variable | Default |
|----------|---------|
| PULSAR_URL | pulsar://localhost:6650 |
| PULSAR_ADMIN | http://localhost:8080 |
| TOPIC_PREFIX | persistent://public/default |
| HOST | 0.0.0.0 |
| PORT | 8000 |

## Architecture

- Entry: `app/main.py` (FastAPI app)
- API: `app/api/routes.py` (POST /jobs, GET /health, GET /ready)
- Queue: `app/queue/producer.py`, `app/queue/consumer.py`
- Config: `app/config.py`

## Testing

- E2E tests exist in `tests_e2e/` (auto-skips if no server)
- Use marker `@pytest.mark.e2e` for end-to-end tests

## Notes

- mypy configured for Python 3.10 but runs on 3.14 locally (compatibility OK)
- Ruff pylint rules enforce strict complexity (max-branches=5, max-locals=5, etc.)