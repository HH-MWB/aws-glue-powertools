Feature: Typed business argument parsing and validation
  As a Glue job author
  I want CLI arguments validated against dataclass or Pydantic schemas before Spark starts
  So that invalid inputs fail fast without provisioning billable Glue workers

  Rule: Supported scalar types are parsed into dataclass fields

    Scenario Outline: Valid scalar arguments are converted to typed fields
      Given an entrypoint decorated with BatchJob expecting a dataclass with scalar field "<field>" of type "<type>"
      And the caller passes CLI arguments:
        | argument   | value        |
        | --JOB_NAME | test         |
        | --<field>  | <raw_value>  |
      When the caller runs the entrypoint
      Then the Glue job is initialized
      And the entrypoint receives a dataclass with "<field>" equal to "<expected_value>"
      And the Glue job is committed

      Examples:
        | field         | type     | raw_value                            | expected_value                       |
        | name          | str      | test                                 | test                                 |
        | batch_id      | int      | 42                                   | 42                                   |
        | rate          | float    | 3.14                                 | 3.14                                 |
        | dry_run       | bool     | true                                 | True                                 |
        | run_id        | UUID     | aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee | aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee |
        | start_time    | datetime | 2026-11-12T12:00:00Z                 | 2026-11-12T12:00:00Z                 |
        | run_date      | date     | 2026-11-12                           | 2026-11-12                           |
        | schedule_time | time     | 14:30:00                             | 14:30:00                             |

    Scenario Outline: Invalid scalar arguments fail before job initialization
      Given an entrypoint decorated with BatchJob expecting a dataclass with scalar field "<field>" of type "<type>"
      And the caller passes CLI arguments:
        | argument   | value       |
        | --JOB_NAME | test        |
        | --<field>  | <bad_value> |
      When the caller runs the entrypoint
      Then the caller receives JobArgumentValidationError
      And the Glue job is not initialized
      And the Glue job is not committed

      Examples:
        | field         | type     | bad_value      |
        | batch_id      | int      | not_an_int     |
        | dry_run       | bool     | not_a_bool     |
        | run_id        | UUID     | not_a_uuid     |
        | start_time    | datetime | not_a_datetime |
        | run_date      | date     | not_a_date     |
        | schedule_time | time     | not_a_time     |

  Rule: Collection fields parse comma-separated values into containers

    Scenario: Parameterized collections parse comma-separated values into typed elements
      Given an entrypoint decorated with BatchJob expecting a collection dataclass
      And the caller passes CLI arguments:
        | argument     | value     |
        | --JOB_NAME   | test      |
        | --JOB_RUN_ID | jr_123    |
        | --scores     | 10,20     |
        | --modes      | fast,safe |
        | --unique_ids | 1,2       |
        | --rates      | 1.5,2.5   |
      When the caller runs the entrypoint
      Then the Glue job is initialized
      And the entrypoint receives a dataclass matching:
        | field      | type             | value                 |
        | scores     | list[int]        | [10, 20]              |
        | modes      | tuple[str, ...]  | ('fast', 'safe')      |
        | unique_ids | set[int]         | {1, 2}                |
        | rates      | frozenset[float] | frozenset({1.5, 2.5}) |
      And the Glue job is committed

    Scenario: Bare collections default elements to strings
      Given an entrypoint decorated with BatchJob expecting a collection dataclass
      And the caller passes CLI arguments:
        | argument        | value        |
        | --JOB_NAME      | test         |
        | --JOB_RUN_ID    | jr_123       |
        | --items         | x,y          |
        | --raw_tuple     | x,y          |
        | --raw_set       | alpha,beta   |
        | --raw_frozenset | apple,banana |
      When the caller runs the entrypoint
      Then the Glue job is initialized
      And the entrypoint receives a dataclass matching:
        | field         | type      | value                          |
        | items         | list      | ['x', 'y']                     |
        | raw_tuple     | tuple     | ('x', 'y')                     |
        | raw_set       | set       | {'alpha', 'beta'}              |
        | raw_frozenset | frozenset | frozenset({'apple', 'banana'}) |
      And the Glue job is committed

    Scenario: Empty collection arguments fall back to empty container instances
      Given an entrypoint decorated with BatchJob expecting a collection dataclass
      And the caller passes CLI arguments:
        | argument        | value |
        | --JOB_NAME      | test  |
        | --JOB_RUN_ID    | jr_123|
        | --scores        |       |
        | --modes         |       |
        | --unique_ids    |       |
        | --rates         |       |
        | --items         |       |
        | --raw_tuple     |       |
        | --raw_set       |       |
        | --raw_frozenset |       |
      When the caller runs the entrypoint
      Then the Glue job is initialized
      And the entrypoint receives a dataclass matching:
        | field         | value       |
        | scores        | []          |
        | modes         | ()          |
        | unique_ids    | set()       |
        | rates         | frozenset() |
        | items         | []          |
        | raw_tuple     | ()          |
        | raw_set       | set()       |
        | raw_frozenset | frozenset() |
      And the Glue job is committed

    Scenario: Invalid collection element values fail before job initialization
      Given an entrypoint decorated with BatchJob expecting a collection dataclass
      And the caller passes CLI arguments:
        | argument     | value      |
        | --JOB_NAME   | test       |
        | --JOB_RUN_ID | jr_123     |
        | --scores     | 10,invalid |
      When the caller runs the entrypoint
      Then the caller receives JobArgumentValidationError
      And the Glue job is not initialized
      And the Glue job is not committed

  Rule: Dataclass schemas support defaults, optional fields, and ignored arguments

    Scenario: Omitted fields fall back to dataclass defaults or None
      Given an entrypoint decorated with BatchJob expecting a lifecycle dataclass
      And the caller passes CLI arguments:
        | argument       | value  |
        | --JOB_NAME     | test   |
        | --JOB_RUN_ID   | jr_123 |
        | --required_val | custom |
      When the caller runs the entrypoint
      Then the Glue job is initialized
      And the entrypoint receives a dataclass matching:
        | field         | value    |
        | required_val  | custom   |
        | default_val   | default  |
        | optional_val  | None     |
        | derived_field | computed |
      And the Glue job is committed

    Scenario: Missing required dataclass argument fails before job initialization
      Given an entrypoint decorated with BatchJob expecting a lifecycle dataclass
      And the caller passes CLI arguments:
        | argument     | value  |
        | --JOB_NAME   | test   |
        | --JOB_RUN_ID | jr_123 |
      When the caller runs the entrypoint
      Then the caller receives JobArgumentValidationError
      And the Glue job is not initialized
      And the Glue job is not committed

    Scenario: Unknown CLI arguments are ignored by dataclass models
      Given an entrypoint decorated with BatchJob expecting a lifecycle dataclass
      And the caller passes CLI arguments:
        | argument       | value   |
        | --JOB_NAME     | test    |
        | --JOB_RUN_ID   | jr_123  |
        | --required_val | custom  |
        | --extra_arg    | ignored |
      When the caller runs the entrypoint
      Then the Glue job is initialized
      And the received dataclass has no "extra_arg" attribute
      And the Glue job is committed

  Rule: Pydantic models validate arguments when the optional pydantic extra is installed

    Scenario: Business arguments are parsed into a Pydantic model
      Given an entrypoint decorated with BatchJob expecting a Pydantic model
      And the caller passes CLI arguments:
        | argument     | value  |
        | --JOB_NAME   | test   |
        | --JOB_RUN_ID | jr_123 |
        | --batch_id   | 42     |
        | --dry_run    | true   |
      When the caller runs the entrypoint
      Then the Glue job is initialized
      And the entrypoint receives a Pydantic model with batch_id 42 and dry_run true
      And the Glue job is committed

    Scenario: Invalid Pydantic arguments fail before job initialization
      Given an entrypoint decorated with BatchJob expecting a Pydantic model
      And the caller passes CLI arguments:
        | argument     | value      |
        | --JOB_NAME   | test       |
        | --JOB_RUN_ID | jr_123     |
        | --batch_id   | not_an_int |
      When the caller runs the entrypoint
      Then the caller receives JobArgumentValidationError
      And the Glue job is not initialized
      And the Glue job is not committed

  Rule: Unsupported entrypoint argument annotations fail before job initialization

    Scenario Outline: Unsupported argument types raise UnsupportedArgumentTypeError
      Given an entrypoint decorated with BatchJob expecting argument type "<type_spec>"
      When the caller runs the entrypoint
      Then the caller receives UnsupportedArgumentTypeError
      And the Glue job is not initialized
      And the Glue job is not committed

      Examples:
        | type_spec                    |
        | dict[str, int]               |
        | dataclass dict[str, object]  |
        | dataclass list[bool]         |
        | dataclass tuple[int, str]    |
        | dataclass int \| str \| None |
        | custom class                 |

    Scenario: Unsupported custom class raises UnsupportedArgumentTypeError without optional Pydantic installed
      Given the optional Pydantic package is not installed
      And an entrypoint decorated with BatchJob expecting argument type "custom class"
      When the caller runs the entrypoint
      Then the caller receives UnsupportedArgumentTypeError
      And the Glue job is not initialized
      And the Glue job is not committed
