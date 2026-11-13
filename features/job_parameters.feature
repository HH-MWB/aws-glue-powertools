Feature: Glue CLI parameter filtering and metadata mapping
  As a Glue job author
  I want AWS Glue system flags separated from business arguments
  So that business arguments stay clean and platform settings remain structured

  Scenario: System parameters are filtered from business arguments
    Given an entrypoint decorated with BatchJob
    And the caller passes CLI arguments:
      | argument          | value             |
      | --JOB_NAME        | test              |
      | --JOB_RUN_ID      | jr_123            |
      | --TempDir         | s3://bucket/temp/ |
      | --RedshiftTempDir | s3://bucket/temp/ |
      | --conf            | spark.shuffle=10  |
      | --enable-metrics  | true              |
      | --custom-key      | custom_val        |
    When the caller runs the entrypoint
    Then the entrypoint receives exact business arguments:
      | key        | value      |
      | custom_key | custom_val |

  Scenario: Platform parameters are mapped into job metadata
    Given an entrypoint decorated with BatchJob
    And the caller passes CLI arguments:
      | argument              | value               |
      | --JOB_NAME            | test_job            |
      | --JOB_RUN_ID          | jr_123              |
      | --job-bookmark-option | job-bookmark-enable |
      | --enable-auto-scaling | true                |
      | --datalake-formats    | iceberg,delta       |
      | --TempDir             | s3://bucket/temp/   |
    When the caller runs the entrypoint
    Then the job metadata matches:
      | attribute            | value               |
      | name                 | test_job            |
      | run_id               | jr_123              |
      | bookmark_option      | job-bookmark-enable |
      | auto_scaling_enabled | true                |
      | datalake_formats     | iceberg, delta      |
      | temp_dir             | s3://bucket/temp/   |
