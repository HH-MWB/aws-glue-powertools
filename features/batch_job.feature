@glue_job
Feature: Automatic Glue batch job lifecycle
  As a Glue job author
  I want job setup and successful completion handling to happen
    automatically around my script entrypoint
  So that my job code stays focused on business logic with less
    boilerplate

  Scenario: Decorator completes successfully
    Given a script entrypoint decorated with BatchJob
    When the entrypoint is called
    Then the entrypoint completes without error
    And the job is initialized
    And the job is committed

  Scenario: Decorator propagates exceptions
    Given a script entrypoint decorated with BatchJob
    And the entrypoint raises a RuntimeError "entrypoint failed"
    When the entrypoint is called
    Then a RuntimeError "entrypoint failed" is propagated to the caller
    And the job is initialized
    And the job is not committed

  Scenario: Context manager completes successfully
    Given a BatchJob context manager
    When the managed block is executed
    Then the managed block completes without error
    And the job is initialized
    And the job is committed

  Scenario: Context manager propagates exceptions
    Given a BatchJob context manager
    And the managed block raises a RuntimeError "managed block failed"
    When the managed block is executed
    Then a RuntimeError "managed block failed" is propagated to the caller
    And the job is initialized
    And the job is not committed
