@glue_job
Feature: Automatic Glue batch job lifecycle
  As a Glue job author
  I want job setup and successful completion handling to happen
    automatically around my script entrypoint
  So that my job code stays focused on business logic with less
    boilerplate

  Scenario: Decorator completes successfully
    Given an entrypoint decorated with BatchJob
    When the entrypoint is called
    Then the entrypoint completes without error
    And the entrypoint receives job arguments and a SparkJobContext
    And the job is initialized
    And the job is committed

  Scenario: Decorator propagates exceptions
    Given an entrypoint decorated with BatchJob
    And the entrypoint raises a RuntimeError "entrypoint failed"
    When the entrypoint is called
    Then a RuntimeError "entrypoint failed" is propagated to the caller
    And the job is initialized
    And the job is not committed

  Scenario: Context manager unpacks arguments and context
    Given a BatchJob context manager
    When the managed block is executed with unpacked arguments and context
    Then the block receives job arguments and a SparkJobContext
    And the job is initialized
    And the job is committed

  Scenario: Context manager propagates exceptions
    Given a BatchJob context manager
    And the managed block raises a RuntimeError "managed block failed"
    When the managed block is executed
    Then a RuntimeError "managed block failed" is propagated to the caller
    And the job is initialized
    And the job is not committed
