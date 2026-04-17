Feature: Entity Extraction

  As a knowledge engineer of the ontology pipeline,
  I want structured entities, typed relations, and entity definitions to be extracted from text,
  So that I can build a consistent and enriched knowledge graph.

  Background:
    Given the LLM API is configured with mock mode

  @extraction @entities @definition
  Scenario: Extract entities, types, relations and definitions from text
    When I submit a document with content "Alice met the White Rabbit"
    Then the extracted entities should be:
      | entity       | type   | definition                                   |
      | Alice        | Person | a person named Alice                         |
      | White Rabbit | Person | a rabbit character known as White Rabbit     |

    And the extracted relation should be:
      | subject | predicate | object        |
      | Alice   | met       | White Rabbit  |