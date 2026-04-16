Feature: Entity Extraction

  As a knowledge engineer of the ontology pipeline,
  I want structured entities and relations to be extracted from text,
  So that I can build a structured knowledge graph.

  Background:
    Given the LLM API is configured with a valid API key
    And the document processing pipeline is operational

  @extraction @entities
  Scenario: Extract person entities from text
    When I process text containing "Alice Smith works at Microsoft"
    Then entities should include "Alice Smith" with type "Person"
    And entities should include "Microsoft" with type "Organization"

  @extraction @entities
  Scenario: Extract organization entities from text
    When I process text containing "Google acquired YouTube in 2006"
    Then entities should include "Google" with type "Organization"
    And entities should include "YouTube" with type "Organization"

  @extraction @entities
  Scenario: Extract location entities from text
    When I process text containing "Headquarters is in San Francisco"
    Then entities should include "San Francisco" with type "Location"

  @extraction @entities
  Scenario: Extract multiple entity types from complex text
    When I process text containing "CEO John Doe announced that Acme Corp will open a new office in Seattle next month"
    Then entities should include "John Doe" with type "Person"
    And entities should include "Acme Corp" with type "Organization"
    And entities should include "Seattle" with type "Location"
    And entities should include "next month" with type "Event"

  @extraction @relations
  Scenario: Extract relations between entities
    When I process text containing "Sarah works at Tech Inc"
    Then relations should include a link from "Sarah" to "Tech Inc"
    And the relation type should indicate employment

  @extraction @relations
  Scenario: Extract multiple relations from text
    When I process text containing "Apple creates iPhone in California"
    Then there should be at least 2 relations extracted
    And relations should connect the subject and object entities

  @extraction @error
  Scenario: Handle empty text gracefully
    When I process empty text
    Then the response should indicate processing error
    And no entities should be extracted

  @extraction @error
  Scenario: Handle LLM API failure
    Given the LLM API is unavailable
    When I process text containing "Some content"
    Then the response should indicate processing error
    And the error should describe the API failure

  @extraction @error
  Scenario: Handle invalid LLM response format
    Given the LLM returns malformed JSON
    When I process text containing "Test content"
    Then the response should indicate parsing error

  @extraction @mock
  Scenario: Process documents in mock mode for testing
    Given mock LLM mode is enabled
    When I process text containing "Any content here"
    Then the response should contain predefined mock entities
    And no actual LLM API call should be made

  @extraction @entities
  Scenario: Handle text with no extractable entities
    When I process text containing only stop words
    Then the response should have empty entities list
    And the response should indicate success

  @extraction @unicode
  Scenario: Extract entities from unicode text
    When I process text containing "こんにちは世界 and Café München"
    Then the response should include entities for unicode names
    And the extraction should complete successfully
