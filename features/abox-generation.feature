Feature: Generating a LinkML A-Box
  As a library
  I want to create class instances conforming to the T-Box schema
  So that concrete facts from the documents are represented

  Scenario: A valid instances file
    Given a generated T-Box with the class Vehicle and the slot has_engine
    And the LLM returns the instance "VW Golf" of class Vehicle with has_engine pointing to "1.6 TDI"
    When the A-Box is generated
    Then the file "instances.yaml" is saved in the output directory
    And it contains the instance "VW_Golf" of class Vehicle
    And the instance has the slot has_engine with the value "1.6_TDI"

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
