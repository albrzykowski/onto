Feature: Generating a LinkML T-Box
  As a library
  I want to build the ontology schema (classes, slots) in LinkML format
  So that the domain structure is formally described

  Scenario: A valid LinkML schema
    Given the LLM has returned the class candidates Vehicle, Engine, Manufacturer and the relations has_engine, produced_by
    When the T-Box is generated
    Then the file "schema.yaml" is saved in the output directory
    And the document contains LinkML-compliant "id" and "name" fields
    And it contains the class definitions Vehicle, Engine, Manufacturer
    And the class Vehicle has the slot "has_engine"

  Scenario: Schema validation
    Given a generated T-Box
    When the schema is validated
    Then it passes linkml validation without errors

  Scenario: Classes carry descriptions and provenance
    Given a generated T-Box
    Then every class has a "description" provided by the LLM
    And every class has a "source_documents" annotation pointing to its source document

  Scenario: Schema consolidation over a large corpus
    Given candidates from 3 independent chunks containing the repeated class Vehicle
    When the T-Box is generated
    Then the schema contains exactly one class Vehicle
    And the source_documents annotation of Vehicle lists all 3 chunks
