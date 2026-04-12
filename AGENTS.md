# AGENTS.md

## Commands

```bash
# Run unit tests only (no external deps required)
pytest tests/ -v

# Run all tests and lint
pytest tests/ -v && pytest tests_e2e/ -v -m e2e && ruff check app/
```

**Always run these after code changes to verify correctness.**

## Commit Messages

Follow Conventional Commits format:
```
<type>: <description>

Types: feat, feat!, fix, test, refactor, docs, chore, style, perf, ci, build, revert
```

Examples:
- `feat: add new endpoint for documents`
- `feat!: rename REST API endpoint for documents creation`
- `fix: resolve API key not loading`
- `test: add unit tests for LLMProcessor`
- `docs: update README with setup instructions`
- `chore: add pytest-asyncio dependency`

## Run Order

Consumer must start before API (or concurrently): `python -m app.queue.consumer & python -m app.main`

## E2E Environment

```bash
# Start all E2E services (Pulsar, Qdrant, PostgreSQL, API)
docker-compose -f docker-compose.e2e.yml up -d

# Run E2E tests
pytest tests_e2e/ -v -m e2e

# Stop E2E services
docker-compose -f docker-compose.e2e.yml down
```

## Environment

| Variable | Default |
|----------|---------|
| PULSAR_URL | pulsar://localhost:6650 |
| PULSAR_ADMIN | http://localhost:8080 |
| TOPIC_PREFIX | persistent://public/default |
| HOST | 0.0.0.0 |
| PORT | 8000 |
| QDRANT_HOST | localhost |
| QDRANT_PORT | 6333 |
| POSTGRES_HOST | localhost |
| POSTGRES_PORT | 5432 |
| POSTGRES_USER | postgres |
| POSTGRES_PASSWORD | postgres |
| POSTGRES_DB | onto |

## Testing

- E2E tests exist in `tests_e2e/` (requires server running)
- Use marker `@pytest.mark.e2e` for end-to-end tests

## Test Conventions

- Always use #Given #When #Then comments in tests
- Example:
  ```python
  def test_example():
      # Given
      ...
      # When
      ...
      # Then
      ...
  ```

## Notes

- mypy configured for Python 3.10 but runs on 3.14 locally (compatibility OK)
- Ruff pylint rules enforce strict complexity (max-branches=5, max-locals=5, etc.)

## Interaction Rules

- When asked a question, answer first before making any code changes
- Ask for confirmation before modifying code or committing
- Example: "It's duplicate in README. Want me to remove it?"