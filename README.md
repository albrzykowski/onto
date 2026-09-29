# Auto Ontology Builder

A Python library that automatically builds an ontology (T-Box + A-Box) from
unstructured text documents using an LLM of your choice. The ontology is written in
[LinkML](https://linkml.io), and every class, slot and instance it produces carries
provenance: the source document, the chunk and the exact text excerpt it was derived
from.

The project is under active development. The library is usable programmatically;
the command-line interface is not implemented yet.

## Quick Start

### Option A: Command-line interface

The `onto` command is planned but does not exist yet — use Option B until it
lands. The intended interface is:

```bash
onto build --input corpus/ --output ontology/
```

### Option B: Programmatic usage

#### 1. Get the code and create a virtual environment

```bash
git clone <repository-url> onto-builder
cd onto-builder
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
.\.venv\Scripts\activate   # Windows
```

The `onto` package runs straight from the repository root; it is not installed as
a distribution yet.

#### 2. Install the dependencies

```bash
pip install pydantic pyyaml pdfminer.six python-docx mistralai
```

`mistralai` is needed only for the Mistral adapter — swap it for `anthropic` or
`openai` if you build with another provider.

#### 3. Configure the model and the API key

Create a `config.yaml` in the repository root:

```yaml
model: mistral-large-latest
chunking_strategy: fixed
max_chunk_tokens: 2000
overlap_tokens: 200
batch_size: 4
mode: override
similarity_threshold: 0.85
api_key: "your_mistral_api_key"
```

Then export the key for the Mistral adapter:

```bash
export MISTRAL_API_KEY="your_api_key"
```

The `api_key` field is what the configuration validates against; the adapter
itself reads `MISTRAL_API_KEY` from the environment when it is constructed
without a key.

#### 4. Prepare the input documents

Put your documents in a folder — `.txt`, `.md`, `.pdf` and `.docx` are read
recursively:

```
corpus/
├── article1.txt
├── article2.md
└── manual.pdf
```

#### 5. Build the ontology

```python
from pathlib import Path

from onto.builder import build
from onto.config import load_config
from onto.llm_mistral import MistralLLM

config = load_config("config.yaml")
llm = MistralLLM()

build(input_dir=Path("corpus"), output_dir=Path("ontology"), config=config, llm=llm)
```

`build` runs the whole pipeline — ingestion, chunking, extraction, T-Box, A-Box —
in the mode `config.mode` names. The steps are also available one by one, if you want
to inspect or change a stage:

```python
from onto.chunking import chunk_document
from onto.extraction import extract
from onto.ingestion import load_documents
from onto.instance_gen import generate_abox
from onto.provenance import ProvenanceLog
from onto.schema_gen import generate_tbox

documents = load_documents(Path("corpus"))
chunks = [chunk for document in documents for chunk in chunk_document(document, config)]
candidates = extract(chunks, config, llm)
schema_path = generate_tbox(candidates, config, llm, Path("ontology"))
log = ProvenanceLog(Path("ontology/provenance.jsonl"), mode=config.mode)
generate_abox(chunks, config, llm, schema_path, log)
```

The schema is the only vocabulary for the instances: an instance of a class the
T-Box does not define is never written — it is rejected and logged as
`instance.rejected`.

With `mode: override` (the default) that is all `build` does: it discards whatever the
output directory held before.

#### 6. Extend the ontology with new documents

`mode: update` reads only the documents whose fingerprint `ontology/state.json` does
not record yet, and extends what is already there. The classes, slots and instances of
an earlier build are kept, a concept that turns out to be another name for a class the
schema already has is merged into it, and a slot the new documents describe with a second
type is put to the model to resolve. The provenance log of the earlier build is appended
to, not replaced, and a run that finds nothing new writes nothing at all.

Telling a repeated concept from a new one is done with embeddings, so update mode needs
an object with an `embed` method — the `Embedder` protocol in `onto.dedup`. No embedding
provider ships with the library yet, so bring your own:

```python
from onto.builder import build
from onto.llm_mistral import MistralLLM

class MyEmbedder:
    """Turn concept names into vectors; their cosine similarity is what is compared."""

    def embed(self, texts: list[str]) -> list[list[float]]:
        ...

build(
    input_dir=Path("corpus"),
    output_dir=Path("ontology"),
    config=config,
    llm=MistralLLM(),
    embedder=MyEmbedder(),
)
```

#### 7. Inspect the output

`ontology/schema.yaml` — the T-Box:

```yaml
classes:
  Vehicle:
    name: Vehicle
    description: A compact passenger car produced since 1974.
    slots:
    - has_engine
```

`ontology/instances.yaml` — the A-Box:

```yaml
instances:
  VW_Golf:
    class: Vehicle
    has_engine: 1_6_TDI
    annotations:
      source_documents:
        tag: source_documents
        value:
        - corpus/article1.txt#c1
      source_excerpt:
        tag: source_excerpt
        value: The Golf is produced by VW and has a 1.6 TDI engine
```

`ontology/provenance.jsonl` — one event per line, recording what each build
changed and where it came from.

`ontology/state.json` — the fingerprint of every document a build has read, so a later
run can tell which of them it has already seen.
