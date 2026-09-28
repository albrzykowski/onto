Feature: Override mode — building the ontology from scratch
  As a user
  I want to rebuild the ontology from scratch
  So that the previous state is discarded

  Scenario: The previous ontology is overwritten
    Given the output directory contains an old "schema.yaml" with the class "OldClass"
    And the input directory contains "new.txt"
    And the LLM returns the class "NewClass"
    When override mode runs
    Then the new "schema.yaml" does not contain the class OldClass
    And it contains the class NewClass
    And the provenance log starts from scratch

  Scenario: state.json is cleared
    Given state.json contains old fingerprints
    When override mode runs
    Then state.json contains only fingerprints from the current build

  Scenario: All documents are processed again
    Given the input directory contains 2 documents whose fingerprints are present in state.json
    When override mode runs
    Then both documents are sent to the LLM
