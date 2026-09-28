Feature: Loading and validating YAML configuration
  As a developer
  I want to configure the ontology build with a YAML file
  So that I can scope the ontology to given domains, classes, and relations

  Scenario: Loading a full configuration
    Given a configuration file "config.yaml" containing:
      | domains           | [automotive, supply_chain]  |
      | allowed_classes   | [Vehicle, Engine]           |
      | allowed_relations | [has_engine]                |
      | mode              | update                      |
    When the configuration is loaded
    Then the BuilderConfig contains domain "automotive"
    And the allowed classes contain "Vehicle" and "Engine"
    And the allowed relations contain "has_engine"
    And the operating mode is "update"

  Scenario: Domains carry descriptions
    Given a configuration file with a domain "automotive" described as "Passenger and commercial vehicles and their components"
    When the configuration is loaded
    Then the domain "automotive" has the description "Passenger and commercial vehicles and their components"

  Scenario: Default values for a minimal configuration
    Given a configuration file containing only "mode: override"
    When the configuration is loaded
    Then the domain list is empty
    And the allowed classes list is empty
    And the allowed relations list is empty
    And the chunking strategy is "fixed"
    And the similarity threshold is 0.85

  Scenario: Rejecting an invalid configuration
    Given a configuration file with "mode: invalid_mode"
    When the configuration is loaded
    Then a ConfigValidationError is raised

  Scenario: API key from environment variable
    Given the environment variable ANTHROPIC_API_KEY has the value "sk-ant-test"
    When the configuration is loaded
    Then the LLM client is initialized with the key "sk-ant-test"

  Scenario: Missing API key
    Given the environment variable ANTHROPIC_API_KEY is not set
    And the configuration does not contain an api_key
    When the configuration is loaded
    Then a MissingAPIKeyError is raised
