# Powertools for AWS Glue

Powertools for AWS Glue is a developer toolkit to implement best practices and increase developer velocity.

*Inspired by Powertools for AWS Lambda.*

## Features

- **`BatchJob`** — Automates Glue batch job lifecycle (`job.init()` and failure-safe `job.commit()`), initializes Spark and Glue contexts, and injects `(args, context)`.
- **`SparkJobInfo` & `SparkJobRun`** — Curated runtime metadata via `ctx.job`, lazy AWS Glue telemetry via `ctx.run` (attempts, workers, timing), and infrastructure paths.
- **Clean Argument Separation** — Strictly separates business inputs in `args` from platform metadata in `ctx.job`.
- **Typed Argument Parsing** — Automatically validates and parses business CLI parameters into standard dataclasses or Pydantic models using entrypoint type hints.

## Installation

```bash
pip install aws-glue-powertools
```

To enable Pydantic model validation for typed argument parsing, install the `pydantic` extra:

```bash
pip install "aws-glue-powertools[pydantic]"
```

## Quick Start

```python
from dataclasses import dataclass

from aws_glue_powertools.jobs.spark import BatchJob, SparkJobContext


@dataclass
class JobParameters:
    target_date: str
    source_bucket: str
    dry_run: bool = False


@BatchJob()
def main(args: JobParameters, ctx: SparkJobContext) -> None:
    if args.dry_run:
        print(f"Dry-run for {ctx.job.name} (run {ctx.job.run_id})")
        return

    spark = ctx.glue.spark_session
    df = spark.read.parquet(f"{args.source_bucket}/{args.target_date}/")
    df.write.parquet(f"{ctx.job.temp_dir}/output/")


if __name__ == "__main__":
    main()
```

## License

This project is licensed under the MIT License — see the [LICENSE](https://github.com/HH-MWB/aws-glue-powertools/blob/main/LICENSE) file for details.
