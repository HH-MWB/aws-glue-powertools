Feature: Typed business argument parsing and validation
  As a Glue job author
  I want CLI arguments validated against dataclass or Pydantic schemas before Spark starts
  So that invalid inputs fail fast without provisioning billable Glue workers

  Rule: Dataclass schemas parse typed scalars, collections, optionals, and defaults

    Scenario: Business arguments are parsed into a typed dataclass
      Given an entrypoint decorated with BatchJob expecting a dataclass
      And the caller passes CLI arguments:
        | argument        | value        |
        | --JOB_NAME      | test         |
        | --JOB_RUN_ID    | jr_123       |
        | --batch_id      | 42           |
        | --name          | test         |
        | --rate          | 3.14         |
        | --dry_run       | true         |
        | --tags          | a, b         |
        | --scores        | 10,20        |
        | --items         | x,y          |
        | --modes         | fast,safe    |
        | --raw_tuple     | x,y          |
        | --unique_ids    | 1,2          |
        | --raw_set       | alpha,beta   |
        | --rates         | 1.5,2.5      |
        | --raw_frozenset | apple,banana |
        | --extra_arg     | ignored      |
      When the caller runs the entrypoint
      Then the Glue job is initialized
      And the entrypoint receives a dataclass matching:
        | field         | type             | value                          |
        | batch_id      | int              | 42                             |
        | name          | str              | test                           |
        | rate          | float            | 3.14                           |
        | dry_run       | bool             | True                           |
        | tags          | list[str]        | ['a', ' b']                    |
        | scores        | list[int]        | [10, 20]                       |
        | items         | list             | ['x', 'y']                     |
        | modes         | tuple[str, ...]  | ('fast', 'safe')               |
        | raw_tuple     | tuple            | ('x', 'y')                     |
        | unique_ids    | set[int]         | {1, 2}                         |
        | raw_set       | set              | {'alpha', 'beta'}              |
        | rates         | frozenset[float] | frozenset({1.5, 2.5})          |
        | raw_frozenset | frozenset        | frozenset({'apple', 'banana'}) |
        | optional_note | str \| None      | None                           |
        | derived_field | str (init=False) | computed                       |
      And the received dataclass has no "extra_arg" attribute
      And the Glue job is committed

    Scenario: Omitted dataclass arguments fall back to defaults and empty collections
      Given an entrypoint decorated with BatchJob expecting a dataclass
      And the caller passes CLI arguments:
        | argument     | value  |
        | --JOB_NAME   | test   |
        | --JOB_RUN_ID | jr_123 |
        | --batch_id   | 42     |
        | --name       | test   |
        | --rate       | 1.0    |
        | --dry_run    | false  |
        | --scores     |        |
        | --rates      |        |
      When the caller runs the entrypoint
      Then the Glue job is initialized
      And the entrypoint receives a dataclass matching:
        | field         | value       |
        | batch_id      | 42          |
        | name          | test        |
        | rate          | 1.0         |
        | dry_run       | False       |
        | tags          | []          |
        | scores        | []          |
        | items         | []          |
        | modes         | ()          |
        | raw_tuple     | ()          |
        | unique_ids    | set()       |
        | raw_set       | set()       |
        | rates         | frozenset() |
        | raw_frozenset | frozenset() |
        | optional_note | None        |
        | derived_field | computed    |
      And the Glue job is committed

    Scenario: Missing required dataclass argument fails before job initialization
      Given an entrypoint decorated with BatchJob expecting a dataclass
      And the caller passes CLI arguments:
        | argument     | value  |
        | --JOB_NAME   | test   |
        | --JOB_RUN_ID | jr_123 |
        | --name       | test   |
        | --rate       | 3.14   |
      When the caller runs the entrypoint
      Then the caller receives JobArgumentValidationError
      And the Glue job is not initialized
      And the Glue job is not committed

    Scenario Outline: Invalid dataclass field values fail before job initialization
      Given an entrypoint decorated with BatchJob expecting a dataclass
      And the caller passes CLI arguments:
        | argument     | value      |
        | --JOB_NAME   | test       |
        | --JOB_RUN_ID | jr_123     |
        | --batch_id   | <batch_id> |
        | --name       | test       |
        | --rate       | 3.14       |
        | --dry_run    | <dry_run>  |
      When the caller runs the entrypoint
      Then the caller receives JobArgumentValidationError
      And the Glue job is not initialized
      And the Glue job is not committed

      Examples:
        | batch_id   | dry_run    |
        | not_an_int | false      |
        | 42         | not_a_bool |

  Rule: Pydantic models validate arguments when the optional parser package is installed

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
        | type_spec                      |
        | dict[str, int]                 |
        | dataclass dict[str, object]    |
        | dataclass list[bool]           |
        | dataclass tuple[int, str]      |
        | dataclass int \| str \| None   |
        | custom class                   |

    Scenario: Unsupported custom class raises UnsupportedArgumentTypeError without optional Pydantic installed
      Given the optional Pydantic package is not installed
      And an entrypoint decorated with BatchJob expecting argument type "custom class"
      When the caller runs the entrypoint
      Then the caller receives UnsupportedArgumentTypeError
      And the Glue job is not initialized
      And the Glue job is not committed
