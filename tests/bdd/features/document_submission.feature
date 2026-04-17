Feature: Document Submission

  As a user of the ontology pipeline,
  I want to submit documents for processing,
  So that entities and relations can be extracted and stored.

  Background:
    Given the API server is running
    And Pulsar message broker is available

  @document @submission
  Scenario: Submit valid document successfully
    When I submit a document with tenant_id "acme-corp" and content "John works at Acme Corp as a software engineer"
    Then the API should return status 200
    And the response should contain status "accepted"
    And the response should include the tenant_id "acme-corp"

  @document @validation
  Scenario: Reject document with empty tenant_id
    When I submit a document with tenant_id "" and content "Some content"
    Then the API should return status 422
    And the response should indicate validation error

  @document @validation
  Scenario: Reject document with invalid tenant_id characters
    When I submit a document with tenant_id "tenant@#$%" and content "Some content"
    Then the API should return status 422
    And the response should indicate validation error

  @document @validation
  Scenario: Reject document with tenant_id exceeding max length
    When I submit a document with tenant_id longer than 128 characters
    Then the API should return status 422
    And the response should indicate validation error

  @document @error
  Scenario: Handle Pulsar unavailable gracefully
    Given Pulsar message broker is unavailable
    When I submit a document with tenant_id "test-tenant" and content "Test content"
    Then the API should return status 503
    And the response should include an error message
