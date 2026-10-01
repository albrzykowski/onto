# Auto Ontology Builder

A Python library that automatically builds an ontology (T-Box + A-Box) from
unstructured text documents using an LLM of your choice. The ontology is written in
[LinkML](https://linkml.io), and every class, slot and instance it produces carries
provenance: the source document, the chunk and the exact text excerpt it was derived
from.

The project is under active development.

## Quick Start

### 1. Get the code and create a virtual environment

```bash
git clone <repository-url> onto-builder
cd onto-builder
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
.\.venv\Scripts\activate   # Windows
```

### 2. Install the library

```bash
pip install -e .
```

One adapter answers for every provider, so there is no provider package left to install.

#### What the provider layers cost

Both adapters run on [LiteLLM](https://github.com/BerriAI/litellm), which is what lets one
adapter answer for every provider. It is the heaviest dependency this project takes, and on
Linux it needs a native library:

```bash
# NixOS only: tokenizers links against the C++ runtime, which is not on the default path
export LD_LIBRARY_PATH=/nix/store/<hash>-gcc-*-lib/lib:$LD_LIBRARY_PATH
```

Every command below needs it on NixOS — not just `pip install`, but anything that imports
LiteLLM, tests included. Elsewhere it is found on its own.

Measured on `litellm` 1.103.1: 134 MB in `site-packages`, 61 installed packages, and roughly
15 seconds for the first `import litellm`. The library itself is 212 KB. `openai` is a direct
dependency too, not an extra: LiteLLM answers with OpenAI-shaped responses, so its exceptions
derive from `openai.APIError`, and both adapters catch that class rather than
`litellm.APIError`, which is not the base of LiteLLM's errors and would catch nothing.

### 3. Describe the ontology, the models and the API keys

Copy `config.example.yaml` to `config.yaml` and adjust it for your setup. You can also create `config.yaml` manually:

```yaml
domains:
  automotive: "Passenger and commercial vehicles and their components"
allowed_classes:
  Vehicle: "A machine that carries people or goods"
allowed_relations:
  produced_by: "Relates a product to the organization that makes it"
model: mistral/mistral-large-latest
embedding_model: mistral/mistral-embed
chunking_strategy: fixed
max_chunk_tokens: 2000
overlap_tokens: 200
batch_size: 4
max_concepts_per_batch: 5
mode: override
similarity_threshold: 0.85
api_key: "your_api_key"
embedding_api_key: "your_api_key"
```

**Every field is required.** There are no defaults and nothing is read from the environment,
so the file above is the whole configuration; a field left out is a `ConfigValidationError`
that names it. `domains` may not be empty, and every concept you name in any of the three
maps needs a description, because the description is what reaches the prompt.

`domains` narrows the subject matter; `allowed_classes` and `allowed_relations` go further and
list the concepts themselves. List either of the two allow-lists and the model is told to use
only those names. Leave both maps as `{}` and the model picks the concepts that matter within
`domains` — but it still works inside them, and a `domains: [automotive]` build never yields
a `Recipe`.

Each model name carries its provider: the part before the slash decides who answers. This is
the only place a provider is named, which is what keeps a build from sending its prompts to
one account and its embeddings to another.

`model` is the model that answers the prompts, `embedding_model` the one that turns concept
names into vectors for update mode. They are separate because a provider embeds with a
different model than it answers with: `mistral/mistral-large-latest` and `mistral/mistral-embed`
are both Mistral, and neither would work in the other's place. **Name both**, so nothing is
sent to an account the file never mentions:

```yaml
model: openai/gpt-4o
embedding_model: openai/text-embedding-3-small
```

The two may name different providers — there is no rule that says a build has to answer and
embed in the same place. When they do, they need different keys, which is what the second one
is for:

```yaml
model: openai/gpt-4o
api_key: "sk-your-openai-key"
embedding_model: mistral/mistral-embed
embedding_api_key: "your-mistral-key"
```

From the command line both keys are handed to the adapters for you; from Python you pass
`api_key=config.api_key` and `embedding_api_key=config.embedding_api_key` yourself.

### 4. Prepare the input documents

Put your documents in a folder — `.txt`, `.md`, `.pdf` and `.docx` are read
recursively:

```
corpus/
├── article1.txt
├── article2.md
└── manual.pdf
```

### 5a. Build from the command line

```bash
onto build --config config.yaml --input corpus/ --output ontology/
```

`onto build` starts the ontology over. `onto update` extends the one already in the output
directory, reading only the documents whose fingerprint it has not recorded. `onto --help`
lists what is available.

### 5b. Or build from Python

```python
from pathlib import Path

from onto.builder import build
from onto.config import load_config
from onto.llm_litellm import LiteLLMLLM

config = load_config("config.yaml")

llm = LiteLLMLLM(api_key=config.api_key)
build(input_dir=Path("corpus"), output_dir=Path("ontology"), config=config, llm=llm)
```

Pass `api_key=config.api_key` to the adapter. LiteLLM will not look the key up from the
environment for a request that names a provider, so leaving it out sends a request with no
credentials and the provider answers `Invalid API Key` — the same as a key that really is wrong.

Both adapters bound each request: `onto.llm_litellm.TIMEOUT_SECONDS` (120, against LiteLLM's
own 6000) and `NUM_RETRIES` (3). A provider that never answers cannot hold a build open, and a
transient failure is retried rather than costing the run every concept that batch stated. A
failure that survives the attempts raises as before, and the caller logs it and skips the
batch. They are module constants, not configuration fields: there is nothing about them that a
user of this project should have to tune, and every field in `config.yaml` is a decision about
the ontology.

`build` runs the whole pipeline — ingestion, chunking, extraction, T-Box, A-Box — in the
mode `config.mode` names. The steps are also available one by one, if you want to inspect
or change a stage:

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
log = ProvenanceLog(Path("ontology/provenance.jsonl"), mode=config.mode)
schema_path = generate_tbox(candidates, config, llm, Path("ontology"), log)
generate_abox(chunks, config, llm, schema_path, log)
```

The log is not something the schema is written beside afterwards: the schema writer records
every class it writes, refuses or updates in it as it goes, so it has to exist first.

The schema is the only vocabulary for the instances: an instance of a class the
T-Box does not define is never written — it is rejected and logged as
`instance.rejected`.

With `mode: override` (the default) that is all `build` does: it discards whatever the
output directory held before.

### 6. Extend the ontology with new documents

`mode: update` reads only the documents whose fingerprint `ontology/state.json` does
not record yet, and extends what is already there. The classes, slots and instances of
an earlier build are kept, a concept that turns out to be another name for a class the
schema already has is merged into it, and a slot the new documents describe with a second
type is put to the model to resolve. The provenance log of the earlier build is appended
to, not replaced, and a run that finds nothing new writes nothing at all.

Telling a repeated concept from a new one is done with embeddings, so update mode is given
an embedder. The one that ships is handed `embedding_model` and `embedding_api_key` from the
configuration, and nothing else: a build may answer and embed through different providers,
so `embedding_api_key` is its own key and there is no fallback to `api_key` and no
environment variable to pick one up from.

```python
from onto.builder import build
from onto.embeddings import LiteLLMEmbedder
from onto.llm_litellm import LiteLLMLLM

build(
    input_dir=Path("corpus"),
    output_dir=Path("ontology"),
    config=config,
    llm=LiteLLMLLM(api_key=config.api_key),
    embedder=LiteLLMEmbedder(
        api_key=config.embedding_api_key,
        model=config.embedding_model,
    ),
)
```

Any object with an `embed` method will do — the `Embedder` protocol in `onto.dedup` is all
`build` asks for, so an embedder that runs locally takes its place without anything else
changing. The command line needs none of this: `onto update` builds the embedder itself.

From Python it is required, not optional. `build` refuses `mode: update` without one, since
telling a repeated concept from a new one is what it is for:

```
BuildError: update mode needs an embedder: it cannot tell a repeated concept from a new one
without one
```

### 7. Inspect the output

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
