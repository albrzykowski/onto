# AGENTS.md

## Commands

```bash
# Lint
ruff check app/

# Typecheck
mypy app/

# Unit tests
pytest tests/ -v

# E2E tests (requires services)
pytest tests_e2e/ -v
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
- API: `app/api/routes.py` (POST /documents, GET /health, GET /ready)
- Queue: `app/queue/producer.py`, `app/queue/consumer.py`
- Pipeline: `app/pipeline/llm_processor.py`
- Config: `app/config.py`

## Testing

- E2E tests exist in `tests_e2e/` (requires server running)
- Use marker `@pytest.mark.e2e` for end-to-end tests

## Notes

- mypy configured for Python 3.10 but runs on 3.14 locally (compatibility OK)
- Ruff pylint rules enforce strict complexity (max-branches=5, max-locals=5, etc.)