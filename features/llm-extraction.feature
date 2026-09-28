Feature: Extracting concepts with the LLM
  As a library
  I want to call the LLM on chunks to extract candidate classes, relations, and instances
  So that an ontology can be built from them

  Scenario: Extracting candidates from a chunk
    Given a chunk with the text "The 1.6 TDI engine is installed in the Golf produced by VW"
    And the LLM returns the candidates Vehicle, Engine, Manufacturer and the relations has_engine, produced_by
    When extraction is performed for the chunk
    Then the result contains the class candidates Vehicle, Engine, Manufacturer
    And the result contains the relation candidates has_engine, produced_by
    And every candidate carries a "source_documents" reference with the chunk identifier
    And every candidate carries the text excerpt it was derived from

  Scenario: English names regardless of source language
    Given a chunk in Polish containing domain concepts
    And the LLM returns candidates with English names
    When extraction is performed
    Then every class candidate has a PascalCase name
    And every relation candidate has a snake_case name

  Scenario: The prompt constrains the LLM to allowed classes and relations
    Given a configuration with domains [automotive]
    And allowed_classes [Vehicle, Engine]
    And allowed_relations [has_engine]
    When extraction is performed
    Then the LLM prompt lists the domains and the predefined classes Vehicle and Engine
    And the LLM prompt lists the predefined relation has_engine
    And the prompt instructs the LLM to return only these concepts and nothing else
    And the LLM returns exactly the classes Vehicle and Engine and the relation has_engine

  Scenario: The prompt scopes the LLM to domains without allow-lists
    Given a configuration with domains [automotive]
    And empty allowed_classes and allowed_relations
    And the domain "automotive" is described as "Passenger and commercial vehicles and their components"
    When extraction is performed
    Then the LLM prompt contains the domain name and its description
    And the prompt instructs the LLM to extract concepts relevant to the automotive domain
    And the LLM returns only automotive concepts such as Vehicle

  Scenario: The LLM decides freely when nothing is scoped
    Given a configuration with no domains and empty allow-lists
    When extraction is performed
    Then the LLM prompt does not constrain the set of concepts
    And the LLM returns the concepts it judged significant

  Scenario: Batching LLM calls
    Given a configuration with batch_size 2
    And 5 chunks to process
    When extraction is performed for all chunks
    Then the LLM is called exactly 3 times (batches of 2, 2, 1)

  Scenario: An LLM error for one chunk does not abort the build
    Given 2 chunks
    And the LLM fails for the first chunk
    When extraction is performed
    Then the result contains candidates from the second chunk
    And an error for the first chunk is logged
