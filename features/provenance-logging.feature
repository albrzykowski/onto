Feature: Provenance log of the ontology build
  As a user
  I want a complete event log with provenance for every ontology change
  So that I know which document and which text passage each change came from

  Scenario: Class creation is logged with its source excerpt
    Given the LLM returns the class Vehicle derived from the sentence "VW has been producing the Golf, a compact passenger car, since 1974." in chunk "corpus/article1.txt#c3"
    When the ontology is built
    Then the provenance.jsonl contains a "class.created" event
    And the event has the id "Vehicle"
    And the event has source_documents with the path "corpus/article1.txt" and the chunk "c3"
    And the event has a source_excerpt equal to "VW has been producing the Golf, a compact passenger car, since 1974."
    And the event has a timestamp and the build mode

  Scenario: Updates and merges are distinguishable events
    Given the existing class Vehicle is updated in update mode by merging the concept "Car"
    When the ontology is updated
    Then the log contains a "class.merged" event naming the surviving concept Vehicle and the merged concept Car, with the source text excerpt
    And the log contains a "class.updated" event with the new source document

  Scenario: Rejections are logged
    Given a candidate class Person is rejected because it is not in allowed_classes
    When the ontology is built
    Then the log contains a "class.rejected" event with the reason "not_in_allowed_classes"

  Scenario: Every log line is valid JSON
    Given an ontology built from 3 documents
    Then every line of provenance.jsonl parses as a JSON object
    And every entry has the fields event, id, source_documents, source_excerpt, timestamp, mode

  Scenario: Skipping a document is logged
    Given an unchanged document in update mode
    When the ontology is updated
    Then the log contains a "document.skipped" event with the document path and the reason "unchanged_fingerprint"
