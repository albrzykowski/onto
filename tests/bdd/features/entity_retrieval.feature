Feature: Entity Retrieval

As a knowledge engineer,
I want to retrieve candidate entities using semantic similarity,
So that the resolution step can make accurate decisions.

Background:
	Given a mock LLM API is available
	And a retrieval Qdrant vector store is available
	And the default candidate limit is 5

@retrieval @basic
Scenario: Retrieve candidates using descriptions
	Given the knowledge base contains entities:
	| name            | type        | description                                              |
	| Mad Hatter      | Character   | Eccentric tea party host                                    |
	| March Hare      | Character   | Companion of the Hatter at the tea party                   |
	When I search for candidate entities for "tea party"
	Then the system should query the vector store using description embeddings
	And the system should return a list of candidates
	And the candidates should be ranked by semantic similarity

@retrieval @empty
Scenario: No candidates found
	Given the knowledge base is empty
	And the default candidate limit is 1
	When I search for candidate entities for "Nonexistent XYZ Query 12345"
	Then the system should return a list of candidates
	And the list should have at most 1 entities

@retrieval @ranking
Scenario: Best semantic match appears first
	Given the knowledge base contains entities:
	| name            | type        | description                                              |
	| Cheshire Cat    | Character   | Grinning cat that can disappear                          |
	| White Rabbit    | Character   | Nervous rabbit obsessed with time                        |
	When I search for candidate entities for "disappearing cat"
	Then the system should return a list of candidates
	And the candidates should be ranked by semantic similarity

@retrieval @type_filter
Scenario: Prefer candidates of the same type with context
	Given the knowledge base contains entities:
	| name   | type      | description                                    |
	| Alice  | Character | Curious girl exploring Wonderland              |
	| Alice  | Book      | Story about a girl in a surreal world          |
	When I lookup entity candidates using query "Alice in Wonderland" with type filter "Character"
	Then the system should return a list of candidates

@retrieval @context
Scenario: Use context to disambiguate entities
	Given the knowledge base contains entities:
	| name            | type        | description                                              |
	| Queen of Hearts | Character   | Tyrannical ruler shouting "Off with their heads!"        |
	| King of Hearts  | Character   | Timid ruler, husband of the Queen                        |
	When I search for candidate entities for "execution ruler"
	Then the system should return a list of candidates

@retrieval @relations
Scenario: Use relational context in descriptions
	Given the knowledge base contains entities:
	| name         | type        | description                                                     |
	| Mad Hatter   | Character   | Hosts a tea party with the March Hare and the Dormouse          |
	| Dormouse     | Character   | Sleeps during the tea party with the Hatter and March Hare      |
	When I search for candidate entities for "tea party character"
	Then the system should return a list of candidates

@retrieval @limit
Scenario: Limit number of candidates
	Given the knowledge base contains more than 5 entities with descriptions
	When I search for candidate entities for "wonderland character"
	Then the system should return no more than 5 candidates
