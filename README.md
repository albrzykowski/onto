# Auto Ontology Builder

> A Python library that automatically builds an ontology (T-Box + A-Box) from unstructured text documents using an LLM (Anthropic Claude API). The ontology is described in **LinkML**.

> [!WARNING]
> **Early stage — this README is mostly a design document.** Only configuration
> loading, document ingestion and chunking are implemented and covered by
> acceptance tests. Everything else (CLI, LLM extraction, T-Box/A-Box generation,
> provenance, deduplication, both build modes) is **planned**; the sections
> describing it are marked 🚧. See [Implementation status](#-implementation-status).

## 📍 Implementation status

| Area                 | State            | Acceptance criteria          |
| -------------------- | ---------------- | --------------------------- |
| Configuration        | ✅ implemented   | `features/config-loading.feature`     |
| Document ingestion   | ✅ implemented   | `features/document-ingestion.feature` |
| Chunking             | ✅ implemented   | `features/chunking.feature`           |
| LLM extraction       | 🚧 planned       | `features/llm-extraction.feature`     |
| T-Box generation     | 🚧 planned       | `features/tbox-generation.feature`    |
| A-Box generation     | 🚧 planned       | `features/abox-generation.feature`    |
| Provenance log       | 🚧 planned       | `features/provenance-logging.feature` |
| Override mode        | 🚧 planned       | `features/override-mode.feature`      |
| Update mode          | 🚧 planned       | `features/update-mode.feature`        |
| CLI                  | 🚧 planned       | `features/cli.feature`                |

The project follows the **ATDD** cycle (see `AGENTS.md`): features are
implemented in dependency order, and a feature is done only when all of its
Gherkin scenarios pass. The ✅ rows are the only ones with passing acceptance
tests today; the 🚧 rows have written criteria but no implementation.

## ✨ Features

### ✅ Implemented

- Loads `.txt`, `.md`, `.pdf`, `.docx` documents from a given folder (recursively)
- Configurable ontology scope via YAML: domains (with descriptions), allowed classes and relations
- Document fingerprints — SHA-256 of the extracted text, stable across re-saves of the same file
- Fixed-size chunking with configurable overlap, and stable `<path>#c<N>` chunk identifiers

### 🚧 Planned

- Automatic extraction of classes, relations, and instances via LLM
- **T-Box** (schema) and **A-Box** (instances) generated in LinkML format (YAML/JSON)
- Two operating modes:
  - **Override** — the ontology is rebuilt from scratch
  - **Update** — the existing ontology is extended with new data (deduplication: embeddings + LLM verification)
- Full provenance log: every ontology change is linked to the source document, chunk, **and the exact text excerpt it was derived from**
- Large corpus support (1000+ documents): LLM batching, skipping unchanged files
- Class and relation names in English (ontology standard); source texts may be in any language

## 🔧 Stack (OpenSource only — Apache-2.0 / MIT / MPL-2.0 only, **no BSD**)


| Component                                | License          | Used today |
| ---------------------------------------- | ---------------- | ---------- |
| `pydantic`                               | MIT              | ✅ config, ingestion |
| `PyYAML`                                 | MIT              | ✅ config loading |
| `pdfminer.six`                           | MIT              | ✅ PDF ingestion |
| `python-docx`                            | MIT              | ✅ DOCX ingestion |
| `pytest`, `pytest-bdd`                   | MIT              | ✅ test suite |
| `mypy`, `ruff`                           | MIT              | ✅ lint & type checks |
| `anthropic`                              | MIT              | 🚧 planned |
| `linkml`, `linkml-runtime`               | Apache-2.0 / CC0 | 🚧 planned |
| `sentence-transformers` (or `fastembed`) | Apache-2.0       | 🚧 planned |
| `typer`                                  | MIT              | 🚧 planned |

## 🚀 Quick Start

> [!WARNING]
> 🚧 The installation and CLI commands below are **planned**. There is no
> `pyproject.toml` yet, so `pip install -e .` does not work, and the `onto` CLI is
> not implemented (`features/cli.feature`). Until then, use the library directly
> from the source tree — the last example in this section is the only one that
> runs today.

🚧 Planned installation:

```bash
pip install -e .
export ANTHROPIC_API_KEY="sk-ant-..."
```

🚧 Planned — build an ontology (override mode):

```bash
onto build --config config.yaml --input ./corpus --output ./ontology
```

🚧 Planned — update an existing ontology:

```bash
onto update --config config.yaml --input ./corpus_new --output ./ontology
```

✅ **As a library (works today):**

```python
from pathlib import Path

from onto.config import load_config
from onto.ingestion import load_documents

config = load_config("config.yaml")
documents = load_documents(Path("./corpus"))
```

## ⚙️ Configuration (`config.yaml`)

✅ Implemented — `onto/config.py`

`BuilderConfig` is a **flat** model — every key below is a top-level field. Unknown
keys are silently ignored, so a typo in a key name will not raise an error.

```yaml
# Domains of the ontology. A plain list of domain names...
domains: [automotive, supply_chain]

# ...and their free-text descriptions, keyed by domain name. Descriptions are
# injected into the LLM prompt to ground the extraction.
domain_descriptions:
  automotive: >
    Passenger and commercial vehicles, their components (engines, drivetrains,
    electronics), manufacturers, and fuel/propulsion types.
  supply_chain: >
    Production networks, suppliers, factories, logistics of vehicle parts.

# Optional restriction to specific classes and relations.
# If set, the LLM is instructed to ONLY use these concepts.
allowed_classes: [Vehicle, Engine, Manufacturer, FuelType]
allowed_relations: [produced_by, has_engine, uses_fuel]

# Mode: override | update          (default: override)
mode: update

# Chunking — a document is split into windows of max_chunk_tokens tokens,
# each starting overlap_tokens before the previous one ended.
chunking_strategy: fixed           # fixed | semantic
max_chunk_tokens: 2000
overlap_tokens: 200

similarity_threshold: 0.85

# The API key. Leave it out to read ANTHROPIC_API_KEY from the environment.
api_key: sk-ant-...
```

Three scoping modes for the extraction prompt:

1. `allowed_classes` / `allowed_relations` **and** `domains` → the LLM is constrained to the predefined concepts and never proposes extras (prompt efficiency).
2. `domains` only → the LLM decides which concepts matter within those domains. A `domains: [automotive]` prompt never yields `Recipe`.
3. Neither → the LLM has full freedom.

### Configuration defaults

| Field                  | Type                 | Default     |
| ---------------------- | -------------------- | ----------- |
| `domains`              | `list[str]`          | `[]`        |
| `allowed_classes`      | `list[str]`          | `[]`        |
| `allowed_relations`    | `list[str]`          | `[]`        |
| `domain_descriptions`  | `dict[str, str]`     | `{}`        |
| `mode`                 | `str`                | `"override"` |
| `chunking_strategy`    | `str`                | `"fixed"`   |
| `max_chunk_tokens`     | `int`                | `2000`      |
| `overlap_tokens`       | `int`                | `200`       |
| `similarity_threshold` | `float`              | `0.85`      |
| `api_key`              | `str \| None`        | env var     |

### Loading a configuration

```python
from onto.config import load_config

config = load_config("config.yaml")     # explicit path
config = load_config()                  # defaults to ./config.yaml
```

`load_config` returns a validated `BuilderConfig`. An empty YAML file is valid and
yields a `BuilderConfig` with all defaults.

**The API key is mandatory**, even when it is absent from the YAML file. It is
resolved in this order:

1. the `api_key` field in the YAML file,
2. the `ANTHROPIC_API_KEY` environment variable.

```python
import os
from onto.config import load_config

os.environ["ANTHROPIC_API_KEY"] = "sk-ant-..."
config = load_config("config.yaml")     # api_key picked up from the environment
```

**Errors are raised as dedicated exceptions, not `pydantic.ValidationError`:**

| Exception                | Raised when                                                     |
| ------------------------ | --------------------------------------------------------------- |
| `ConfigValidationError`  | `mode` is neither `override` nor `update`                       |
| `MissingAPIKeyError`     | no `api_key` in the file and no `ANTHROPIC_API_KEY` in the env   |

```python
from onto.config import ConfigValidationError, MissingAPIKeyError, load_config

try:
    config = load_config("config.yaml")
except ConfigValidationError as error:
    print(f"invalid configuration: {error}")
except MissingAPIKeyError as error:
    print(f"no API key: {error}")
```

## 📥 Document ingestion

✅ Implemented — `onto/ingestion.py`

`load_documents` walks the input directory **recursively** and returns one
`Document` per supported file. The signature takes a plain path — it does **not**
take a `BuilderConfig`. Ingestion is format-driven, not configuration-driven; the
loaded configuration only influences later stages of the build.

```python
from pathlib import Path

from onto.ingestion import load_documents

documents = load_documents(Path("./corpus"))

for document in documents:
    print(document.path, document.fingerprint, len(document.text))
```

### The `Document` model

| Attribute     | Type   | Meaning                                                       |
| ------------- | ------ | ------------------------------------------------------------- |
| `path`        | `Path` | source path **as given**, e.g. `corpus/sub/nested.txt`         |
| `text`        | `str`  | text extracted from the document                              |
| `fingerprint` | `str`  | SHA-256 of `text`, hex-encoded                                |

`path` is kept relative to the input directory you passed in — it is not
resolved to an absolute path — so it can be written straight into the provenance
log.

The fingerprint is computed from the **extracted text**, not from the raw bytes.
Re-saving a document — which rewrites PDF creation dates, DOCX zip timestamps
and other container metadata — leaves the fingerprint unchanged, which is what
lets update mode skip unchanged documents.

Note that the same text stored in two *different* formats can still yield two
different fingerprints, because each extractor normalizes whitespace and line
breaks its own way. A fingerprint is therefore a reliable "did this change?"
signal within a format, not a cross-format content hash.

### Supported formats and failure handling

| File                              | Outcome                                                        |
| --------------------------------- | -------------------------------------------------------------- |
| `.txt`, `.md`                     | read as UTF-8                                                  |
| `.pdf`                            | parsed with `pdfminer.six`                                     |
| `.docx`                           | paragraphs parsed with `python-docx`                           |
| any other extension (`.png`, …)  | **skipped**, a `WARNING` is logged naming the file            |
| a supported but corrupted file    | **skipped**, an `ERROR` is logged naming the file              |

**A single bad file never aborts ingestion.** Unsupported and unreadable files
are logged and skipped, and the remaining documents are returned. An empty
folder, or an input directory that does not exist, raises
`NoDocumentsFoundError`.

```python
import logging
from pathlib import Path

from onto.ingestion import DocumentLoadError, NoDocumentsFoundError, load_document, load_documents

logging.basicConfig(level=logging.INFO)

try:
    documents = load_documents(Path("./corpus"))
except NoDocumentsFoundError as error:
    print(f"nothing to ingest: {error}")

# A single file, raising instead of skipping:
try:
    document = load_document(Path("./corpus/article1.pdf"))
except DocumentLoadError as error:
    print(f"unreadable: {error}")
```

Discovery order is deterministic (`sorted()` over the directory tree), so repeated
runs over an unchanged corpus produce identical document lists.

## ✂️ Chunking

✅ Implemented — `onto/chunking.py`

`chunk_document` splits one document into overlapping, size-limited chunks. It
takes a `Document` (from ingestion) and a `BuilderConfig`:

```python
from pathlib import Path

from onto.chunking import chunk_document
from onto.config import load_config
from onto.ingestion import load_documents

config = load_config("config.yaml")

for document in load_documents(Path("./corpus")):
    for chunk in chunk_document(document, config):
        print(chunk.chunk_id, chunk.token_count)
```

### The `Chunk` model

| Attribute     | Type   | Meaning                                                       |
| ------------- | ------ | ------------------------------------------------------------- |
| `chunk_id`    | `str`  | `<source_path>#c<N>`, numbered from 1                          |
| `text`        | `str`  | the chunk's slice of the document                             |
| `source_path` | `Path` | the document this chunk came from                             |
| `token_count` | `int`  | number of tokens in `text`                                    |

Because chunk identifiers embed the source path, they are stable across runs and
can be stored in the provenance log as-is. They are **1-based**: the first chunk
of `corpus/a.txt` is `corpus/a.txt#c1`.

### How the fixed strategy works

The document is split into windows of at most `max_chunk_tokens` tokens. Each
window after the first starts `overlap_tokens` *before* the previous one ended,
so consecutive chunks share exactly `overlap_tokens` tokens at their boundary —
a sentence straddling a boundary is present in full in one of them.

With `max_chunk_tokens: 100` and `overlap_tokens: 20`:

| Document size | Chunks | Chunk sizes          |
| ------------- | ------ | -------------------- |
| 50 tokens     | 1      | 50                   |
| 100 tokens    | 1      | 100                  |
| 250 tokens    | 3      | 100, 100, **90**     |
| 300 tokens    | 4      | 100, 100, 100, **60** |

Coverage is complete — no token of the source document is ever dropped, and with
`overlap_tokens: 0` the chunks are an exact partition of the text. A document
with no text yields no chunks.

### What a "token" is here

**Tokens are whitespace-delimited words, not model tokens.** This is an
approximation: a real tokenizer for the target model would count differently, so
`max_chunk_tokens: 2000` is not a guarantee of 2000 model tokens. `tokenize` and
`count_tokens` in `onto/chunking.py` are the single place to swap when a real
tokenizer becomes available. Chunk boundaries, overlap and identifiers are all
computed from that one function, so replacing it changes nothing else.

`chunk_document` raises `ChunkError` when the configuration cannot produce
chunks: an unsupported `chunking_strategy` (only `fixed` is implemented),
`max_chunk_tokens` below 1, or `overlap_tokens` not in `0..max_chunk_tokens - 1`
— the last one would otherwise loop forever.

## 📁 Output structure

🚧 **Planned** — no build pipeline exists yet, so nothing writes this directory.

```
ontology/
├── schema.yaml          # T-Box — LinkML schema
├── instances.yaml       # A-Box — LinkML instances
├── provenance.jsonl     # build log (1 line = 1 event)
└── state.json           # document fingerprints (for update mode)
```

## 🗒️ Provenance log

🚧 **Planned** — `onto/provenance.py` does not exist yet. The event format below
is the one specified by `features/provenance-logging.feature` and is not produced
by any current code.

Every event (creation/update/merge of a class, relation, or instance) is recorded as one JSONL entry. Each entry includes the **source text excerpt** the change was derived from:

```json
{
  "event": "class.created",
  "id": "Vehicle",
  "source_documents": [{"path": "corpus/article1.txt", "chunk_id": "article1.txt#c12"}],
  "source_excerpt": "VW has been producing the Golf, a compact passenger car, since 1974.",
  "timestamp": "2026-09-27T10:00:00Z",
  "mode": "update"
}
```

## 🧪 Tests

The project is built using the **ATDD** cycle — see `AGENTS.md` and the `features/` directory. 3 of the 10 features currently have acceptance tests (configuration loading, document ingestion, chunking).

**Use the virtual environment `.venv` to run tests:**

```bash
source .venv/bin/activate
pytest features/ -v
```

**Static analysis** — `mypy` and `ruff` are configured in `pyproject.toml` and
are dev-only, not runtime dependencies:

```bash
pip install --group dev
source .venv/bin/activate
ruff check .
mypy onto features conftest.py
```

## 📜 License

Apache-2.0
