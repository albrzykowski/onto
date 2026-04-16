Feature: System Integration

  As an end user of the ontology pipeline,
  I want to submit documents and retrieve extracted knowledge,
  So that I can build a knowledge graph from unstructured text.

  Background:
    Given all services are running
    And the pipeline is operational

  @integration @end_to_end
  Scenario: Full pipeline from document submission to entity storage
    When I submit a document with tenant_id "integration-test" and content "CEO Tim Cook leads Apple"
    Then the document should be accepted with status 202
    When the consumer processes the document
    Then entities "Tim Cook" and "Apple" should be extracted
    And entities should be stored in PostgreSQL
    And embeddings should be stored in Qdrant

  @integration @multi_tenant
  Scenario: Multi-tenant isolation
    Given tenant "tenant-a" with document "Alice works at Google"
    And tenant "tenant-b" with document "Bob works at Microsoft"
    When both documents are processed
    Then entities from tenant-a should not affect tenant-b
    And each tenant should have separate topic

  @integration @async
  Scenario: Async processing with eventual consistency
    When I submit a document with content "New company founded"
    Then I should receive acceptance immediately
    And after processing, entities should be available in database
    And the processing should complete within reasonable time

  @integration @reliability
  Scenario: Producer retries on transient failure
    Given Pulsar has transient connection issues
    When I submit a document
    Then the system should retry automatically
    And the document should eventually be queued
    And the API should return success

  @integration @reliability
  Scenario: Graceful degradation when LLM is slow
    Given the LLM API has high latency
    When I submit a document
    Then the request should not timeout immediately
    And the document should be processed when LLM responds

  @integration @reliability
  Scenario: Consumer continues after message processing error
    Given a malformed message in the queue
    When the consumer receives the malformed message
    Then the consumer should log the error
    And the consumer should continue processing next message
    And the consumer should not crash

  @integration @data
  Scenario: Entities persist across restarts
    Given documents have been processed and entities stored
    When the consumer is restarted
    Then the stored entities should remain in PostgreSQL
    And the embeddings should remain in Qdrant

  @integration @scaling
  Scenario: Multiple documents processed concurrently
    Given I submit 5 documents in quick succession
    When all documents are queued
    Then all documents should be processed
    And no documents should be lost or duplicated

  @integration @deduplication
  Scenario: Same content submitted multiple times deduplicates
    Given tenant has submitted document with "Same Company LLC"
    When the same tenant submits another document with "Same Company LLC"
    Then the entities should be merged
    And there should be only one canonical entity

  @integration @graph
  Scenario: Relations form connected knowledge graph
    Given document "Alice works at TechCorp"
    And document "TechCorp acquired StartupX"
    When both documents are processed
    Then there should be a path from "Alice" to "StartupX" through relations
    And the knowledge graph should reflect the company relationships

  @integration @tenant
  Scenario: Same entity name in different tenants
    Given tenant-a has entity "Global Corp"
    And tenant-b has entity "Global Corp"
    When both tenants exist
    Then each tenant should have their own instance
    And cross-tenant merging should not occur

  @integration @health
  Scenario: System reports unhealthy when Pulsar is down
    Given Pulsar message broker is stopped
    When I check system health
    Then the readiness endpoint should report not ready
    And the API should still respond to health checks
    And new document submissions should fail gracefully

  @integration @recovery
  Scenario: System recovers after Pulsar restart
    Given Pulsar was down and documents were submitted
    When Pulsar is restarted
    And the system recovers
    Then queued documents should be processed
    And new documents should be accepted
