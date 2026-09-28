# Auto Ontology Builder

> A Python library that automatically builds an ontology (T-Box + A-Box) from unstructured text documents using an LLM (Anthropic Claude API). The ontology is described in **LinkML**.

## ✨ Features

- Loads `.txt`, `.md`, `.pdf`, `.docx` documents from a given folder (recursively)
- Automatic extraction of classes, relations, and instances via LLM
- **T-Box** (schema) and **A-Box** (instances) generated in LinkML format (YAML/JSON)
- Two operating modes:
  - **Override** — the ontology is rebuilt from scratch
  - **Update** — the existing ontology is extended with new data (deduplication: embeddings + LLM verification)
- Configurable ontology scope via YAML: domains (with descriptions), allowed classes and relations
- Full provenance log: every ontology change is linked to the source document, chunk, **and the exact text excerpt it was derived from**
- Large corpus support (1000+ documents): chunking, batching, fingerprinting (skipping unchanged files)
- Class and relation names in English (ontology standard); source texts may be in any language

## 🔧 Stack (OpenSource only — Apache-2.0 / MIT / MPL-2.0 only, **no BSD**)


| Component                                | License          |
| ---------------------------------------- | ---------------- |
| `anthropic`                              | MIT              |
| `linkml`, `linkml-runtime`               | Apache-2.0 / CC0 |
| `sentence-transformers` (or `fastembed`) | Apache-2.0       |
| `pdfminer.six`                           | MIT              |
| `python-docx`                            | MIT              |
| `typer`                                  | MIT              |
| `pydantic`                               | MIT              |
| `pytest`, `pytest-bdd`                   | MIT              |


## 🚀 Quick Start

```bash
pip install -e .
export ANTHROPIC_API_KEY="sk-ant-..."
```

Build an ontology (override mode):

```bash
onto build --config config.yaml --input ./corpus --output ./ontology
```

Update an existing ontology:

```bash
onto update --config config.yaml --input ./corpus_new --output ./ontology
```

As a library:

```python
from onto import OntologyBuilder, BuilderConfig

config = BuilderConfig.from_yaml("config.yaml")
builder = OntologyBuilder(config)
result = builder.build(input_dir="./corpus", output_dir="./ontology", mode="override")
```

## ⚙️ Configuration (`config.yaml`)

```yaml
# Domains of the ontology. Each domain has a name and a free-text description
# that is injected into the LLM prompt to ground the extraction.
# Three scoping modes are supported:
#   1. domains + allowed_classes/allowed_relations  -> the LLM is constrained
#      to the predefined concepts (prompt optimization: it never proposes extras)
#   2. domains only                                  -> the LLM decides which
#      concepts matter within each domain
#   3. no domains, no allow-lists                    -> the LLM has full freedom
domains:
  - name: automotive
    description: >
      Passenger and commercial vehicles, their components (engines, drivetrains,
      electronics), manufacturers, and fuel/propulsion types.
  - name: supply_chain
    description: >
      Production networks, suppliers, factories, logistics of vehicle parts.

# Optional restriction to specific classes and relations.
# If set, the LLM is instructed to ONLY use these concepts.
allowed_classes: [Vehicle, Engine, Manufacturer, FuelType]
allowed_relations: [produced_by, has_engine, uses_fuel]

# Mode: override | update
mode: update

llm:
  model: claude-sonnet-4-5
  max_tokens: 4096
  batch_size: 20          # chunks/calls processed in batches
  temperature: 0.0

chunking:
  strategy: fixed         # fixed | semantic
  max_chunk_tokens: 2000
  overlap_tokens: 200

deduplication:
  embedding_model: sentence-transformers/all-MiniLM-L6-v2
  similarity_threshold: 0.85
  llm_verify: true        # merge candidates are confirmed by the LLM

paths:
  output_dir: ./ontology
  provenance_log: ./ontology/provenance.jsonl
```

## 📁 Output structure

```
ontology/
├── schema.yaml          # T-Box — LinkML schema
├── instances.yaml       # A-Box — LinkML instances
├── provenance.jsonl     # build log (1 line = 1 event)
└── state.json           # document fingerprints (for update mode)
```

## 🗒️ Provenance log

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

The project is built using the **ATDD** cycle — see `AGENTS.md` and the `features/` directory.

**Use the virtual environment `.venv` to run tests:**

```bash
source .venv/bin/activate
pytest features/ -v
```

## 📜 License

Apache-2.0
