# AGENTS.md — Instructions for the coding agent

This file defines the working rules for the agent building the **Auto Ontology Builder** project (Python, LinkML, Anthropic LLM API). The agent works in an **ATDD (Acceptance Test-Driven Development)** cycle.

## 🔄 Working cycle (ATDD) — mandatory

For **each** feature file in `features/`, in alphabetical order or per the dependency order below:

1. **Read the feature** — the `.feature` (Gherkin) file and any related step definitions (`features/steps/`).
2. **Run the tests** — all scenarios in that feature fail because the steps are not implemented.
3. **Implement the steps** — add step definitions in `features/steps/*.py` (pytest-bdd). Run the tests — they still fail because the production code is missing.
4. **Implement the solution** — the minimal code in the `onto` package that satisfies the scenarios. Run the tests — **they must pass**.
5. **Refactor** — improve naming, remove duplication, extract modules. **Run the tests again — they must pass.** Never refactor in a way that breaks or skips tests.

Forbidden: implementing a feature without running tests, writing speculative production code, editing `.feature` files to make tests easier.
NEVER Edit `.feature` files!

## 📦 Feature dependencies (implementation order)

```
config-loading → document-ingestion → chunking → llm-extraction
                                              → tbox-generation → abox-generation
                                              → provenance-logging
                            update-mode (requires: tbox + abox + provenance)
                            override-mode (requires: tbox + abox)
                            cli (last)
```

## 🏗️ Project structure

```
onto/
├── __init__.py
├── config.py          # BuilderConfig (pydantic), YAML loading, validation
├── ingestion.py       # txt/md/pdf/docx loading, fingerprinting
├── chunking.py        # fixed/semantic chunking
├── llm.py             # provider-neutral LLM contract (CompletionRequest, LLM, LLMError)
├── extraction.py      # LLM calls, prompts, batching
├── schema_gen.py      # T-Box — LinkML schema generation
├── instance_gen.py    # A-Box — LinkML instance generation
├── dedup.py           # embeddings, similarity threshold, LLM verification
├── provenance.py      # JSONL event log
├── builder.py         # orchestration: override/update
└── cli.py             # typer CLI (`onto build`, `onto update`)
features/
├── *.feature
└── steps/
```

## 🎯 Engineering principles

- **KISS, YAGNI, DRY.** Minimalism and reusability first. No abstractions, options, or configuration knobs beyond what the features require. When two pieces of code repeat, extract; when a rule exists once, don't generalize it.
- Python 3.11+, full type hints, `pydantic` v2.
- All code, identifiers, and comments in **English**. Class names `PascalCase`, relations/slots `snake_case`.

### 💬 Code style — self-documenting, comments as a last resort

**The code must explain itself through naming, structure and types. Inline comments are not allowed by default.**

Add a comment only in a genuinely important situation, when the code *cannot* express the reason by itself:

1. **A non-obvious invariant or guard** — why this bound, and what breaks past it.
2. **A deliberate workaround** — what is being worked around, plus the condition for removing it.
3. **A decision that contradicts the obvious reading** and that the next reader would otherwise "fix" by mistake.

Forbidden:

- restating what the code already says (`# increment i`, `# return the chunks`);
- section banners, decorative separators, and numbered narration of the flow;
- commented-out code — delete it, git remembers it;
- `TODO`/`FIXME` left in production code — either fix it or open an issue.

**Prefer a docstring over a comment** whenever the note describes the whole function, class or module. A docstring states the contract (what it does, what it returns, what it raises); a comment explains one specific line. If you cannot decide which one fits, it is a docstring.

Examples of what is allowed:

```python
# a zero-length window would never advance -> infinite loop
if not 0 <= overlap < size:
    raise ChunkError(...)


def _load_docx(path: Path) -> str:
    """Extract paragraph text; tables and headers are not part of the model."""
```

Examples of what is not:

```python
# Load the document
# Loop over the chunks
# if it's a pdf
# return the result
```

When a comment is genuinely warranted, write *why*, never *what*.

## 🤖 LLM prompt scoping — three modes

The extraction prompt is built from the configuration with exactly three scoping levels:

1. `allowed_classes` / `allowed_relations` **and** domains set → the prompt instructs the LLM to use **only** the predefined concepts. For prompt-efficiency, the LLM must never propose anything outside the allow-lists.
2. Domains (with their descriptions) set, no allow-lists → the prompt instructs the LLM to extract whatever concepts are relevant **within those domains**. A `domains: [automotive]` prompt must never yield `Recipe`.
3. Neither domains nor allow-lists → the LLM decides which concepts and relations are significant on its own.

Domain descriptions from `config.yaml` are always injected into the prompt when domains are set.

## 🧪 Testing

**Always use the virtual environment `.venv` for all operations.**

Run all tests:
```bash
source .venv/bin/activate
pytest features/ -v
```

Run tests for a specific feature:
```bash
source .venv/bin/activate
pytest features/test_<feature_name>.py -v
```

Lint and type-check (both configured in `pyproject.toml`, dev-only):
```bash
source .venv/bin/activate
ruff check .
mypy onto features conftest.py
```

Run **all three** after every change — a step that leaves the suite green but
introduces a lint or type error is not done.

Tests **never** call the real Anthropic API. Replace the LLM client with a test double (`unittest.mock` / `pytest-mock`) in the step definitions — the business scenarios in `.feature` files speak only about what the language model "returns"/"is instructed to return", never about test doubles. Embeddings in tests: a fake/deterministic implementation (no model downloads in CI).

**Note:** When defining steps for pytest-bdd, ensure that steps with the same text but different logic use unique function names or `target_fixture` to avoid conflicts.

## 📜 Conventions

- Dependencies restricted to Apache-2.0 / MIT / MPL-2.0 licenses. **No BSD, no GPL/AGPL, no proprietary.**
- User configuration only via YAML + the `ANTHROPIC_API_KEY` environment variable (never hard-coded).
- Every ontology change (class, slot, instance) **must** carry provenance: source document path, chunk id, **and the source text excerpt** it was derived from.
- A single failing document (corrupted PDF, etc.) must not abort the build — log and skip it.
- Commit after every green ATDD cycle: `feat: <feature-name>` or `refactor: <feature-name>`.

## ✅ Definition of done for a feature

1. All scenarios of the `.feature` pass (`pytest features/ -k <feature>`).
2. The whole existing suite passes (`pytest`).
3. `ruff check .` and `mypy onto features conftest.py` are clean.
4. Code is typed, duplicate-free, and follows the conventions above.
5. No new dependencies outside the list allowed in README.