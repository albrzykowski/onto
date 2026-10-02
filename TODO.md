# TODO

Scenariusze do dopisania przez autora Gherkina. Agent ich nie pisze — `AGENTS.md`
zabrania edycji plików `.feature`; po ich dodaniu agent przechodzi normalny cykl ATDD.

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

### Excerpt klas i slotów w schemacie — do decyzji

`schema.yaml` zapisuje dla klas i slotów tylko `source_documents`, bez excerptu. Scenariusz
poniżej chce annotacji `source_excerpt` w wygenerowanej ontologii, co stoi w sprzeczności
z ustalonym kierunkiem: excerpt jest dowodem w `provenance.jsonl`, a nie treścią ontologii —
ten sam argument usunął excerpt z instancji w `cfffdfc`. Do rozstrzygnięcia, zanim scenariusz
trafi do `features/tbox-generation.feature`.

```gherkin
  Scenario: Classes and slots carry the excerpt they were derived from
    Given the LLM returns the class Vehicle and the relation has_engine from one chunk
    When the T-Box is generated
    Then every class and every slot has a "source_excerpt" annotation with the text it was derived from
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

## `features/abox-generation.feature`

### Normalizacja wartości slotów — zgłoszone przez prawdziwy przebieg

Przebieg na dwóch PDF-ach (`corpus/History_of_the_car.pdf`,
`corpus/When-Was-the-First-Car-Made-Exploring-the-History-of-the-Automobile.docx.pdf`,
`mistral-small-2603`, 2026-10-02) zapisał 16 instancji i **8 odrzuceń** powodu
`unresolved_reference`. Odrzucenie jest bezpieczne — fakt nie trafia do ontologii, a zdarzenie
zostaje w `provenance.jsonl` — ale **połowa wartości slotów zniknęła**: tylko 4 z 12 zostały
zapisane. Te 4 to dokładnie te wartości, których identyfikator odpowiadał istniejącej instancji
co do znaku (`DRP_No_37435.protected_by = Karl_Benz`, `Benz_Patent.protected_by = Karl_Benz`,
`Benz_Patent_Motor_Car_model_No_1.powered_by = gas_engine`,
`Nicolas_Joseph_Cugnot.used_in = Fardier_à_vapeur`). Reszta rozpadła się na trzy przypadki:

| wartość w slocie | wskazywa na | przykład |
| --- | --- | --- |
| nazwę **klasy**, nie instancji | `InternalCombustionEngine`, `Automobile` | `Model_T`, `George_Selden` |
| **prefiks** istniejącej instancji | `Ford_Motor_Company` przy jedynej instancji `Ford_Motor_Company_Assembly_Line` | `Highland_Park_Michigan_plant` |
| encję, której korpus nigdy nie opisuje | `military_tractor`, `steam_powered_land_vehicle` | `Fardier_à_vapeur`, `Oliver_Evans` |

Trzeci przypadek **nie jest** problemem normalizacji: encji nie ma w korpusie, więc nie ma na co
zamienić referencji, a zgadywanie instancji byłoby fabrykowaniem faktu — obecne odrzucenie jest
właściwą odpowiedzią. Drugi przypadek jest najczystszym kandydatem: różnica to jedno słowo, a
instancja, do której wartość pasuje, jest już w A-Boksie.

Do rozstrzygnięcia zanim scenariusz trafi do `features/abox-generation.feature`:

1. **Prefiks, czy osnowa?** `Ford_Motor_Company` jest poprawnym prefiksem
   `Ford_Motor_Company_Assembly_Line`. Reguła „dopasuj, gdy jeden identyfikator jest prefiksem
   drugiego, a ogon nie wnosi nowego słowa" jest wąska i przewidywalna, ale nie złapie
   `Ford Motor Company` → `Ford_Motor_Company_Assembly_Line`. Dopasowanie po osnowie
   (`_identifier` na obu) jest szersze, kosztuje więcej fałszywych trafień i zaczyna zgadywać.
2. **Zgadywać, czy pytać model?** `onto/dedup.py` ma już dokładnie ten mechanizm dla nazw klas
   i slotów: `closest_of` po embedderze, `verify_merge` przez LLM, a próg bierze z
   `config.similarity_threshold` (używany w `onto/schema_gen.py:435`). Nadanie mu progu dla
   wartości slotów byłoby spójne z trybem update, ale kosztuje dodatkowe wywołanie dla każdej
   wiszącej wartości. KISS przemawia za regułą deterministyczną z punktu 1, bez LLM.
3. **Slot w ogóle nie ma `range`.** W tym buildzie żaden slot nie dostał range, bo model go nie
   podał — wszystkie pięć ma `range=None`. Bez range nie da się odróżnić „wartość ma wskazywać na
   instancję klasy `InternalCombustionEngine`" od „wartość jest nazwą klasy", czyli przypadku
   pierwszego z tabeli. To decyzja o schemacie, nie o wartości, i zamyka ten przypadek na
   dłużej niż normalizacja.

Propozycja scenariusza dla przypadku prefiksowego (do napisania przez autora Gherkina):

```gherkin
  Scenario: A slot value that prefixes a known instance is resolved to that instance
    Given the LLM returns the instance "Ford Motor Company Assembly Line" of class AssemblyLine
    And the LLM returns the instance "Highland Park Michigan plant" of class AssemblyLine
    And the LLM gives the second instance "manufactured_by" pointing to "Ford Motor Company"
    When the A-Box is generated
    Then the instance Highland_Park_Michigan_plant has "manufactured_by" with the value Ford_Motor_Company_Assembly_Line
    And no event "instance.rejected" with the reason "unresolved_reference" is recorded
```

Na przypadek pierwszy z tabeli scenariusza nie ma, dopóki punkt 3 nie zostanie rozstrzygnięty:
dziś nie wiadomo, czy slot ma w ogóle obowiązek wskazywać na instancję.

## Uwagi

- Timeout i ponowienia z `onto/llm_litellm.py` celowo nie mają scenariusza: to zachowanie
  adaptera, który jest testowany jednostkowo (`tests/test_llm_adapters.py`,
  `tests/test_embedding_adapters.py`).

## Adaptery w dostępie programistycznym

`features/adapter-wiring.feature` pilnuje jednej ścieżki: `onto/cli.py`. `llm_for(config)`
i `embedder_for(config)` przekazują `config.api_key` i `config.embedding_api_key`, a testy
jednostkowe przypinają, że adapter przekazuje klucz do `litellm.completion`. Ścieżka
programistyczna nie ma fabryki — README każe czytelnikowi złożyć adapter ręcznie:

```python
llm = LiteLLMLLM(api_key=config.api_key)
build(input_dir=Path("corpus"), output_dir=Path("ontology"), config=config, llm=llm)
```

To dokładnie drift, który zgłosiło `157de4f`: przykład zbudował `MistralLLM()` bez klucza,
CLI przekazał `api_key=config.api_key`, żądanie wyszło bez poświadczeń, a Mistral odpowiedział
`Invalid API Key` — tak samo jak zły klucz i jak klucz właśnie rotowany. `a54c057` poprawił
przykład, ale nic nie pilnuje, żeby znowu się nie rozjechał. Ochronna notatka w README
(`Pass api_key=config.api_key to the adapter.`) jest tylko tekstem; jedyne, co jest przypięte,
to ścieżka CLI.

Trzy możliwości, żeby zamknąć:

1. **Fabryka w bibliotece.** `onto.llm_litellm.factory(config)` i `onto.embeddings.factory(config)`
   obok `LLM` i `Embedder`; `onto/cli.py` przestaje składać adaptery sam i woła je. README
   pokazuje tę samą funkcję. Jedna ścieżka konstrukcji, brak możliwości rozjazdu — kosztem dwóch
   nowych publicznych funkcji i zależności `litellm` od `BuilderConfig` (dziś
   `onto/llm_litellm.py` zna tylko `CompletionRequest`).
2. **Scenariusz na ścieżce programistycznej.** Bez nowej fabryki: krok w `config-loading.feature`
   uruchamia `build()` z dokumentu i sprawdza klucz na wywołaniu `litellm.completion`. Pilnuje
   przykładu, nie API.
3. **Nic.** Zostaje notatka w README i ryzyko, które już raz wystąpiło.

Rekomendacja: 1. Powód jest ten sam, dla którego powstało `features/adapter-wiring.feature` —
pomiary przypięte są tylko tam, gdzie jest jedna ścieżka konstrukcji, a `cli.py` jest jedynym
miejscem, które obiecuje, że klucz z konfiguracji dociera do providera.

Do rozstrzygnięcia przed wdrożeniem: czy `factory` ma przyjmować cały `BuilderConfig` (i sama
wybiera `model` i `api_key`), czy model i klucz osobno — pierwsze to mniej argumentów dla
użytkownika, drugie nie wiąże `onto/llm_litellm.py` z `BuilderConfig`.

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

-------------------------------------- DODANE PRZEZ UŻYTKOWNIKA -----------------------

Zadanie 1:

Poprawki w README.md:

- W README.md jest konfiguracja dla NiXOS, to niedopuszczalne. Opis musi byc krosssystemowy. 
- Paragraf: "Measured on litellm 1.103.1: (...) " - do usuniecia
- Mowa jest o adapterach ale nie ma wytłumaczenia co to jest.
- config.yaml w README powinien być z komentarzami takimi jak w config.example.yaml
- Sprawdż aktualonośc pliku
- Sprawdź logiczną spójność
- Poziom angielskiego B1/B2
- Odbiorcami mogą być DataScietnist a nie programiści, nie może być zbyt skomplikowany technicznie 