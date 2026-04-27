Feature: Health Monitoring

  As an operator of the pipeline,
  I want to monitor system health,
  So that I can verify the system is operational.

  Background:
    Given the API server is running

  @health @monitoring
  Scenario: Health endpoint returns healthy status
    When I call the health endpoint
    Then the response should have status "healthy"
    And the response should be HTTP 200

  @health @monitoring
  Scenario: Health endpoint is always available
    When I call the health endpoint
    Then the response should be received within 1 second
    And the response should not depend on external services

  @health @readiness
  Scenario: Readiness endpoint detects successful Pulsar connection
    Given Pulsar message broker is available
    When I call the readiness endpoint
    Then the response should have pulsar status "connected"
    And the response should be HTTP 200

  @health @readiness
  Scenario: Readiness endpoint detects Pulsar unavailability
    Given Pulsar message broker is unavailable
    When I call the readiness endpoint
    Then the response should indicate system is not ready
    And the response should be HTTP 503
    And the response should include an error message

  @health @readiness
  Scenario: Readiness endpoint handles connection timeout
    Given Pulsar message broker has connection timeout
    When I call the readiness endpoint
    Then the response should indicate system is not ready
    And the response should be HTTP 503

  @health @monitoring
  Scenario: Health check does not affect Pulsar connection pool
    Given the system has processed multiple requests
    When I call the health endpoint
    Then Pulsar connections should remain stable
