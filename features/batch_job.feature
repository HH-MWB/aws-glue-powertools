@glue_job
Feature: Automatic Glue batch job lifecycle
  As a Glue job author
  I want job setup and completion handling to happen automatically around my script entrypoint
  So that my job code stays focused on business logic with less boilerplate

  Scenario: Successful job execution commits job bookmarks
    Given an entrypoint decorated with BatchJob
    When the entrypoint is called
    Then the job is initialized
    And the entrypoint receives job arguments and a SparkJobContext
    And the entrypoint completes without error
    And the job is committed

  Scenario: Failed job execution propagates exception without committing
    Given an entrypoint decorated with BatchJob
    And the entrypoint raises a RuntimeError "entrypoint failed"
    When the entrypoint is called
    Then the job is initialized
    And a RuntimeError "entrypoint failed" is propagated to the caller
    And the job is not committed
