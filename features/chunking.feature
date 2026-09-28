Feature: Splitting documents into chunks
  As a library
  I want to split documents into size-limited chunks
  So that large documents can be processed in safe batches for the LLM

  Background:
    Given a configuration with chunking.strategy "fixed"
    And max_chunk_tokens 100
    And overlap_tokens 20

  Scenario: A long document is split
    Given a document with 300 tokens of text
    When chunking is performed
    Then the number of chunks is greater than 1
    And every chunk has at most 100 tokens
    And every chunk has the identifier "<path>#c<N>"

  Scenario: A short document becomes a single chunk
    Given a document with 50 tokens of text
    When chunking is performed
    Then the number of chunks is 1

  Scenario: Overlap between adjacent chunks
    Given a document with 250 tokens of text
    When chunking is performed
    Then the tail of chunk N overlaps the head of chunk N+1 by at least 20 tokens

  Scenario: A chunk keeps a reference to its document
    Given any document split into chunks
    Then every chunk has a "source_path" attribute pointing to its source document
