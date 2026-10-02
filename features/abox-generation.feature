Feature: Generating a LinkML A-Box
  As a library
  I want to create class instances conforming to the T-Box schema
  So that concrete facts from the documents are represented

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

  Scenario: Instances validated against the schema
    Given a generated A-Box and its T-Box
    When the instances are validated against the schema
    Then they pass LinkML schema-conformance validation without errors

  Scenario: An instance outside the schema is rejected
    Given the LLM returns an instance of the class "UnknownClass" that is not in the T-Box
    When the A-Box is generated
    Then the UnknownClass instance is not written to instances.yaml
    And an "instance.rejected" event is recorded in the provenance log

  Scenario: Every instance carries provenance
    Given a generated A-Box
    Then every instance has an annotation with its source document and chunk

  Scenario: A written instance is recorded
    Given a generated T-Box with the class Vehicle
    And the LLM returns the instance "VW Golf" of class Vehicle
    When the A-Box is generated
    Then an "instance.created" event for VW_Golf is recorded with the chunk and the excerpt in the provenance log

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

  Scenario: Instance description is merged from multiple chunks using LLM
    Given the LLM returns the instance "VW Golf" of class Vehicle from chunk#1 with description "A car made by VW"
    And the LLM returns the instance "VW Golf" of class Vehicle from chunk#2 with description "A popular model"
    When the A-Box is generated
    Then the instance VW_Golf has a description merged from both chunks
    And an "instance.updated" event is recorded with the merged description
