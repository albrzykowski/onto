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
├── extraction.py      # LLM calls (anthropic), prompts, batching
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
3. Code is typed, duplicate-free, and follows the conventions above.
4. No new dependencies outside the list allowed in README.