# TODO

Scenariusze do dopisania przez autora Gherkina. Agent ich nie pisze — `AGENTS.md`
zabrania edycji plików `.feature`; po ich dodaniu agent przechodzi normalny cykl ATDD.

## `features/adapter-wiring.feature`

Klucze `api_key` i `embedding_api_key` muszą trafić do odpowiednich adapterów.
Brak scenariusza sprawdzającego, że klucze faktycznie docierają do LiteLLM.

```gherkin
Feature: Adapter wiring
  As a developer
  I want the configuration keys to reach the adapters
  So that the build runs with the correct credentials

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

## `features/tbox-generation.feature` — aktualizacja klas/slotów/instancji

Obecnie klasa, slot i instancja zapisywane są raz z opisem z planu (LLM widzi tylko
nazwę klasy/slotu/instancji), a kolejne chunki z tą samą klasą/slotem/instancją
dołączają jedynie swój ID do `source_documents`. Informacje z późniejszych chunków
(np. nowy kontekst, inne detale) nie trafiają do opisu klasy, slotu ani instancji.

```gherkin
  Scenario: Class description is merged from multiple chunks using LLM
    Given the LLM returns the class Vehicle from chunk#1 with description "A motorized road vehicle"
    And the LLM returns the class Vehicle from chunk#2 with description "A car"
    When the T-Box is generated
    Then the class Vehicle has a description merged from both chunks
    And an "class.updated" event is recorded with the merged description

  Scenario: Slot description is merged from multiple chunks using LLM
    Given the LLM returns the relation has_engine from chunk#1 with description "Links a vehicle to its engine"
    And the LLM returns the relation has_engine from chunk#2 with description "The engine that powers a vehicle"
    When the T-Box is generated
    Then the slot has_engine has a description merged from both chunks
    And an "slot.updated" event is recorded with the merged description

  Scenario: Instance description is merged from multiple chunks using LLM
    Given the LLM returns the instance "VW Golf" of class Vehicle from chunk#1 with description "A car made by VW"
    And the LLM returns the instance "VW Golf" of class Vehicle from chunk#2 with description "A popular model"
    When the A-Box is generated
    Then the instance VW_Golf has a description merged from both chunks
    And an "instance.updated" event is recorded with the merged description
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

## Plan: typowanie i publikacja jako biblioteka

Przeprowadzone pomiary, na których plan opiera się (stan na 2026-10-02):

- `onto/` jest w pełni zadnotowany: 0 błędów pod `disallow_untyped_defs`,
  `warn_return_any`, `disallow_any_generics` i `warn_unreachable` (14 modułów).
- Braki są wyłącznie w warstwie testów: 88 brakujących adnotacji zwracanych,
  20 zwrotów `Any`, 176 surowych generyków — wszystkie w `features/` i `tests/`.
  158 z nich to `state: dict`, czyli stan współdzielony pytest-bdd, z natury `Any`.
- Nie ma żadnego `type: ignore` w repozytorium.
- `python_version = "3.11"` przy venvie na 3.12.14 — świadome i poprawne, zostawić.
- `LICENSE` to MIT, © 2026 Leszek Albrzykowski. **Pliku nie wolno zmieniać** — tylko
  wskazywać go z `pyproject.toml`.
- W historii git nie ma sekretów: 0 wartości `sk-` dłuższych niż 20 znaków,
  `config.yaml` nigdy nie był śledzony.
- `py.typed` nie ma, więc konsument nie dostaje żadnych typów.
- Globalne `ignore_missing_imports = true` ukrywa dokładnie dwa moduły bez `py.typed`:
  `yaml` (runtime) i `linkml` (dev, w `features/steps/`, zero `.pyi`). Wszystkie
  pozostałe (`docx`, `litellm`, `openai`, `pdfminer`, `pydantic`, `pytest`, `pytest_bdd`)
  mają `py.typed`.

### Krok 1 — `onto.*` twardo zadnotowany

W `[tool.mypy]` dodać nadpisanie:

```toml
[[tool.mypy.overrides]]
# `onto/` jest dziś w pełni zadnotowany; to trzyma go w tym miejscu. Warstwa testów
# jest wyłączona celowo: pytest-bdd przekazuje stan przez gołe `dict`.
module = "onto.*"
disallow_untyped_defs = true
warn_return_any = true
disallow_any_generics = true
```

`onto/__init__.py` istnieje, więc nazwy modułów to `onto.config`, `onto.builder` itd.
i wzorzec `onto.*` je obejmuje. Oczekiwany wynik: `Success: no issues found in
14 source files`, potem 39 plików na pełnym przebiegu.

### Krok 2 — zawęzić `ignore_missing_imports`

Usunąć globalne `ignore_missing_imports = true` i zastąpić nadpisańiem:

```toml
[[tool.mypy.overrides]]
# PyYAML i linkml nie dostarczają `py.typed`, więc mypy nie ma czego dla nich czytać
module = ["yaml.*", "linkml.*"]
ignore_missing_imports = true
```

Uwaga: mypy nie zna przeciwnika `--no-ignore-missing-imports`, więc usunięcia nie da się
wydryfować z CLI. Powyższe wyliczenie importów jest dowodem, że lista jest kompletna.
Jeśli przy przebiegu wyskoczy trzeci moduł, odezwie się natychmiast.

### Krok 3 — typy docierają do konsumenta

Dodać pusty `onto/py.typed` (znacznik PEP 561, treść celowo pusta) oraz w
`[tool.setuptools]`:

```toml
package-data = { onto = ["py.typed"] }
```

Na repozytorium nie wpływa: pakiet jest instalowany edytowalnie, a `mypy_path = "."`
i tak czyta `onto` z drzewa źródeł. Znaczenie ma tylko dla prawdziwego koła.

Weryfikacja wymaga `build` i `setuptools`, których w venv nie ma ani jednego, ani drugiego
(`ModuleNotFoundError: No module named 'setuptools'`). Dodać oba do grupy `dev` (MIT,
licencja w porządku), zbudować `python -m build` i potwierdzić, że `onto/py.typed`
jest w środku koła. Bez tego kroku zmiana pakowania jest niesprawdzona.

### Krok 4 — metadane `[project]` (do decyzji)

`[project]` ma sześć kluczy: `name`, `version`, `description`, `requires-python`,
`scripts`, `dependencies`. Brakuje `readme`, `license`, `license-files`, `authors`,
`keywords`, `classifiers`, `urls`. Pliki na dysku są, tylko nie są zadeklarowane, więc
strona pakietu na PyPI wygląda pusto.

Uwaga techniczna: forma SPDX `license = "MIT"` z `license-files` to PEP 639 i wymaga
setuptools ≥ 77, a teraz wymagane jest `setuptools>=68`. Trzeba podnieść wymaganie
i użyć formy SPDX; dokładne minimum do potwierdzenia przy wdrożeniu, nie z pamięci.
`LICENSE` przy tym pozostaje nietknięty — jest tylko wskazywany.

### Otwarte pytania

1. **Zakres:** kroki 1–3, czy dokładnie te plus krok 4? Rekomendacja: kroki 1–4 i jedna
   linia `opencode.json` do `.gitignore`, bo `opencode.json` jest nieśledzony i nie jest
   zignorowany, więc w publicznym repozytorium wisi jako obcy plik.
2. **Autor do publikacji:** imię i nazwisko oraz e-mail, które mają trafić do
   `authors`. `LICENSE` mówi „Leszek Albrzykowski", ale pakiet nazywa się
   `onto-builder`, a repozytorium `albrzykowski/onto` — decyzja należy do właściciela.
3. **Klasyfikatory:** czy ma być `License :: OSI Approved :: MIT License` obok pola
   `license`, czy samo pole.
4. **CI:** brak `.github/`. Warto dodać przepłyg na trzy udokumentowane kontrole
   (`pytest`, `ruff`, `mypy`), ale dopiero po krokach 1–4. Uwaga: `LD_LIBRARY_PATH`
   z `AGENTS.md` to obejście NixOS-a i nie może trafić do publicznego przepływu.
