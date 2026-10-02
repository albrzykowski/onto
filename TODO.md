# TODO

Scenariusze do dopisania przez autora Gherkina. Agent ich nie pisze — `AGENTS.md`
zabrania edycji plików `.feature`; po ich dodaniu agent przechodzi normalny cykl ATDD.

---

**Legenda statusów użytych w tym pliku:**

- „— do decyzji” = pytanie projektowe, wymaga rozstrzygnięcia przed implementacją
- „— wybrano opcję X” = decyzja podjęta, oczekuje na implementację
- „— zgłoszone przez prawdziwy przebieg” = bug/obserwacja z realnego przebiegu, do potwierdzenia scenariuszem
- brak statusu = scenariusz do dopisania przez autora Gherkina

**Podsumowanie otwartych tematów:**

| Sekcja | Status | Plik | Krótki opis |
|--------|--------|------|-------------|
| Allow-list i normalizacja nazw | Scenariusz | `tbox-generation.feature` | Casing klasy z konfiguracji |
| Excerpt klas i slotów w schemacie | Do decyzji | `tbox-generation.feature` | Czy dodać `source_excerpt` do schematu |
| Batchowanie w obrębie jednego dokumentu | Wybrano opcję 2 | `tbox-generation.feature` | `source_documents` nie przekracza granicy dokumentu |
| chunk_id względny | Scenariusz | `chunking.feature` | Nazwa dokumentu względna do katalogu roboczego |
| Normalizacja wartości slotów | Do decyzji | `abox-generation.feature` | Prefiks vs. osnowa, zgadywać vs. pytać model |
| Prompt instancji nie zna domeny | Zgłoszone | `abox-generation.feature` | Brak domeny w prompcie instancji |
| Adaptery w dostępie programistycznym | Do decyzji | `config-loading.feature` | Fabryka vs. scenariusz vs. nic |
| Typowanie i publikacja | Plan 4-krokowy | `pyproject.toml` | `py.typed`, mypy, pakowanie, metadane |

---


## `features/tbox-generation.feature`

### Allow-list i normalizacja nazw

`_allowed` normalizuje nazwę z konfiguracji, a `_admit` oczekuje znormalizowanej nazwy
kandydatów. Brak scenariusza, który weryfikuje, że klasa dopuszczona w oryginalnym casingu
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
poniżej zakłada annotację `source_excerpt` w wygenerowanej ontologii, co stoi w sprzeczności
z ustalonym kierunkiem: excerpt jest dowodem w `provenance.jsonl`, a nie treścią ontologii —
ten sam argument usunął `source_excerpt` z instancji w `cfffdfc`. Do rozstrzygnięcia, zanim scenariusz
trafi do `features/tbox-generation.feature`.

```gherkin
  Scenario: Classes and slots carry the excerpt they were derived from
    Given the LLM returns the class Vehicle and the relation has_engine from one chunk
    When the T-Box is generated
    Then every class and every slot has a "source_excerpt" annotation with the text it was derived from
```

### Batchowanie w obrębie jednego dokumentu — wybrano opcję 2

`_candidates_of` w `onto/extraction.py:255` przypisuje kandydatowi **każdy chunk z jego batcha**,
co udokumentowuje docstring `extract` (`onto/extraction.py:242-244`): model widział cały batch
na raz, więc precyzję daje dopiero `source_excerpt`. Przy jednym temacie korpusu jest to
nieszkodliwe. Przebieg na trzech dokumentach — dwóch motoryzacyjnych i `Ukladplanetarny.pdf`
(po polsku), `batch_size: 4`, 2026-10-02 — pokazał, że nie:

- batch 1 to: `History_of_the_car.pdf#c1..c3` + `Ukladplanetarny.pdf#c1`,
  batch 2 to: `Ukladplanetarny.pdf#c2` + `When-Was-the-First-Car-Made-...docx.pdf#c1`;
- klasa `Planet` cytuje **wszystkie 6 chunków z 3 dokumentów**, a `Star` 4 chunki, w tym trzy
  motoryzacyjne — mimo że `source_excerpt` obu jest poprawnym polskim tekstem o Układzie
  Słonecznym.

Kandydat może więc wskazać dokument, z którego nic nie pochodzi, a czytelnik logu nie ma
jak tego rozpoznać bez zaglądania do treści, bo wiarygodny jest tylko `source_excerpt`.

**Wybrano opcję 2:** `_batches` ma grupować chunki w obrębie jednego dokumentu. Kandydat wtedy
nigdy nie wskaże obcego dokumentu, a precyzja wraca do poziomu dokumentu, co jest granicą,
poza którą i tak nie schodzimy.

Koszt: liczba zapytań rośnie z liczbą dokumentów, a nie z `batch_size`.
Dziś 6 chunków idzie w 2 batchach, po zmianie w 3 — jeden na dokument. Przy korpusie z 50
dokumentów to +~50 zapytań na build.

Do rozstrzygnięcia przed implementacją: przyjęty scenariusz
`features/tbox-generation.feature:28` ("the source_documents annotation of Vehicle lists all
3 chunks") przypina atrybucję per-batch, a jego `Given` mówi o 3 niezależnych chunkach
bez podania dokumentów. Agent nie edytuje plików `.feature`, więc autor Gherkina musi
zdecydować, czy `Given` ma wskazywać 3 chunki **jednego** dokumentu — wtedy scenariusz
przechodzi bez zmiany oczekiwania — czy 3 dokumenty, a wtedy zmienia się oczekiwanie na
listę jednego chunka. Do rozważenia przy tej samej okazji: `features/update-mode.feature:31`
doprecyzowuje, że `source_documents` klasy jest „extended with the new document”, więc przy
batchowaniu per-dokument ta scena powinna dostać scenariusz na łączenie chunków z różnych
dokumentów.

## `features/chunking.feature`

`chunk_id` powinien być niezależny od bezwzględnej ścieżki. Brak scenariusza sprawdzającego,
że nazwa dokumentu jest względna do katalogu roboczego.

```gherkin
  Scenario: A chunk is named using the document name as seen from the working directory
    Given a document at "corpus/article1.txt" and the working directory is the project root
    When the document is chunked
    Then the first chunk has the chunk id "corpus/article1.txt#c1"
```

## `features/abox-generation.feature`

### Normalizacja wartości slotów — zgłoszone przez prawdziwy przebieg

Przebieg na dwóch PDF-ach (`corpus/History_of_the_car.pdf`,
`corpus/When-Was-the-First-Car-Made-Exploring-the-History-of-the-Automobile.docx.pdf`,
`mistral-small-2603`, 2026-10-02) zapisał 16 instancji i **8 odrzuceń** z powodu
`unresolved_reference`. Odrzucenie jest bezpieczne — fakt nie trafia do ontologii,
a zdarzenie zostaje w `provenance.jsonl` — ale **połowa wartości slotów zniknęła**:
z 12 wartości zapisano tylko 4. Były to dokładnie te, których identyfikator odpowiadał
istniejącej instancji co do znaku:
`DRP_No_37435.protected_by = Karl_Benz`,
`Benz_Patent.protected_by = Karl_Benz`,
`Benz_Patent_Motor_Car_model_No_1.powered_by = gas_engine`,
`Nicolas_Joseph_Cugnot.used_in = Fardier_à_vapeur`.

Reszta rozpadła się na trzy przypadki:

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

1. **Prefiks czy osnowa?** `Ford_Motor_Company` jest poprawnym prefiksem
    `Ford_Motor_Company_Assembly_Line`. Reguła „dopasuj, gdy jeden identyfikator jest prefiksem
    drugiego, a ogon nie wnosi nowego słowa" jest wąska i przewidywalna, ale nie złapie
    `Ford Motor Company` → `Ford_Motor_Company_Assembly_Line`. Dopasowanie po osnowie
    (porównanie `_identifier` obu stron) jest szersze, kosztuje więcej fałszywych trafień
    i zaczyna zgadywać.
2. **Zgadywać czy pytać model?** `onto/dedup.py` ma już ten mechanizm dla nazw klas
    i slotów: `closest_of` po embedderze, `verify_merge` przez LLM, a próg bierze z
    `config.similarity_threshold` (używany w `onto/schema_gen.py:435`).
    Nadanie mu progu dla wartości slotów byłoby spójne z trybem update,
    ale kosztuje dodatkowe wywołanie dla każdej wiszącej wartości.
    KISS przemawia za regułą deterministyczną z punktu 1, bez LLM.
3. **Slot w ogóle nie ma `range`.** W tym buildzie żaden slot nie dostał `range`,
    bo model go nie podał — wszystkie mają `range=None`. Bez `range` nie da się odróżnić
    „wartość ma wskazywać na instancję klasy `InternalCombustionEngine`"
    od „wartość jest nazwą klasy”, czyli przypadku pierwszego z tabeli.
    To decyzja o schemacie, nie o wartości, i zamyka ten przypadek na dłużej niż normalizacja.

Propozycja scenariusza dla przypadku prefiksowego (do napisania przez autora Gherkina):

```gherkin
  Scenario: A slot value that is a prefix of a known instance is resolved to that instance
    Given the LLM returns the instance "Ford Motor Company Assembly Line" of class AssemblyLine
    And the LLM returns the instance "Highland Park Michigan plant" of class AssemblyLine
    And the LLM gives the second instance with a "manufactured_by" slot with value "Ford Motor Company"
    When the A-Box is generated
    Then the instance Highland_Park_Michigan_plant has a "manufactured_by" slot with value Ford_Motor_Company_Assembly_Line
    And no event "instance.rejected" with the reason "unresolved_reference" is recorded
```

Dla pierwszego przypadku z tabeli scenariusza nie ma, dopóki punkt 3 nie zostanie rozstrzygnięty:
dziś nie wiadomo, czy slot ma obowiązek wskazywać na instancję.

### Prompt instancji nie zna domeny — zgłoszone przez prawdziwy przebieg

`onto/instance_gen.py:117` (`_prompt`) składa cztery sekcje: instrukcje, listę klas schematu,
kontrakt wyjścia i tekst źródłowy. **Domeny nie ma wcale** — słowo `domains` nie występuje
w tym module. Ekstrakcja klas ją ma (`_scope` w `onto/extraction.py`), i dlatego T-Box
w przebiegu z 2026-10-02 trzymał tylko 6 klas astronomicznych: dwa dokumenty motoryzacyjne
wydały zero kandydatów klas. Ta sama rozbieżność po stronie instancji dała 19 instancji,
z czego **10 motoryzacyjnych sklasyfikowanych jako obiekty astronomii**:

| instancja | klasa |
| --- | --- |
| `Model_T`, `Curved_Dash_Oldsmobile`, `Motorwagen` | `Planet` |
| `Ford_Motor_Company`, `Benz_Patent_Motor_Car_model_No_1` | `Star` |
| `Gottlieb_Daimler`, `Karl_Benz`, `Mercedes` | `Moon` |
| `Cannstatt_Daimler` | `DwarfPlanet` |
| `American_gasoline_automobile` | `Asteroid` |

Instrukcja mówi „Use only the classes and slots listed below; invent nothing”,
czyli model **musi** wybrać jedną z 6 klas, ale nigdzie nie ma
„a jeśli tekst jest spoza domeny, zwróć pustą listę”.
Jedyna bramka, `not_in_tbox`, sprawdza, czy klasa **istnieje**, a nie czy pasuje do domeny —
`Planet` istnieje, więc przepuszcza. Sloty tych instancji zostały odrzucone jako
`unresolved_reference`, więc przetrwały jako puste skorupy: nazwa, klasa, opis, zero slotów.
`not_in_tbox` zadziałał tam, gdzie model odmówił wrócić klasy spoza schematu (10 odrzuceń),
i nie zadziałał tam, gdzie klasa istniała, lecz była niezgodna z domeną.

To łamie obietnicę z `AGENTS.md` wprost, tylko w drugą stronę:
„An `automotive` prompt must never yield `Recipe`" — tutaj prompt `solar_system` wyprodukował
`Model_T` jako `Planet`.

**Proponowana naprawa:** wstrzyknąć domenę do promptu instancji przez `_scope(config)`
z `onto/extraction` oraz dodać regułę „tekst spoza domen → `"instances": []`”.
Bez nowej zależności: `instance_gen` już importuje z `extraction`
(`described_by_chunk`, `merge_descriptions`), a `_Answer.instances` ma `default_factory=list`,
więc pusta odpowiedź przechodzi walidację bez zmian w kodzie poza promptem.

Do rozstrzygnięcia przed wdrożeniem: dziedzina i prompt to dwie niezależne sprawy.
Dodanie domeny `automotive` do `config.yaml` czyni chunki motoryzacyjne w obrębie domen,
ale nie uczy modelu, że tekst spoza domeny ma dawać pustą listę — ten sam wyciek
wróci przy pierwszym dokumencie spoza tematu. Samo wstrzyknięcie domeny do promptu
wystarczy, ale wtedy oba tematy w jednej ontologii nadal nie powstaną,
dopóki `config.yaml` nie wymieni obu.

Propozycja scenariusza (do napisania przez autora Gherkina):

```gherkin
  Scenario: A chunk outside the configured domains yields no instances
    Given a configuration with the domain "solar_system" describing the Solar System
    And a chunk from a document about the history of the car
    And the LLM is asked for instances
    When the A-Box is generated
    Then no instance is created
    And the instance "Model T" is not written
```

Do rozważenia przy tej samej okazji: czy pusta odpowiedź ma być zdarzeniem
(`chunk.rejected` albo `instance.rejected` bez `id`), czy ma być ciszą.
Dziś jest ciszą, a z logu nie da się odróżnić „ten chunk nie dotyczył domeny”
od „model nic nie znalazł”.

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

To dokładnie ten drift, który zgłosiło `157de4f`: przykład zbudował `MistralLLM()` bez klucza,
CLI przekazał `api_key=config.api_key`, żądanie wyszło bez poświadczeń, a Mistral odpowiedział
`Invalid API Key` — tak samo jak zły klucz i jak klucz właśnie rotowany. `a54c057` poprawił
przykład, ale nic nie pilnuje, żeby znowu się nie rozjechał. Ochronna notatka w README
(„Pass `api_key=config.api_key` to the adapter.”) jest tylko tekstem; jedyne, co jest przypięte,
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
- `LICENSE` to MIT. **Pliku nie wolno zmieniać** — tylko wskazywać go z `pyproject.toml`.
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

1. **Zakres:** kroki 1–3 czy też krok 4? Rekomendacja: kroki 1–4 oraz dodanie
    `opencode.json` do `.gitignore`, bo plik jest nieśledzony i nie jest zignorowany,
    więc w publicznym repozytorium wisi jako obcy plik.
2. **Autor do publikacji:** imię, nazwisko oraz e-mail do pola `authors`. Pakiet nazywa się
    `onto-builder`, a repozytorium `albrzykowski/onto` — decyzja należy do właściciela.
3. **Klasyfikatory:** czy dodać `License :: OSI Approved :: MIT License` obok pola `license`,
    czy wystarczy samo pole.
4. **CI:** brak `.github/`. Warto dodać przepływ na trzy kontrole (`pytest`, `ruff`, `mypy`),
    ale dopiero po krokach 1–4. Uwaga: `LD_LIBRARY_PATH` z `AGENTS.md` to obejście
    specyficzne dla NixOS-a i nie może trafić do publicznego przepływu.

