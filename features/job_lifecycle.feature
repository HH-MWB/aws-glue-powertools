Feature: Automatic Glue batch job lifecycle
  As a Glue job author
  I want Glue job setup and completion handled automatically around my entrypoint
  So that my job code stays focused on business logic with less boilerplate

  Scenario: Successful job execution commits the Glue job
    Given an entrypoint decorated with BatchJob
    When the caller runs the entrypoint
    Then the Glue job is initialized
    And the entrypoint receives business arguments and a SparkJobContext
    And the Glue job is committed

  Scenario: Failed job execution propagates exception without committing
    Given an entrypoint decorated with BatchJob
    And the entrypoint raises RuntimeError "entrypoint failed"
    When the caller runs the entrypoint
    Then the Glue job is initialized
    And the caller receives RuntimeError "entrypoint failed"
    And the Glue job is not committed
