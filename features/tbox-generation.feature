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

   Scenario: A class is assigned only the slots the schema has
    Given a configuration with allowed_relations containing the relation "has_engine"
    And the LLM has returned the class candidate "Vehicle" and the relations "has_engine", "has_wheel"
    When the T-Box is generated
    Then the class Vehicle has the slot "has_engine" only
    And a "slot.rejected" event with the reason "not_in_allowed_relations" is recorded for has_wheel

  Scenario: Slot creation is logged with its source excerpt
    Given the LLM returns the class Vehicle and the relation has_engine from one chunk
    When the T-Box is generated
    Then an "slot.created" event for has_engine is recorded with the chunk and the excerpt

  Scenario: Class description is merged from multiple chunks using LLM
    Given the LLM returns the class Vehicle from chunk#1 with description "A motorized road vehicle"
    And the LLM returns the class Vehicle from chunk#2 with description "A car"
    When the T-Box is generated
    Then the class Vehicle has a description merged from both chunks
    And an "class.updated" event is recorded with the merged description

  Scenario: Slot description is merged from multiple chunks using LLM
    Given the LLM returns the relation has_engine from chunk#1 with description "Links a vehicle to its engine"
    And the LLM returns the relation has_engine from chunk#2 with description "The engine that powers a vehicle"
    When the T-Box is generated
    Then the slot has_engine has a description merged from both chunks
    And an "slot.updated" event is recorded with the merged description
