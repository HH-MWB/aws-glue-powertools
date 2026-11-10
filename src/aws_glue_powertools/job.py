"""Automatic Glue batch job lifecycle management."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import cached_property, wraps
from typing import TYPE_CHECKING

import boto3
from awsglue.context import GlueContext
from awsglue.job import Job
from awsglue.utils import getResolvedOptions
from botocore.exceptions import (
    ClientError,
    ConnectTimeoutError,
    EndpointConnectionError,
)
from pyspark.context import SparkContext

from aws_glue_powertools.exceptions import (
    GlueConnectionError,
    GluePermissionError,
)
from aws_glue_powertools.parser import parse_arguments

if TYPE_CHECKING:
    from collections.abc import Callable
    from typing import TypeVar

    _ArgsT = TypeVar("_ArgsT")

__all__ = [
    "BatchJob",
    "SparkJobContext",
    "SparkJobInfo",
    "SparkJobRun",
    "resolve_arguments",
]


# =============================================================================
# Models & Runtime Context
# =============================================================================


@dataclass(frozen=True, slots=True, kw_only=True)
class SparkJobRun:
    """Telemetry and execution details for the current Spark Glue job run.

    Attributes:
        attempt: Execution attempt number from AWS.
        started_on: Run start timestamp from AWS.
        timeout: Job timeout in minutes from AWS.
        worker_type: Worker type from AWS (e.g., 'G.1X', 'G.2X').
        number_of_workers: Configured worker count from AWS.
        glue_version: Glue version from AWS (e.g., '5.0', '6.0').
        execution_class: Execution class from AWS ('STANDARD' or 'FLEX').
    """

    attempt: int
    started_on: datetime
    timeout: int
    worker_type: str
    number_of_workers: int
    glue_version: str
    execution_class: str = "STANDARD"

    def get_remaining_time_in_millis(self) -> int:
        """Calculate milliseconds remaining before job timeout.

        Returns:
            Remaining execution time in milliseconds, or 0 if timed out.
        """
        deadline = self.started_on + timedelta(minutes=self.timeout)
        remaining = deadline - datetime.now(UTC)
        return max(0, remaining // timedelta(milliseconds=1))


# AWS IAM permission error codes mapped to GluePermissionError.
_PERMISSION_ERROR_CODES: frozenset[str] = frozenset(
    {
        "AccessDeniedException",
        "UnauthorizedOperation",
    },
)


@dataclass(frozen=True, kw_only=True)
class SparkJobInfo:
    """Runtime metadata and execution details for the current Spark Glue job.

    Attributes:
        name: Human-readable name of the Glue job.
        run_id: Unique identifier for this specific execution.
        bookmark_option: Job bookmark mode option.
        auto_scaling_enabled: Whether worker auto-scaling is enabled.
        datalake_formats: Enabled open table formats.
        temp_dir: Staging directory for temporary job files.
        run: Lazy-loaded AWS Glue job run telemetry from AWS API.
    """

    name: str
    run_id: str
    bookmark_option: str = "job-bookmark-disable"
    auto_scaling_enabled: bool = False
    datalake_formats: tuple[str, ...] = ()
    temp_dir: str | None = None

    @cached_property
    def run(self) -> SparkJobRun:
        """Lazy-loaded AWS Glue job run telemetry from AWS API."""
        # 1. Fetch job run details and translate service/network errors
        try:
            job_run = boto3.client("glue").get_job_run(
                JobName=self.name,
                RunId=self.run_id,
            )["JobRun"]
        except ClientError as exc:
            if (
                exc.response.get("Error", {}).get("Code", "")
                not in _PERMISSION_ERROR_CODES
            ):
                raise
            raise GluePermissionError(self.name, "glue:GetJobRun") from exc
        except (EndpointConnectionError, ConnectTimeoutError) as exc:
            raise GlueConnectionError(self.name) from exc

        # 2. Map verified payload into domain telemetry model
        return SparkJobRun(
            attempt=job_run["Attempt"],
            started_on=job_run["StartedOn"],
            timeout=job_run["Timeout"],
            worker_type=job_run["WorkerType"],
            number_of_workers=job_run["NumberOfWorkers"],
            glue_version=job_run["GlueVersion"],
            execution_class=job_run.get("ExecutionClass", "STANDARD"),
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class SparkJobContext:
    """Immutable runtime context for Spark Batch jobs.

    Attributes:
        glue: Initialized GlueContext instance.
        job: Runtime metadata and execution details for the current job.
    """

    glue: GlueContext
    job: SparkJobInfo


# =============================================================================
# Argument Resolution
# =============================================================================

_GLUE_SYSTEM_OPTIONS: frozenset[str] = frozenset(
    {
        # Identification & Metadata
        "JOB_ID",
        "JOB_RUN_ID",
        "SECURITY_CONFIGURATION",
        # Bookmarks & Continuation
        "job-bookmark-option",
        "continuation-option",
        "job-bookmark-from",
        "job-bookmark-to",
        # Security & Governance
        "encryption-type",
        "enable-data-lineage",
    },
)

_GLUE_RESERVED_KEYS: frozenset[str] = frozenset(
    {
        # Identification & Metadata (owned by ctx.job)
        "JOB_NAME",
        "JOB_RUN_ID",
        "JOB_ID",
        "SECURITY_CONFIGURATION",
        # Bookmarks & Continuation (owned by ctx.job or internal)
        "job_bookmark_option",
        "continuation_option",
        "job_bookmark_from",
        "job_bookmark_to",
        # Security & Governance
        "encryption_type",
        "enable_data_lineage",
        # Staging & Storage (owned by ctx.job)
        "TempDir",
        "RedshiftTempDir",
        "spark_event_logs_path",
        # Engine & Table Formats (owned by ctx.job)
        "enable_auto_scaling",
        "datalake_formats",
        "conf",
        # Monitoring & Observability
        "enable_metrics",
        "enable_continuous_cloudwatch_log",
        "enable_continuous_log_filter",
        "enable_spark_ui",
        # Dependencies & Classpath
        "extra_py_files",
        "extra_jars",
        "extra_files",
        "user_jars_first",
        # Shuffle & Optimization
        "write_shuffle_files_to_s3",
        "write_shuffle_spills_to_s3",
    },
)


def resolve_arguments(
    argv: list[str],
) -> tuple[dict[str, str], dict[str, str]]:
    """Resolve options into business payload and Glue system arguments.

    Args:
        argv: Command-line argument vector to resolve.

    Returns:
        A tuple of (business_args, glue_args).
    """
    options = [
        opt
        for arg in argv[1::2]
        if (opt := arg.removeprefix("--")) not in _GLUE_SYSTEM_OPTIONS
    ]
    resolved = getResolvedOptions(argv, options)
    return (
        {k: v for k, v in resolved.items() if k not in _GLUE_RESERVED_KEYS},
        {k: v for k, v in resolved.items() if k in _GLUE_RESERVED_KEYS},
    )


# =============================================================================
# Lifecycle Management
# =============================================================================


class BatchJob:
    """Spark Batch job lifecycle decorator."""

    def __call__(
        self,
        entrypoint: Callable[[_ArgsT, SparkJobContext], None],
    ) -> Callable[[], None]:
        """Wrap an entrypoint accepting (args, context)."""

        @wraps(entrypoint)
        def wrapper() -> None:
            # 1. Resolve arguments from command-line options
            args, glue_args = resolve_arguments(sys.argv)

            # 2. Parse and validate business payload
            parsed_args = parse_arguments(entrypoint, args)

            # 3. Build runtime context and curate job metadata
            ctx = SparkJobContext(
                glue=GlueContext(SparkContext.getOrCreate()),
                job=SparkJobInfo(
                    name=glue_args["JOB_NAME"],
                    run_id=glue_args["JOB_RUN_ID"],
                    bookmark_option=glue_args.get(
                        "job_bookmark_option",
                        "job-bookmark-disable",
                    ),
                    auto_scaling_enabled=glue_args.get(
                        "enable_auto_scaling",
                    )
                    == "true",
                    datalake_formats=tuple(
                        f.strip()
                        for f in glue_args.get(
                            "datalake_formats",
                            "",
                        ).split(",")
                        if f.strip()
                    ),
                    temp_dir=glue_args.get("TempDir"),
                ),
            )

            # 4. Initialize AWS Glue job lifecycle
            glue_job = Job(ctx.glue)
            glue_job.init(ctx.job.name, glue_args)

            # 5. Execute user entrypoint with business payload
            entrypoint(parsed_args, ctx)

            # 6. Commit bookmarks and job state
            glue_job.commit()

        return wrapper
