Feature: Command-line interface
  As a developer
  I want to run ontology builds and updates from the CLI
  So that I can use the library without writing code

  Scenario: The build command in override mode
    Given a directory "corpus" with the file "a.txt"
    And a configuration file "config.yaml" with mode "override"
    When I run `onto build --config config.yaml --input corpus --output out`
    Then the exit code is 0
    And the files "out/schema.yaml", "out/instances.yaml", "out/provenance.jsonl" exist

  Scenario: The update command
    Given an existing ontology in the directory "out"
    And a new document in the directory "corpus_new"
    When I run `onto update --config config.yaml --input corpus_new --output out`
    Then the exit code is 0
    And the ontology in "out" has been extended

  Scenario: Missing configuration fails with an error
    When I run `onto build` without arguments
    Then the exit code is non-zero
    And the error message explains the required arguments

  Scenario: Command help
    When I run `onto --help`
    Then the exit code is 0
    And the help lists the commands build and update
