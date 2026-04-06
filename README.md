# Powertools for AWS Glue

Powertools for AWS Glue is a developer toolkit to implement best practices and increase developer velocity.

*It's inspired by Powertools for AWS Lambda.*

## Features

- **Batch job** — Use `BatchJob` as a decorator on a parameterless entrypoint (for example `main`) or as a context manager. It runs `job.init()` before your code and `job.commit()` only when the block or decorated function exits without an exception. Spark and Glue are initialized internally; you do not receive context objects from the API.

## Installation

TBD

## Development

Tests run [inside the AWS Glue 5.0 libraries Docker image](https://docs.aws.amazon.com/glue/latest/dg/develop-local-docker-image.html) so Behave exercises the same Python environment as Glue jobs. Docker must be running locally.

```bash
just test
```

CI runs the same command (`just test`).

## License

This project is licensed under the MIT License — see the [LICENSE](https://github.com/HH-MWB/aws-glue-powertools/blob/main/LICENSE) file for details.
