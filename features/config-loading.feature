Feature: Loading and validating YAML configuration
  As a developer
  I want to configure the ontology build with a YAML file
  So that the ontology is scoped to the domains, classes, and relations I state

  Every field of the configuration is required. A build that names no domain states
  nothing about what the ontology is for, and the model left to guess produces a narrow
  ontology that looks like a successful build. The two allow-lists are the exception: they
  may be empty, which is a deliberate "no allow-list" rather than a missing key.

  Scenario: Loading a full configuration
    Given a configuration file "config.yaml" containing:
      | domains            | {automotive: "Passenger and commercial vehicles and their components", supply_chain: "Suppliers, logistics and assembly of automotive parts"} |
      | allowed_classes    | {Vehicle: "A motorized road vehicle", Engine: "A machine converting fuel into motion"} |
      | allowed_relations  | {has_engine: "Links a vehicle to its engine"} |
      | mode               | update |
      | model              | mistral/mistral-large-latest |
      | embedding_model    | mistral/mistral-embed |
      | api_key            | "sk-test-key" |
      | embedding_api_key  | "sk-test-embed-key" |
      | chunking_strategy  | fixed |
      | max_chunk_tokens   | 2000 |
      | overlap_tokens     | 200 |
      | batch_size         | 4 |
      | max_concepts_per_batch | 5 |
      | similarity_threshold   | 0.85 |
    When the configuration is loaded
    Then the BuilderConfig contains the domain "automotive" with the description "Passenger and commercial vehicles and their components"
    And the BuilderConfig contains the domain "supply_chain" with the description "Suppliers, logistics and assembly of automotive parts"
    And the allowed classes contain "Vehicle" with its description and "Engine" with its description
    And the allowed relations contain "has_engine" with its description
    And the operating mode is "update"
    And the model is "mistral/mistral-large-latest"
    And the embedding model is "mistral/mistral-embed"
    And the chunking strategy is "fixed"
    And max_chunk_tokens is 2000, overlap_tokens is 200, batch_size is 4
    And max_concepts_per_batch is 5 and similarity_threshold is 0.85

  Scenario: An empty domains mapping is rejected
    Given a configuration file with an empty "domains" mapping
    When the configuration is loaded
    Then a ConfigValidationError is raised

  Scenario: Every domain must carry a description
    Given a configuration file with the domain "automotive" having an empty description
    When the configuration is loaded
    Then a ConfigValidationError is raised

  Scenario: Empty allow-lists are valid
    Given a configuration file with all required fields
    And allowed_classes set to an empty mapping
    And allowed_relations set to an empty mapping
    When the configuration is loaded
    Then the allowed classes list is empty
    And the allowed relations list is empty

  Scenario: A class on an allow-list must carry a description
    Given a configuration file with allowed_classes containing the class "Vehicle" without a description
    When the configuration is loaded
    Then a ConfigValidationError is raised

  Scenario: A relation on an allow-list must carry a description
    Given a configuration file with allowed_relations containing the relation "has_engine" without a description
    When the configuration is loaded
    Then a ConfigValidationError is raised

  Scenario Outline: An invalid field value is rejected
    Given a configuration file with the field "<field>" set to "<value>"
    When the configuration is loaded
    Then a ConfigValidationError is raised

    Examples:
      | field             | value             |
      | mode              | invalid_mode      |
      | chunking_strategy | invalid_strategy  |

  Scenario Outline: A missing required field is rejected
    Given a configuration file with every required field except "<field>"
    When the configuration is loaded
    Then a ConfigValidationError is raised with a message naming "<field>"

    Examples:
      | field                  | note                  |
      | domains                | scoping               |
      | allowed_classes        | allow-list            |
      | allowed_relations      | allow-list            |
      | mode                   | mode                  |
      | model                  | chat model            |
      | embedding_model        | embedding model       |
      | api_key                | key                   |
      | embedding_api_key      | key                   |
      | chunking_strategy      | splitting             |
      | max_chunk_tokens       | splitting             |
      | overlap_tokens         | splitting             |
      | batch_size             | extraction            |
      | max_concepts_per_batch | extraction            |
      | similarity_threshold   | deduplication         |
