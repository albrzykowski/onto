# AGENTS.md

## Commands

```bash
# Run unit and BDD tests
pytest tests/ -v

# Run lint
ruff check app/
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

## Local Dev Environment

```bash
# Start all services
docker-compose -f docker-compose.dev.yml up -d

# Stop and cleanup
docker-compose -f docker-compose.dev.yml down --remove-orphans -v
```

## Environment

| Variable | Default |
|----------|---------|
| PULSAR_URL | pulsar://localhost:6650 |
| PULSAR_ADMIN | http://localhost:8080 |
| TOPIC_PREFIX | persistent://public/default |
| HOST | 0.0.0.0 |
| PORT | 8000 |

## Testing
### Unit Tests
```bash
pytest tests/unit/ -v
ruff check app/
```

### BDD Tests
Each scenario runs on a fresh Docker environment (clean after every scenario, start before every scenario).
```bash
# 1. Run tests - environment.py automatically handles cleanup/start
behave tests/bdd/features/ | tee /dev/null
```

## Test Conventions

- Always use #Given #When #Then comments in tests
- Example:
  ```python
  def test_example():

      # Given (no additional comments here)
      ...

      # When (no additional comments here)
      ...

      # Then (no additional comments here)
      ...
  ```

## Notes

- mypy configured for Python 3.10 but runs on 3.14 locally (compatibility OK)
- Ruff pylint rules enforce strict complexity (max-branches=5, max-locals=5, etc.)

## Interaction Rules

- When asked a question, answer first before making any code changes
- Ask for confirmation before modifying code or committing
- Example: "It's duplicate in README. Want me to remove it?"