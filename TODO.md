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
