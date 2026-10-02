# Auto Ontology Builder

A Python library that automatically builds an ontology (T-Box + A-Box) from unstructured text
documents using an LLM of your choice. The ontology is written in [LinkML](https://linkml.io),
and every class, slot and instance it produces is recorded in a provenance log with the source
document, the chunk and the exact text excerpt it was derived from.

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

#### What an adapter is

An *adapter* is the small piece of code that sends one request to a language model and hands
the answer back. Nothing else in this project talks to a provider — everything else works with
the answer. Two adapters ship with the library: one for answering prompts, one for embeddings.

Both run on [LiteLLM](https://github.com/BerriAI/litellm), which already knows how to reach
OpenAI, Mistral, Anthropic and the other providers. That is why there is no provider package to
install: you choose a provider by naming it in the model, not by installing anything.

LiteLLM is the heaviest dependency this project takes. On Linux it also needs a native C++
library at run time, which most distributions already provide. On NixOS it has to be put on the
library path first:

```bash
# NixOS only
export LD_LIBRARY_PATH=/nix/store/<hash>-gcc-*-lib/lib:$LD_LIBRARY_PATH
```

On NixOS every command below needs that line — not only `pip install`, but anything that imports
LiteLLM, tests included. On Windows, macOS and other Linux distributions nothing has to be set.

`openai` is a direct dependency too, not an extra: LiteLLM answers with OpenAI-shaped responses,
so its errors derive from `openai.APIError`, and both adapters catch that class rather than
`litellm.APIError`, which is not the base of LiteLLM's errors and would catch nothing.

### 3. Describe the ontology, the models and the API keys

Copy `config.example.yaml` to `config.yaml` and adjust it for your setup. You can also create `config.yaml` manually:

```yaml
# Subject matter of the ontology: domain name -> description.
# At least one domain is required.
domains:
  automotive: "Passenger and commercial vehicles and their components"

# Concepts the model may use. Leave a map as {} to let the model pick concepts within the
# domains. If you list a concept, you must also describe it.
allowed_classes: {}
allowed_relations: {}

# "override" starts from scratch, "update" merges with the ontology already in the output
# directory and uses embeddings to recognise repeated concepts.
mode: override

# Models. The part before the slash is the provider ("mistral", "openai", ...). Both models
# are required and may point to different providers.
model: "mistral/mistral-large-latest"
embedding_model: "mistral/mistral-embed"

# Keys, passed straight to the adapters. Nothing is read from the environment. If both models
# use the same provider, the same key works for both.
api_key: "your_api_key"
embedding_api_key: "your_api_key"

# How documents are split into chunks.
chunking_strategy: fixed
max_chunk_tokens: 2000
overlap_tokens: 200  # overlap between chunks; must be smaller than max_chunk_tokens

# How much the model is asked for at once.
batch_size: 4
max_concepts_per_batch: 5

# How similar two concept names must be to count as the same concept, in update mode.
similarity_threshold: 0.85
```

**Every field is required.** There are no defaults and nothing is read from the environment,
so the file above is the whole configuration; a field left out is a `ConfigValidationError`
that names it. `domains` may not be empty, and every concept you name in any of the three
maps needs a description, because the description is what reaches the prompt.

`domains` narrows the subject matter; `allowed_classes` and `allowed_relations` go further and
list the concepts themselves. List either of the two allow-lists and the model is told to use
only those names. Leave both maps as `{}` and the model picks the concepts that matter within
`domains` — but it still works inside them, and a build about `automotive` never yields a
`Recipe`.

The provider is named by the model, never by a separate setting: the part before the slash
decides who answers. Naming both models is what keeps a build from sending its prompts to one
account and its embeddings to another.

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

The adapters also bound every request: `onto.llm_litellm.TIMEOUT_SECONDS` (120) and
`NUM_RETRIES` (3). A provider that stops answering can no longer hold a build open forever, and
a short failure is retried instead of losing everything that batch found. These are constants in
the module rather than fields in `config.yaml`, because there is nothing in them that you should
have to tune: every field in the configuration is a decision about the ontology.

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

With `mode: override` that is all `build` does: it discards whatever the output directory held
before.

### 6. Extend the ontology with new documents

`mode: update` reads only the documents whose fingerprint `ontology/state.json` does
not record yet, and extends what is already there. The classes, slots and instances of
an earlier build are kept, a concept that turns out to be another name for a class the
schema already has is merged into it, and a slot the new documents describe with a second
type is put to the model to resolve. The provenance log of the earlier build is appended
to, not replaced, and a run that finds nothing new writes nothing at all.

Telling a repeated concept from a new one is done with embeddings, so update mode is given an
embedder. The one that ships takes `embedding_model` and `embedding_api_key` from the
configuration and nothing else — the same rule as for the model: no key is picked up from the
environment, and there is no fallback from `embedding_api_key` to `api_key`.

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
slots:
  has_engine:
    name: has_engine
    description: Links a vehicle to the engine that powers it.
```

A concept the corpus states in several places gets one description that covers all of them,
because a description taken from a single chunk would drop what the others said. The same holds
for classes, slots and instances, and `class.updated`, `slot.updated` and `instance.updated`
events in the log record the wording that was written.

`ontology/instances.yaml` — the A-Box:

```yaml
instances:
  VW_Golf:
    class: Vehicle
    description: A compact car produced by Volkswagen since 1974.
    has_engine: 1_6_TDI
    annotations:
      source_documents:
        tag: source_documents
        value:
        - corpus/article1.txt#c1
```

An instance is only written for a class the T-Box defines. Anything else is left out and
recorded as `instance.rejected` with the reason — a slot value that names no instance the
A-Box knows included.

`ontology/provenance.jsonl` — one event per line, recording what each build changed and where
it came from: the source document, the chunk and the text excerpt.

`ontology/state.json` — the fingerprint of every document a build has read, so a later run can
tell which of them it has already seen.
