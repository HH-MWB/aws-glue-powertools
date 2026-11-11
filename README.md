# Powertools for AWS Glue

Powertools for AWS Glue is a developer toolkit to implement best practices and increase developer velocity.

*It's inspired by Powertools for AWS Lambda.*

## Features

- **`BatchJob`** — Automates Glue batch job lifecycle (`job.init()` and failure-safe `job.commit()`), initializes Spark and Glue contexts, and injects `(args, context)`.
- **`SparkJobInfo`** — Curated runtime metadata, AWS Glue telemetry via `ctx.job.run` (attempts, workers, timing), and infrastructure paths.
- **Clean Argument Separation** — Strictly separates business inputs in `args` from platform metadata in `ctx.job`. See [Job Parameters Reference](docs/job-parameters.md).
- **Typed Argument Parsing** — Automatically validates and parses business CLI parameters into standard dataclasses or Pydantic models using entrypoint type hints.

## Installation

```bash
pip install aws-glue-powertools
```

## License

This project is licensed under the MIT License — see the [LICENSE](https://github.com/HH-MWB/aws-glue-powertools/blob/main/LICENSE) file for details.
