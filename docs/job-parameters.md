# Job Parameters and Runtime Context

In `aws-glue-powertools`, your job entrypoint receives two distinct arguments: `args` and `ctx`.

They follow a strict **Invariance Rule**: if an attribute belongs to `ctx`, it does not belong to `args` (`args ∩ ctx.job = ∅`).

## 1. Design Philosophy

This architecture mirrors the separation between `event` and `context` in AWS Lambda:

* **`args: dict[str, str]` (Business Payload)**:
  Contains exclusively domain-specific, business parameters passed to the job (e.g. `--target_date`, `--source_bucket`, `--environment`).
* **`ctx: SparkJobContext` (Runtime Environment)**:
  Provides the initialized execution environment and structured platform metadata:
  * `ctx.glue` (`GlueContext`): Initialized AWS Glue and Apache Spark sessions.
  * `ctx.job` (`SparkJobInfo`): Curated job identity and static configuration from CLI arguments.
  * `ctx.run` (`SparkJobRun`): Lazy-loaded execution telemetry from the AWS Glue service.

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

## 3. Runtime Telemetry (`ctx.run`)

While CLI arguments provide static configuration, runtime telemetry is fetched on-demand from the AWS Glue service (`glue:GetJobRun`) and exposed through `ctx.run`:

| Attribute | Type | Description |
| :--- | :--- | :--- |
| `ctx.run.attempt` | `int` | Execution attempt number (1 for initial run, 2+ for retries). |
| `ctx.run.started_on` | `datetime` | UTC timestamp when the job run started. |
| `ctx.run.timeout` | `timedelta` | Configured job timeout duration. |
| `ctx.run.worker_type` | `str` | Worker type allocated by AWS (e.g., `'G.1X'`, `'G.2X'`). |
| `ctx.run.number_of_workers` | `int` | Number of provisioned workers for this execution. |
| `ctx.run.glue_version` | `str` | AWS Glue runtime version (e.g., `'5.0'`). |
| `ctx.run.execution_class` | `str` | Execution class (`'STANDARD'` or `'FLEX'`). |
| `ctx.run.get_remaining_time()` | `timedelta` | Remaining execution time before job timeout. |

> [!TIP]
> **Lazy-Loaded:** The AWS Glue API is only called when `ctx.run` is first accessed. If your code only needs the run ID, read `ctx.job.run_id` directly — it comes from `--JOB_RUN_ID` with zero API calls and zero network requests.

## 4. Usage Example

```python
from aws_glue_powertools.jobs.spark import BatchJob, SparkJobContext


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

    # 3. Access dynamic execution telemetry via 'ctx.run':
    print(
        f"Allocated workers: {ctx.run.number_of_workers} ({ctx.run.worker_type})"
    )
    print(f"Time remaining: {ctx.run.get_remaining_time()}")

    # 4. Use Spark and Glue contexts directly:
    spark = ctx.glue.spark_session
    df = spark.read.parquet(f"{source_bucket}/{target_date}/")
    df.write.parquet(f"{temp_dir}/output/")
```

## 5. Typed Argument Parsing

Instead of receiving raw strings in `dict[str, str]` and manually converting types, you can annotate your first argument with a standard Python `@dataclass` (zero external dependencies) or a **Pydantic** model (`BaseModel`). `@BatchJob` automatically parses, validates, and injects the model instance into your entrypoint.

### Option A: Standard Library `@dataclass` (Zero Dependencies)

Standard dataclasses work out of the box in Python 3.11+ without installing any extra packages:

```python
from dataclasses import dataclass, field
from aws_glue_powertools.jobs.spark import BatchJob, SparkJobContext


@dataclass
class JobParameters:
    target_date: str
    source_bucket: str
    batch_size: int = 1000
    threshold: float = 0.95
    dry_run: bool = False
    partitions: list[str] = field(default_factory=list)
    optional_note: str | None = None


@BatchJob()
def main(args: JobParameters, ctx: SparkJobContext) -> None:
    if args.dry_run:
        print(f"Dry-run execution for batch size: {args.batch_size}")
        return

    spark = ctx.glue.spark_session
    df = spark.read.parquet(f"{args.source_bucket}/{args.target_date}/")
    df.limit(args.batch_size).write.parquet(f"{ctx.job.temp_dir}/output/")
```

#### Supported Basic Types in Dataclasses

* **Scalars:** `str`, `int`, `float`, `bool`
  * `bool` accepts `"True"`, `"true"` (`True`) and `"False"`, `"false"` (`False`) only.
  * In accordance with Glue's parser behavior, values are never silently stripped with `.strip()`, preserving user input integrity.
* **Collections:** `list`, `tuple`, `set`, `frozenset` (e.g. `list[int]`, `tuple[str, ...]`, `set[int]`, `frozenset[float]`, bare `list`, `tuple`, `set`, `frozenset`)
  * Parsed from comma-separated CLI strings (e.g. `--partitions "part1,part2"` or `--partitions ""`).
  * If an item type is specified (`str`, `int`, `float`), elements are cast to that type; bare collections default element types to `str`.
* **Optionals & Defaults:** `T | None` / `Optional[T]`, field defaults (`= ...`), and `field(default_factory=...)`.

### Option B: Pydantic (`BaseModel`)

For deep validation, regex constraints, and nested schema parsing, use Pydantic models.

#### Installation

Install `aws-glue-powertools` with the optional `pydantic` extra:

```bash
pip install "aws-glue-powertools[pydantic]"
```

#### Example

```python
from aws_glue_powertools.jobs.spark import BatchJob, SparkJobContext
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
* If input arguments fail dataclass or Pydantic validation, a `JobArgumentValidationError` is raised immediately.
* If an entrypoint specifies an unsupported argument type (e.g. primitives, unsupported field types, or invalid dictionary types), an `UnsupportedArgumentTypeError` is raised.
* No billable Spark worker execution or state commitment occurs.
