@glue_job
Feature: Automatic Glue batch job lifecycle
  As a Glue job author
  I want job setup and completion handling to happen automatically around my script entrypoint
  So that my job code stays focused on business logic with less boilerplate

  Scenario: Successful job execution commits job bookmarks
    Given an entrypoint decorated with BatchJob
    When the entrypoint is called
    Then the job is initialized
    And the entrypoint receives business arguments and a SparkJobContext
    And the entrypoint completes without error
    And the job is committed

  Scenario: Failed job execution propagates exception without committing
    Given an entrypoint decorated with BatchJob
    And the entrypoint raises a RuntimeError "entrypoint failed"
    When the entrypoint is called
    Then the job is initialized
    And a RuntimeError "entrypoint failed" is propagated to the caller
    And the job is not committed

  Scenario: System parameters are filtered from business arguments
    Given an entrypoint decorated with BatchJob
    And the job is launched with CLI arguments:
      | argument          | value             |
      | --JOB_NAME        | test              |
      | --JOB_RUN_ID     | jr_123            |
      | --TempDir         | s3://bucket/temp/ |
      | --RedshiftTempDir | s3://bucket/temp/ |
      | --conf            | spark.shuffle=10  |
      | --enable-metrics  | true              |
      | --custom-key      | custom_val        |
    When the entrypoint is called
    Then business arguments match exactly:
      | key        | value      |
      | custom_key | custom_val |

  Scenario: Platform arguments are curated into job metadata
    Given an entrypoint decorated with BatchJob
    And the job is launched with CLI arguments:
      | argument              | value               |
      | --JOB_NAME            | test_job            |
      | --JOB_RUN_ID         | jr_123              |
      | --job-bookmark-option | job-bookmark-enable |
      | --enable-auto-scaling | true                |
      | --datalake-formats    | iceberg,delta       |
      | --TempDir             | s3://bucket/temp/   |
    When the entrypoint is called
    Then the job metadata matches:
      | attribute            | value               |
      | name                 | test_job            |
      | run_id               | jr_123              |
      | bookmark_option      | job-bookmark-enable |
      | auto_scaling_enabled | True                |
      | temp_dir             | s3://bucket/temp/   |
    And datalake formats include "iceberg" and "delta"

  Scenario: Lazy evaluation fetches job run telemetry in one call
    Given an entrypoint decorated with BatchJob
    And the AWS Glue service returns job run telemetry
    When the entrypoint is called
    Then accessing job run telemetry calls get_job_run exactly once
    And job run telemetry matches:
      | attribute         | value    |
      | worker_type       | G.2X     |
      | number_of_workers | 10       |
      | attempt           | 2        |
      | glue_version      | 5.0      |
      | execution_class   | STANDARD |

  Scenario: Calculating remaining execution time
    Given a job run with 30 minutes timeout that started 5 minutes ago
    When calculating remaining execution time
    Then the remaining time in milliseconds is greater than zero

  Scenario: Telemetry fetch raises PermissionError when access is denied
    Given the AWS Glue service fails with ClientError "AccessDeniedException"
    When accessing lazy job telemetry
    Then a PermissionError is raised indicating missing IAM permissions

  Scenario: Telemetry fetch raises ConnectionError on network timeout
    Given the AWS Glue service is unreachable due to network timeout
    When accessing lazy job telemetry
    Then a ConnectionError is raised indicating network or VPC failure

  Scenario: Telemetry fetch propagates unhandled ClientError
    Given the AWS Glue service fails with ClientError "ValidationException"
    When accessing lazy job telemetry
    Then a ClientError "ValidationException" is propagated to the caller
