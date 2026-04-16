Feature: Entity Resolution

  As the ontology pipeline,
  I resolve extracted entities against existing knowledge base,
  So that duplicate entities are merged and canonical records are maintained.

  Background:
    Given the Qdrant vector store is available
    And the PostgreSQL database is available
    And entities have been extracted from a document

  @resolution @new_entity
  Scenario: Create new entity when no candidates found
    Given no existing entities in the knowledge base
    When I resolve entity "NewCompany" of type "Organization"
    Then the system should create a new entity record
    And the decision should be "CREATE_NEW"
    And the entity should be stored in PostgreSQL

  @resolution @merge
  Scenario: Merge entity when highly similar
    Given existing entity "Acme Corp" of type "Organization" with ID "123"
    When I resolve entity "ACME CORP" of type "Organization"
    Then the system should merge with existing entity
    And the decision should be "MERGE"
    And the confidence should be at least 0.85

  @resolution @no_merge
  Scenario: Keep entities separate when dissimilar
    Given existing entity "Apple" of type "Organization"
    When I resolve entity "Banana" of type "Organization"
    Then the system should create a new entity
    And the decision should be "CREATE_NEW"

  @resolution @type_mismatch
  Scenario: Apply penalty for type mismatch during resolution
    Given existing entity "Java" of type "Product"
    When I resolve entity "Java" of type "Location"
    Then the similarity score should be reduced
    And the entities should not merge due to type mismatch penalty

  @resolution @confidence
  Scenario: Use 0.85 threshold for merge decision
    Given existing entity with various similarity scores
    When I resolve entity with confidence 0.85
    Then the decision should be "MERGE"
    When I resolve entity with confidence 0.84
    Then the decision should be "CREATE_NEW"

  @resolution @error
  Scenario: Handle embedding generation failure
    Given the embedding service is unavailable
    When I resolve entity "TestEntity"
    Then the system should create a new entity
    And the decision should have confidence 0.0
    And the error should be logged

  @resolution @error
  Scenario: Handle Qdrant search failure
    Given Qdrant vector store is unavailable
    When I resolve entity "TestEntity"
    Then the system should create a new entity
    And the error should be logged as warning
    And the processing should continue

  @resolution @relations
  Scenario: Map relations to canonical entity IDs
    Given entities are resolved with merge decisions
    When relations reference original entity IDs
    Then relations should be updated to use canonical IDs
    And the mapped relations should be stored

  @resolution @relations
  Scenario: Filter relations with unmapped entities
    Given some entities are merged and others are new
    When there are relations referencing unmapped entities
    Then those relations should be filtered out
    And only valid relations should be stored

  @resolution @history
  Scenario: Record merge history for audit
    Given entity "A" is being merged with entity "B"
    When the merge decision is made
    Then the merge should be recorded in merge_history table
    And the record should include both entity IDs and timestamp

  @resolution @duplicate
  Scenario: Handle exact duplicate entity submissions
    Given the same entity was submitted in previous document
    When I resolve the same entity again
    Then it should merge with the existing canonical entity
    And the count of references should increase

  @resolution @multi
  Scenario: Resolve multiple entities in single document
    Given a document with 5 entities and 3 relations
    When I resolve all entities
    Then each entity should have a resolution decision
    And all relations should be mapped to canonical IDs
    And all valid relations should be stored

  @resolution @type
  Scenario: Support all entity types
    Given extracted entities of types: Person, Organization, Location, Event, Concept, Product, Other
    When I resolve each entity type
    Then each type should be stored correctly in PostgreSQL
    And the entity type should be searchable in Qdrant
