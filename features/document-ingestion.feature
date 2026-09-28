Feature: Loading text documents
  As a library
  I want to load all supported documents from a given folder
  So that they can be fed into ontology extraction

  Background:
    Given an empty input directory "corpus"

  Scenario: Loading all supported formats
    Given files "a.txt", "b.md", "c.pdf", "d.docx" in the directory "corpus"
    When documents are loaded from "corpus"
    Then the document list contains 4 entries
    And every document has non-empty text content
    And every document has a "path" attribute with its source path

  Scenario: Skipping unsupported formats
    Given files "a.txt" and "img.png" in the directory "corpus"
    When documents are loaded from "corpus"
    Then the document list contains 1 entry
    And a warning about the skipped file "img.png" is logged

  Scenario: Recursive discovery
    Given a file "sub/nested.txt" in the directory "corpus"
    When documents are loaded from "corpus"
    Then the document list contains 1 entry "corpus/sub/nested.txt"

  Scenario: A corrupted document does not abort ingestion
    Given a corrupted file "broken.pdf" in the directory "corpus"
    And a file "good.txt" in the directory "corpus"
    When documents are loaded from "corpus"
    Then the document list contains 1 entry "corpus/good.txt"
    And an error for "broken.pdf" is logged

  Scenario: Document fingerprint
    Given a file "a.txt" in the directory "corpus"
    When documents are loaded from "corpus"
    Then every document has a fingerprint computed from its content (sha256)

  Scenario: Empty input folder
    Given an input directory "corpus" without files
    When documents are loaded from "corpus"
    Then a NoDocumentsFoundError is raised
