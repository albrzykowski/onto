Feature: Entity Resolution

	As a knowledge engineer of the ontology pipeline,
	I want duplicate entities to be merged automatically,
	So that the knowledge base remains consistent and reliable.

	Background:
		Given the Qdrant vector store is available
		And the PostgreSQL database is available
		And entities have been extracted from a document
		And the merge threshold is 0.90
		And the review threshold is 0.70
		And type mismatch penalty is 0.20

	@resolution @new_entity
	Scenario: Create new entity when no candidates found
		Given no existing entities in the knowledge base
		When I search for candidate entities for "NewCompany"
		Then the system should return an empty candidate list
		When I resolve entity "NewCompany" of type "Organization"
		Then the system should create a new entity record
		And the decision should be "CREATE_NEW"
		And the entity should be stored in PostgreSQL

	@resolution @merge
	Scenario: Merge entity when highly similar
		Given existing entities:
		| name       | type          | id  |
		| Acme Corp  | Organization  | 123 |
		When I search for candidate entities for "ACME CORP"
		Then the system should return candidates ranked by similarity
		When I resolve entity "ACME CORP" of type "Organization"
		Then the system should compute similarity scores for each candidate
		And the best candidate should have a score greater than or equal to 0.90
		And the system should select the best candidate
		And the system should merge with entity ID "123"
		And the decision should be "MERGE"

	@resolution @review
	Scenario: Flag entity for review when similarity is ambiguous
		Given existing entities:
		| name       | type          | id  |
		| Acme Corp  | Organization  | 123 |
		| Acme Inc   | Organization  | 456 |
		When I search for candidate entities for "Acme"
		Then the system should return multiple candidates
		When I resolve entity "Acme" of type "Organization"
		Then the system should compute similarity scores
		And the best score should be between 0.70 and 0.90
		And the system should not automatically merge
		And the decision should be "REVIEW"

	@resolution @no_merge
	Scenario: Create new entity when dissimilar
		Given existing entities:
		| name    | type          |
		| Apple   | Organization  |
		When I search for candidate entities for "Banana"
		Then the system should return candidates ranked by similarity
		When I resolve entity "Banana" of type "Organization"
		Then the best similarity score should be lower than 0.70
		And the system should create a new entity
		And the decision should be "CREATE_NEW"

	@resolution @type_mismatch
	Scenario: Apply penalty for type mismatch during resolution
		Given existing entities:
		| name  | type     | id  |
		| Java  | Product  | 111 |
		When I search for candidate entities for "Java"
		Then the system should return candidates
		When I resolve entity "Java" of type "Location"
		Then the system should compute a base similarity score
		And a type mismatch penalty of 0.20 should be applied
		And the final score should be reduced accordingly
		And the final score should be below merge threshold
		And the system should not merge
		And the decision should be "CREATE_NEW"

	@resolution @same_name_different_entities
	Scenario: Same name but different real-world entities
		Given existing entities:
		| name   | type          | context        |
		| Apple  | Organization  | technology     |
		When I search for candidate entities for "Apple"
		Then the system should return candidates
		When I resolve entity "Apple" of type "Food" with context "fruit"
		Then the system should compute similarity scores
		And contextual mismatch should reduce the score
		And the final score should be below merge threshold
		And the system should create a new entity
		And the decision should be "CREATE_NEW"

	@resolution @exact_match_boost
	Scenario: Boost score for exact name match
		Given existing entities:
		| name       | type          | id  |
		| Acme Corp  | Organization  | 123 |
		When I search for candidate entities for "acme corp"
		Then the system should return candidates
		When I resolve entity "acme corp" of type "Organization"
		Then the system should detect case-insensitive exact match
		And an exact match boost should be applied
		And the final score should exceed merge threshold
		And the system should merge with entity ID "123"
		And the decision should be "MERGE"

	@resolution @alias
	Scenario: Boost score using alias mapping
		Given existing entities:
		| name                          | type          | id  |
		| International Business Machines | Organization | 999 |
		And alias mappings:
		| alias | canonical                          |
		| IBM   | International Business Machines    |
		When I search for candidate entities for "IBM"
		Then the system should return candidates
		When I resolve entity "IBM" of type "Organization"
		Then the system should detect alias match
		And an alias boost should be applied
		And the final score should exceed merge threshold
		And the system should merge with entity ID "999"
		And the decision should be "MERGE"

