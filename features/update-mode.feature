Feature: Update mode — extending an existing ontology
  As a user
  I want to update an existing ontology with new documents
  So that the ontology grows without rebuilding from scratch

  Background:
    Given an existing ontology with a schema containing the class Vehicle
    And the instance "VW_Golf"
    And a state.json file with the fingerprint of "old.txt"

  Scenario: An unchanged document is skipped
    Given the input directory contains "old.txt" with content matching its stored fingerprint
    When update mode runs
    Then "old.txt" is not sent to the LLM
    And the ontology remains unchanged
    And a "document.skipped" event is logged

  Scenario: A new document extends the schema
    Given the input directory contains "new.txt" with a fingerprint absent from state.json
    And the LLM returns a new class "Transmission"
    When update mode runs
    Then the schema contains the classes Vehicle and Transmission
    And the existing instances are left untouched
    And the fingerprint of "new.txt" is stored in state.json

  Scenario: A duplicate class is detected via embeddings and merged
    Given the LLM returns a new class "MotorCar" whose embedding is similar to "Vehicle" above the 0.85 threshold
    And the LLM confirms the two concepts are identical during merge verification
    When update mode runs
    Then the schema does not contain a new class MotorCar
    And the class Vehicle has its source_documents annotation extended with the new document
    And a "class.merged" event is recorded in the provenance log, mentioning both MotorCar and Vehicle, with the source text excerpt

  Scenario: Related but distinct concepts are not merged
    Given the LLM returns a new class "ElectricVehicle" whose embedding is similar to "Vehicle" above the threshold
    And the LLM rejects the merge during verification because the concepts are distinct
    When update mode runs
    Then the schema contains both Vehicle and ElectricVehicle
    And ElectricVehicle is defined with "is_a: Vehicle" when the LLM proposes that hierarchy

  Scenario: Candidates below the similarity threshold are added without LLM verification
    Given the LLM returns a new class "FuelStation" whose embedding similarity to Vehicle is 0.4
    When update mode runs
    Then merge verification is not performed for the pair FuelStation/Vehicle
    And FuelStation is added as a new class

  Scenario: A slot type conflict is resolved by the LLM
    Given the existing class Vehicle has the slot "weight" of type string
    And a new document suggests the type integer
    And the LLM resolves the conflict
    When update mode runs
    Then the schema has a consistent weight slot type matching the LLM decision
    And a "slot.updated" event is recorded in the provenance log with the source text excerpt
