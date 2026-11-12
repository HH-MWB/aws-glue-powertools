Feature: Lazy job run telemetry and remaining execution time
  As a Glue job author
  I want job run telemetry fetched on demand and service errors translated clearly
  So that jobs avoid extra AWS API calls and fail with clear diagnostics

  Rule: Telemetry is fetched once on first access and cached

    Scenario: Reading multiple telemetry attributes requests job run details once
      Given a BatchJob entrypoint that reads all job run telemetry
      And AWS Glue returns job run details:
        | field             | value    |
        | worker_type       | G.2X     |
        | number_of_workers | 10       |
        | attempt           | 2        |
        | timeout_minutes   | 60       |
        | glue_version      | 5.0      |
        | execution_class   | STANDARD |
      When the caller runs the entrypoint
      Then AWS Glue receives one request for job run details
      And the job run telemetry matches:
        | attribute         | value    |
        | worker_type       | G.2X     |
        | number_of_workers | 10       |
        | attempt           | 2        |
        | timeout           | 1:00:00  |
        | glue_version      | 5.0      |
        | execution_class   | STANDARD |
      And the Glue job is committed

  Rule: AWS service and network errors fail without committing the job

    Scenario: Denied telemetry access raises GluePermissionError
      Given a BatchJob entrypoint that reads all job run telemetry
      And AWS Glue returns error "AccessDeniedException"
      When the caller runs the entrypoint
      Then the Glue job is initialized
      And the caller receives GluePermissionError requiring "glue:GetJobRun"
      And the Glue job is not committed

    Scenario: Telemetry network timeout raises GlueConnectionError
      Given a BatchJob entrypoint that reads all job run telemetry
      And AWS Glue fails with a network timeout
      When the caller runs the entrypoint
      Then the Glue job is initialized
      And the caller receives GlueConnectionError for VPC or network failure
      And the Glue job is not committed

    Scenario: Unhandled AWS error propagates to the caller
      Given a BatchJob entrypoint that reads all job run telemetry
      And AWS Glue returns error "ValidationException"
      When the caller runs the entrypoint
      Then the Glue job is initialized
      And the caller receives ClientError "ValidationException"
      And the Glue job is not committed

  Rule: Remaining execution time reflects timeout minus elapsed duration

    Scenario Outline: Calculating remaining execution time
      Given a BatchJob entrypoint that reads remaining execution time
      And AWS Glue returns a job run with a <timeout> minute timeout started <elapsed> minutes ago
      When the caller runs the entrypoint
      Then the remaining execution time is <expectation>
      And the Glue job is committed

      Examples:
        | timeout | elapsed | expectation       |
        | 30      | 5       | greater than zero |
        | 30      | 40      | zero              |
