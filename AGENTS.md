# AGENTS.md

## Commands

```bash
# Run all tests and lint
pytest tests/ tests_e2e/ -v && ruff check app/
```

**Always run these after code changes to verify correctness.**

## Commit Messages

Follow Conventional Commits format:
```
<type>: <description>

Types: feat, fix, test, refactor, docs, chore, style, perf, ci, build, revert
```

Examples:
- `feat: add new endpoint for documents`
- `fix: resolve API key not loading`
- `test: add unit tests for LLMProcessor`
- `docs: update README with setup instructions`
- `chore: add pytest-asyncio dependency`

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