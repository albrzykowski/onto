# TODO

Scenariusze do dopisania przez autora Gherkina. Agent ich nie pisze — `AGENTS.md`
zabrania edycji plików `.feature`; po ich dodaniu agent przechodzi normalny cykl ATDD.

## `features/config-loading.feature`

Klucze `api_key` i `embedding_api_key` muszą trafić do odpowiednich adapterów.
Brak scenariusza sprawdzającego, że klucze faktycznie docierają do LiteLLM.

```gherkin
  Scenario: The two keys reach their own adapters
    Given the configuration has model "openai/gpt-4o" and api_key "sk-openai"
    And the configuration has embedding_model "mistral/mistral-embed" and embedding_api_key "sk-mistral"
    When the adapters are built for the run
    Then the LLM adapter is given the key "sk-openai"
    And the embedder adapter is given the key "sk-mistral"
```

## `features/llm-extraction.feature`

`max_tokens` może uciąć odpowiedź modelu, a `read_json` zwraca surowy tekst zamiast błędu.
Brak scenariusza rozróżniającego ucięcie od błędnego JSON-a.

```gherkin
  Scenario: A reply cut off at the token limit is not taken for an answer
    Given a document chunk about vehicle engines
    And the model is given max_tokens of 64
    And the model replies with the class "Engine" and stops at the token limit
    When extraction runs for that chunk
    Then an error names the chunk as cut off
    And the truncated reply is not parsed as concepts
```

## `features/tbox-generation.feature`

### Allow-list i normalizacja nazw

`_allowed` normalizuje nazwę z konfiguracji, a `_admit` oczekuje znormalizowanej nazwy
kandydata. Brak scenariusza weryfikującego, że klasa dopuszczona w oryginalnym casingu
zostanie zapisana.

```gherkin
  Scenario: A concept allowed in the configuration's own casing is written
    Given a configuration with allowed_classes containing the class "vehicle"
    And the LLM has returned the class candidate "vehicle"
    When the T-Box is generated
    Then the class Vehicle is in the schema
    And no class is logged as rejected
```

### Slot spoza allow-list

Klasa dostaje tylko sloty, które trafiły do schematu. Brak scenariusza sprawdzającego,
że slot odrzucony przez `allowed_relations` nie zostanie przypisany do klasy.

```gherkin
  Scenario: A class is assigned only the slots the schema has
    Given a configuration with allowed_relations containing the relation "has_engine"
    And the LLM has returned the class candidate "Vehicle" and the relations "has_engine", "has_wheel"
    When the T-Box is generated
    Then the class Vehicle has the slot "has_engine" only
    And a "slot.rejected" event with the reason "not_in_allowed_relations" is recorded for has_wheel
```

### Zdarzenia i excerpt dla slotów

Slot utworzony z ekstrakcji nie jest logowany. `schema.yaml` zawiera slot `has_engine`,
ale `provenance.jsonl` nie ma żadnego zdarzenia slotu. T-Box nie zapisuje też excerptu,
w przeciwieństwie do A-Box.

```gherkin
  Scenario: Slot creation is logged with its source excerpt
    Given the LLM returns the class Vehicle and the relation has_engine from one chunk
    When the T-Box is generated
    Then an "slot.created" event for has_engine is recorded with the chunk and the excerpt

  Scenario: Classes and slots carry the excerpt they were derived from
    Given the LLM returns the class Vehicle and the relation has_engine from one chunk
    When the T-Box is generated
    Then every class and every slot has a "source_excerpt" annotation with the text it was derived from
```

## `features/abox-generation.feature`

### Zdarzenia dla instancji

Log zapisywał odrzucenia, ale nie zapisy. Brak scenariuszy weryfikujących eventy
`instance.created` i `instance.updated`.

```gherkin
  Scenario: A written instance is recorded
    Given a generated T-Box with the class Vehicle
    And the LLM returns the instance "VW Golf" of class Vehicle
    When the A-Box is generated
    Then an "instance.created" event for VW_Golf is recorded with the chunk and the excerpt

  Scenario: An instance the corpus names again is extended, not restated
    Given an existing A-Box in which VW_Golf has the slot has_engine with the value "1_6_TDI"
    And the LLM returns the instance "VW Golf" of class Vehicle with no slot values
    When update mode runs
    Then the instance VW_Golf still has the slot has_engine with the value "1_6_TDI"
    And its source_documents annotation cites the new document
    And an "instance.updated" event for VW_Golf is recorded

  Scenario: Two wordings of one id do not overwrite each other
    Given a generated T-Box with the class Vehicle
    And the LLM returns the instances "VW Golf" and "VW_Golf" of class Vehicle
    When the A-Box is generated
    Then one instance VW_Golf is written
    And an "instance.rejected" event with the reason "identifier_taken" is recorded
```

### Wiszące odwołania w slotach

**Zablokowane przez istniejacy scenariusz w tym samym pliku.**
`abox-generation.feature:12` wymaga zapisania `has_engine: 1_6_TDI` w scenariuszu,
gdzie `1_6_TDI` nie jest instancją. Trzeba najpierw zmienić ten scenariusz.

```gherkin
  Background:
    Given a generated T-Box with the classes Vehicle and Engine and the slot has_engine

  Scenario: A slot value that names a written instance is written
    Given the LLM returns the instance "VW Golf" of class Vehicle with has_engine pointing to "1.6 TDI"
    And the LLM returns the instance "1.6 TDI" of class Engine
    When the A-Box is generated
    Then it contains the instance "VW_Golf" of class Vehicle
    And the instance has the slot has_engine with the value "1_6_TDI"

  Scenario: A slot value that names no written instance is dropped and recorded
    Given the LLM returns the instance "VW Golf" of class Vehicle with has_engine pointing to "1.6 TDI"
    When the A-Box is generated
    Then the instance "VW_Golf" is written
    And the instance has no slot has_engine
    And an "instance.rejected" event with the reason "unresolved_reference" is recorded for the value "1_6_TDI"
```

## `features/chunking.feature`

`chunk_id` powinien być niezależny od bezwzględnej ścieżki. Brak scenariusza sprawdzającego,
że nazwa dokumentu jest względna do katalogu roboczego.

```gherkin
  Scenario: A chunk is named after the document as the working directory names it
    Given a document at "corpus/article1.txt" and the working directory is the project root
    When the document is chunked
    Then the first chunk has the chunk id "corpus/article1.txt#c1"
```

## Uwagi

- Timeout i ponowienia z `onto/llm_litellm.py` celowo nie mają scenariusza: to zachowanie
  adaptera, który jest testowany jednostkowo (`tests/test_llm_adapters.py`,
  `tests/test_embedding_adapters.py`).
