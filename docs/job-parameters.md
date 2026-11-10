# Job Parameters and Runtime Context

In `aws-glue-powertools`, your job entrypoint receives two distinct arguments: `args` and `ctx`.

They follow a strict **Invariance Rule**: if an attribute belongs to `ctx`, it does not belong to `args` (`args ∩ ctx.job = ∅`).

---

## 1. Design Philosophy

This architecture mirrors the separation between `event` and `context` in AWS Lambda:

* **`args: dict[str, str]` (Business Payload)**:
  Contains exclusively domain-specific, business parameters passed to the job (e.g. `--target_date`, `--source_bucket`, `--environment`).
* **`ctx: SparkJobContext` (Runtime Environment)**:
  Provides the initialized execution environment and structured platform metadata:
  * `ctx.glue` (`GlueContext`): Initialized AWS Glue and Apache Spark sessions.
  * `ctx.job` (`SparkJobInfo`): Curated job identity and static configuration from CLI arguments.
  * `ctx.job.run` (`SparkJobRun`): Lazy-loaded execution telemetry from the AWS Glue service.

### Why are platform options filtered from `args`?

When AWS Glue launches a job, it injects dozens of infrastructure, classpath, and monitoring flags into `sys.argv` (e.g., `--conf`, `--extra-jars`, `--enable-metrics`). Leaving these system flags in `args` pollutes the business dictionary with platform noise.

`aws-glue-powertools` automatically filters out all AWS Glue system arguments from `args`. Any parameter that is useful to application logic is curated onto `ctx.job` as a typed, structured attribute.

### Escape Hatch

In the rare event that a script requires access to an uncurated AWS Glue platform flag, you can call Glue's native parser directly:

```python
import sys
from awsglue.utils import getResolvedOptions

extra_args = getResolvedOptions(sys.argv, ["spark-event-logs-path"])
```

---

## 2. CLI Options Reference Table

The table below catalogs all AWS Glue platform parameters injected via CLI arguments, their curated attribute on `ctx.job`, and their descriptions. In accordance with the Invariance Rule, **none of these options appear in `args`**:

| CLI Option | Curated in `ctx.job` | Description |
| :--- | :--- | :--- |
| **`JOB_NAME`** | `ctx.job.name` | Name of the AWS Glue job. |
| **`JOB_RUN_ID`** | `ctx.job.run_id` | Unique execution identifier for this run. |
| **`job-bookmark-option`** | `ctx.job.bookmark_option` | Bookmark state (`job-bookmark-enable`, `job-bookmark-disable`, `job-bookmark-pause`). |
| **`enable-auto-scaling`** | `ctx.job.auto_scaling_enabled` | Whether dynamic worker auto-scaling is active. |
| **`datalake-formats`** | `ctx.job.datalake_formats` | Enabled open table formats (e.g., `iceberg`, `delta`). |
| **`TempDir`** | `ctx.job.temp_dir` | S3 path for temporary and scratch files. |
| **`RedshiftTempDir`** | — | Legacy Redshift staging directory (aliased to `TempDir` by AWS Glue). |
| **`JOB_ID`** | — | Unique Glue job definition ID. |
| **`SECURITY_CONFIGURATION`** | — | Name of AWS security configuration. |
| **`job-bookmark-from`** | — | Bookmark lower bound run ID. |
| **`job-bookmark-to`** | — | Bookmark upper bound run ID. |
| **`continuation-option`** | — | Job run continuation mode. |
| **`conf`** | — | Native Spark configuration options passed to driver. |
| **`encryption-type`** | — | S3 encryption mode for job artifacts. |
| **`enable-data-lineage`** | — | OpenLineage tracking configuration. |
| **`enable-metrics`** | — | CloudWatch detailed job metrics. |
| **`enable-continuous-cloudwatch-log`** | — | Real-time continuous CloudWatch log streaming. |
| **`enable-continuous-log-filter`** | — | CloudWatch log filter level. |
| **`enable-spark-ui`** | — | Apache Spark UI event log generator. |
| **`spark-event-logs-path`** | — | S3 storage path for Spark event logs. |
| **`extra-py-files`** | — | S3 paths to additional Python modules or wheels. |
| **`extra-jars`** | — | S3 paths to additional Java `.jar` dependencies. |
| **`extra-files`** | — | S3 paths to arbitrary non-executable text files. |
| **`user-jars-first`** | — | Classpath priority flag for user-supplied jars. |
| **`write-shuffle-files-to-s3`** | — | Offload Spark shuffle partitions to Amazon S3. |
| **`write-shuffle-spills-to-s3`** | — | Offload Spark shuffle spills to Amazon S3. |

---

## 3. Runtime Telemetry (`ctx.job.run`)

While CLI arguments provide static configuration, runtime telemetry is fetched on-demand from the AWS Glue service (`glue:GetJobRun`) and exposed through `ctx.job.run`:

| Attribute | Type | Description |
| :--- | :--- | :--- |
| `ctx.job.run.attempt` | `int` | Execution attempt number (1 for initial run, 2+ for retries). |
| `ctx.job.run.started_on` | `datetime` | UTC timestamp when the job run started. |
| `ctx.job.run.timeout` | `int` | Configured job timeout in minutes. |
| `ctx.job.run.worker_type` | `str` | Worker type allocated by AWS (e.g., `'G.1X'`, `'G.2X'`). |
| `ctx.job.run.number_of_workers` | `int` | Number of provisioned workers for this execution. |
| `ctx.job.run.glue_version` | `str` | AWS Glue runtime version (e.g., `'5.0'`). |
| `ctx.job.run.execution_class` | `str` | Execution class (`'STANDARD'` or `'FLEX'`). |
| `ctx.job.run.get_remaining_time_in_millis()` | `int` | Calculated milliseconds remaining before job timeout. |

> [!TIP]
> **Lazy-Loaded:** The AWS Glue API is only called when `ctx.job.run` is first accessed. If your code never reads telemetry, zero API calls and zero network requests are made.

---

## 4. Usage Example

```python
from aws_glue_powertools.job import BatchJob, SparkJobContext


@BatchJob()
def main(args: dict[str, str], ctx: SparkJobContext) -> None:
    # 1. Access business inputs directly from 'args':
    target_date = args["target_date"]
    source_bucket = args["source_bucket"]

    # 2. Access static platform configuration from 'ctx.job':
    job_name = ctx.job.name
    temp_dir = ctx.job.temp_dir

    if "iceberg" in ctx.job.datalake_formats:
        print(f"Executing Iceberg ETL for {job_name}")

    # 3. Access dynamic execution telemetry via 'ctx.job.run':
    print(
        f"Allocated workers: {ctx.job.run.number_of_workers} ({ctx.job.run.worker_type})"
    )
    print(f"Time remaining: {ctx.job.run.get_remaining_time_in_millis()}ms")

    # 4. Use Spark and Glue contexts directly:
    spark = ctx.glue.spark_session
    df = spark.read.parquet(f"{source_bucket}/{target_date}/")
    df.write.parquet(f"{temp_dir}/output/")
```

---

## 5. Typed Argument Parsing (Pydantic)

Instead of receiving raw strings in `dict[str, str]` and manually converting types, you can annotate your first argument with a **Pydantic** model (`BaseModel`). `@BatchJob` automatically parses, validates, and injects the model instance into your entrypoint.

### Installation

Install `aws-glue-powertools` with the optional `parser` extra:

```bash
pip install "aws-glue-powertools[parser]"
```

### Example

```python
from aws_glue_powertools.job import BatchJob, SparkJobContext
from pydantic import BaseModel


class JobParameters(BaseModel):
    target_date: str
    source_bucket: str
    batch_size: int = 1000
    dry_run: bool = False


@BatchJob()
def main(args: JobParameters, ctx: SparkJobContext) -> None:
    # 'args' is now a fully validated JobParameters instance:
    if args.dry_run:
        print(f"Dry-run execution for batch size: {args.batch_size}")
        return

    spark = ctx.glue.spark_session
    df = spark.read.parquet(f"{args.source_bucket}/{args.target_date}/")
    df.limit(args.batch_size).write.parquet(f"{ctx.job.temp_dir}/output/")
```

### Fail-Fast Validation

Argument validation executes **before** the AWS Glue lifecycle initializes (`glue_job.init()`) and before the Apache Spark session starts:
* If input arguments fail Pydantic validation, a `JobArgumentValidationError` is raised immediately.
* If an entrypoint specifies an unsupported argument type (e.g. primitives, non-Pydantic classes, or invalid dictionary types), an `UnsupportedArgumentTypeError` is raised.
* No billable Spark worker execution or state commitment occurs.
