# TODO

Scenariusze do dopisania przez autora Gherkina. Agent ich nie pisze — `AGENTS.md`
zabrania edycji plików `.feature`; po ich dodaniu agent przechodzi normalny cykl ATDD.

## `features/config-loading.feature` — klucz wędruje do adaptera

`api_key` i `embedding_api_key` są obowiązkowe i niepuste, a `onto/cli.py:llm_for` oraz
`embedder_for` przekazują je do adapterów. Nic nie pilnuje, że klucz faktycznie wędruje:
regresja wyglądałaby jak zły klucz, zrotowany klucz i klucz w ogóle nieprzekazany —
trzy różne awarie, jeden komunikat błędu (`Invalid API Key`).

```gherkin
  Scenario: The two keys reach their own adapters
    Given the configuration has model "openai/gpt-4o" and api_key "sk-openai"
    And the configuration has embedding_model "mistral/mistral-embed" and embedding_api_key "sk-mistral"
    When the adapters are built for the run
    Then the LLM adapter is given the key "sk-openai"
    And the embedder adapter is given the key "sk-mistral"
```

Warto przy okazji przypiąć, że model i embedding mogą należeć do **różnych** providerów —
to jedyna sytuacja, w której drugi klucz jest potrzebny, a bez scenariusza ktoś uzna
`embedding_api_key` za duplikat i go usunie.

LiteLLM daje jawnie podanemu `api_key` pierwszeństwo nad `OPENAI_API_KEY` ze środowiska
(zmierzone), więc przypisanie z konfiguracji działa — ale warto to przypiąć, zanim ktoś
uzna, że klucz można zostawić w środowisku.

## `features/llm-extraction.feature` — ucięta odpowiedź

`max_concepts_per_batch` ogranicza liczbę pojęć na partię, ale nic nie pilnuje, że LLM faktycznie
domknął odpowiedź. Przy zbyt małym `max_tokens` model zwraca `finish_reason: "length"` i
`read_json` zwraca surowy tekst — cudzysłowy, nawias, wszystko — a `extraction` loguje to jako
zwykły błąd odczytu. Taki run wygląda na „wyciął zdanie”, choć przyczyna jest w konfiguracji.

Scenariusz ma dwa liczne uzasadnienia. Po pierwsze, błędy JSON z partii są dziś nierozróżnialne
od tych spowodowanych ucięciem, więc diagnostyka kłamie. Po drugie, to jedyna sytuacja, w której
`max_concepts_per_batch` i `max_tokens` wchodzą w konflikt — limit pojęć chroni przed długą
odpowiedzią, a `max_tokens` może ją uciąć mimo to.

```gherkin
  Scenario: A reply cut off at the token limit is not taken for an answer
    Given a document chunk about vehicle engines
    And the model is given max_tokens of 64
    And the model replies with the class "Engine" and stops at the token limit
    When extraction runs for that chunk
    Then an error names the chunk as cut off
    And the truncated reply is not parsed as concepts
```

Implementacja, gdy scenariusz będzie zaakceptowany: `LiteLLMLLM.complete` sprawdza
`finish_reason` i rzuca `LLMError`, gdy jest równy `"length"`. Osobna wiadomość, nie ogólna —
`extraction` już loguje per chunk, więc różnica w tekście błędu wystarczy, żeby odróżnić
ucięcie od złego JSON-a.

## `features/tbox-generation.feature` — allow-list porównuje dwie formy nazwy

`_allowed` normalizuje nazwę **z konfiguracji** (`vehicle` → `Vehicle`), a `_admit` polega na
tym, że `onto/extraction.py` zdążył znormalizować nazwę **kandydata**. Działa, bo obie strony
spotykają się w tej samej formie — ale zależność jest ni widoczna w sygnaturach, ani
udokumentowana kontraktem. Gdyby kiedykolwiek `Candidate` powstał z nazwy nieznormalizowanej
(np. walidacja, inny caller `generate_tbox`), zostałby **po cichu odrzucony**: allow-list
wyglądałby na pusty, a schema cicho pusta byłaby konsekwencją czegoś, czego nikt nie pisał.

```gherkin
  Scenario: A concept allowed in the configuration's own casing is written
    Given a configuration with allowed_classes containing the class "vehicle"
    And the LLM has returned the class candidate "vehicle"
    When the T-Box is generated
    Then the class Vehicle is in the schema
    And no class is logged as rejected
```

Warto przy okazji przypiąć drugą stronę: klasa spoza allow-list **nie** trafia do schematu
i jest zalogowana jako `class.rejected` z `reason: not_in_allowed_classes`. Dziś to jedyna
droga, którą da się sprawdzić, że allow-list jest egzekwowany, a nie tylko wklejony do promptu.

## `features/tbox-generation.feature` — klasa wskazuje slot, którego nie ma

Klasa dostaje tylko te sloty, które faktycznie trafiły do schematu, a `allowed_relations`
decyduje, które to są. Ścieżka jest egzekwowana, ale nieprzypięta — brak scenariusza, który
przepuściłby slot odrzucony przez allow-list do `Vehicle.slots`. Schema wskazywałaby wtedy na
slot, którego w niej nie ma, a walidacja LinkML tego nie zauważa.

```gherkin
  Scenario: A class is assigned only the slots the schema has
    Given a configuration with allowed_relations containing the relation "has_engine"
    And the LLM has returned the class candidate "Vehicle" and the relations "has_engine", "has_wheel"
    When the T-Box is generated
    Then the class Vehicle has the slot "has_engine" only
    And a "slot.rejected" event with the reason "not_in_allowed_relations" is recorded for has_wheel
```

## `features/abox-generation.feature` — zapisana instancja znika z logu

Log zapisywał wyłącznie odrzucenia. Klasa ma `class.created` i `class.updated` od pierwszej
fazy naprawczej, a instancja nie miała **żadnego** eventu o zapisaniu — choć `AGENTS.md`
wymaga, by każda zmiana ontologii niosła provenance, a log był jedynym miejscem, które o
zapisanej instancji milczało. Do dopisania są trzy rzeczy, które dziś zweryfikowano tylko
ad hoc:

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

Ostatni scenariusz chroni przed utratą danych, nie przed awarią: `_identifier` sprowadza
nazwy do jednego tokenu, więc dwie różne nazwy trafiają pod ten sam klucz i druga po cichu
nadpisywała pierwszą. Dziś ta druga jest odrzucana i logowana, ale bez scenariusza
nadpisanie wygląda identycznie jak „model nie znalazł drugiej encji”.

## `features/chunking.feature` — nazwa dokumentu nie zależy od katalogu

`chunk_id` powstajeł ze ścieżki, pod którą build został wywołany, więc bezwzględne `--input`
zapisywało układ katalogów maszyny do `schema.yaml` i `provenance.jsonl`, a ten sam korpus
dawał inny schema z innego katalogu. `document_name` nazwywa dokument względem katalogu
roboczego, a `provenance-logging.feature` oraz README już twierdziły `corpus/article1.txt` —
to tylko nie dochodziło.

```gherkin
  Scenario: A chunk is named after the document as the working directory names it
    Given a document at "corpus/article1.txt" and the working directory is the project root
    When the document is chunked
    Then the first chunk has the chunk id "corpus/article1.txt#c1"
```

Do przypięcia jest też granica tej reguły: dokument **poza** katalogiem roboczym nie ma nazwy
względnej, więc `document_name` zwraca ścieżkę podaną i `onto build --input /data/corpus`
zapisze `/data/corpus/article1.txt#c1`. To jest świadomy wybór — względem `input_dir` wyszłoby
`article1.txt`, co przeczyłoby temu, co feature i README już obiecują. Warto jednak przypiąć
zachowanie dla katalogu poza roboczym, żeby przyszła refaktoryzacja nie uznała go za błąd.

Timeout i ponowienia z `onto/llm_litellm.py` celowo **nie** mają scenariusza: to zachowanie
adaptera, który w tym repozytorium nie ma kontraktu Gherkin i jest testowany jednostkowo
(`tests/test_llm_adapters.py`, `tests/test_embedding_adapters.py`).

## `features/abox-generation.feature` — slot wskazujący na niezapisaną encję

**Ten punkt jest zablokowany przez inny scenariusz w tym samym pliku i wymaga decyzji autora
przed jakąkolwiek zmianą w kodzie.**

Wartość slotu jest zapisywana jako id instancji, na którą wskazuje. Nic nie pilnuje, że taka
instancja istnieje, więc `The_Golf.has_engine: 1_6_TDI` powstaje nawet wtedy, gdy `1_6_TDI`
nigdzie nie trafiło do `instances.yaml`. Schema deklaruje zakres jako `string`, więc walidacja
LinkML to przepuszcza, a `abox-generation.feature` („Instances validated against the schema")
nie zauważa. Wyjątek ten sam co w A-Boksie: encja jest w excerptcie, który zapisujemy, więc
nic nie ginie poza właściwym połączeniem.

Nie da się tego naprawić bez zmiany kontraktu, bo `features/abox-generation.feature:12`
wprost wymaga zapisania wiszącej wartości:

```gherkin
    And the LLM returns the instance "VW Golf" of class Vehicle with has_engine pointing to "1.6 TDI"
    ...
    And the instance has the slot has_engine with the value "1_6_TDI"
```

Jedna instancja w scenariuszu, `1_6_TDI` nie jest żadną instancją — feature nakazuje zapisać
dokładnie ten przypadek, który chcemy upuszczać. Osłabienie asercji w
`features/steps/abox_generation_steps.py:164` byłoby obejściem tego sameco rodzaju co edycja
`.feature`, tylko bez nazwy.

Do rozstrzygnięcia są dwa scenariusze i T-Box, bo encja, na którą slot wskazuje, musi mieć
klasę, inaczej zostanie odrzucona jako spoza T-Boxu:

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

Implementacja po zaakceptowaniu, w `onto/instance_gen.py`: `_merge` zna zbiór id dopiero po
dodaniu wszystkich instancji, więc rozstrzyganie musi być drugim przebiegiem — wartość wskazująca
na instancję znalezioną w późniejszym chunku nie jest wisząca. Upuszczenie dotyczy tylko
instancji zapisywanych po raz pierwszy: wpis już istniejący zachowuje sloty, które ustanowił
wcześniejszy build, a nowe wartości i tak do niego nie dochodzą. Zdarzenie dostanie dwa opcjonalne
pola, `slot` i `value` — bez nich log mówiłby, że coś wypadło, ale nie co i którego slotu dotyczyło;
`ProvenanceEvent` serializuje z `exclude_none=True`, więc pozostałe linie pozostaną bajt w bajt
takie same.

## `onto/schema_gen.py` — zdarzenie i excerpt dla slotu

Znalezione przy pierwszym uruchomieniu udokumentowanego quick startu (`onto build`, potem
`onto update` z drugim katalogiem, w obu przypadkach wyjście 0). Oba przebiegi zachowują się
tak samo i dowód jest w ich wyniku, nie w domysłach: `schema.yaml` zawiera slot `has_engine`
zapisany przez oba tryby, a `provenance.jsonl` po obu przebiegach ma `class.created`,
`instance.created`, `class.updated`, `instance.updated` — i **żadnego** zdarzenia slotu.

**1. Slot utworzony z ekstrakcji nie jest w ogóle zgłaszany.** `onto/schema_gen.py` zna
`_SLOT_UPDATED` (`features/update-mode.feature:53` to pilnuje), ale nie zna `_SLOT_CREATED`.
Slot nadchodzący z ekstrakcji jest zapisywany do `schema.yaml` w `generate_tbox` (linia ~310)
bez ani jednej linii w logu. Czytelnik logu nie dowiaduje się, że slot istnieje ani skąd
przyszedł, a `AGENTS.md` wymaga provenance dla każdej zmiany ontologii — klasy, **slotu**
i instancji.

**2. T-Box nie zapisuje excerptu, A-Box zapisuje.** Sprawdzone na tym samym przebiegu:

| element | annotation w YAML |
|---|---|
| klasa `Vehicle` | `source_documents` |
| slot `has_engine` | `source_documents` |
| instancja `VW_Golf` | `source_documents`, `source_excerpt` |

Excerpt jest w zasięgu — `schema_gen.py` już przekazuje `source_excerpt=excerpt` do
`log.record`, tylko nie zapisuje go w schemacie. `AGENTS.md` każe, żeby każda zmiana
niosła „source document path, chunk id **and the source text excerpt**”, a
`features/tbox-generation.feature:19-22` wymaga przy klasie tylko `source_documents`, zaś
`features/abox-generation.feature:27` przy instancji wymaga wszystkich trzech. **Umowa
i `AGENTS.md` mówią tu różne rzeczy** i to rozstrzyga, którą stronę poprawić.

Proponowane scenariusze — pierwszy domyka dziurę w logu, drugi wyrównuje T-Box z A-Boxem:

```gherkin
  Scenario: Slot creation is logged with its source excerpt
    Given the LLM returns the class Vehicle and the relation has_engine from one chunk
    When the T-Box is generated
    Then an "slot.created" event for has_engine is recorded with the chunk and the excerpt

  Scenario: Classes and slots carry the excerpt they were derived from
    Given the LLM returns the class Vehicle and the relation has_engine from one chunk
    When the T-Box is generated
    And every class and every slot has a "source_excerpt" annotation with the text it was derived from
```

Nazwy zdarzeń są już w `_MERGED`/`_CREATED`/`_UPDATED`/`_SLOT_UPDATED` i tworzą
`class.merged`, `class.created`, `class.updated`, `slot.updated` — brakuje tylko
`slot.created` i `_SLOT_UPDATED` używa innego sufiksu niż reszta, więc przy okazji warto
je ujednolicic.

Uwaga obok, nie defekt: slot `has_engine` wylądował na poziomie schematu, a klasa `Vehicle`
ma `slots: []`. Wyciągnięta relacja nie została przypisana do klas, z których korpus ją
łączy. To zależy od tego, co model zwróci, i nie da się tego stwierdzić bez scenariusza
o tym, gdzie relacja ma trafić — dlatego jako pytanie, nie jako pozycja do naprawy.
