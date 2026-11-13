"""Automatic Glue Spark job lifecycle management and runtime context."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import cached_property, wraps
from typing import TYPE_CHECKING

import boto3
from awsglue.context import GlueContext
from awsglue.job import Job
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
from aws_glue_powertools.jobs.options import resolve_arguments
from aws_glue_powertools.jobs.parser import parse_arguments

if TYPE_CHECKING:
    from collections.abc import Callable
    from typing import Self, TypeVar

    _ArgsT = TypeVar("_ArgsT")

__all__ = [
    "BatchJob",
    "SparkJobContext",
    "SparkJobInfo",
    "SparkJobRun",
]


# =============================================================================
# Models & Runtime Context
# =============================================================================


@dataclass(frozen=True, slots=True, kw_only=True)
class SparkJobInfo:
    """Curated static metadata for the current Spark Glue job.

    Attributes:
        name: Human-readable name of the Glue job.
        run_id: Unique identifier for this specific execution.
        bookmark_option: Job bookmark mode option.
        auto_scaling_enabled: Whether worker auto-scaling is enabled.
        datalake_formats: Enabled open table formats.
        temp_dir: Staging directory for temporary job files.
    """

    name: str
    run_id: str
    bookmark_option: str = "job-bookmark-disable"
    auto_scaling_enabled: bool = False
    datalake_formats: tuple[str, ...] = ()
    temp_dir: str | None = None

    @classmethod
    def from_args(cls, glue_args: dict[str, str]) -> Self:
        """Create SparkJobInfo from resolved Glue platform arguments.

        Args:
            glue_args: Resolved AWS Glue platform argument dictionary.

        Returns:
            Populated SparkJobInfo instance.
        """
        return cls(
            name=glue_args["JOB_NAME"],
            run_id=glue_args["JOB_RUN_ID"],
            bookmark_option=glue_args.get(
                "job_bookmark_option",
                "job-bookmark-disable",
            ),
            auto_scaling_enabled=glue_args.get("enable_auto_scaling")
            == "true",
            datalake_formats=tuple(
                fmt.strip()
                for fmt in glue_args.get("datalake_formats", "").split(",")
                if fmt.strip()
            ),
            temp_dir=glue_args.get("TempDir"),
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class SparkJobRun:
    """Telemetry and execution details for the current Spark Glue job run.

    Attributes:
        attempt: Execution attempt number from AWS.
        started_on: Run start timestamp from AWS.
        timeout: Configured job timeout duration from AWS.
        worker_type: Worker type from AWS (e.g., 'G.1X', 'G.2X').
        number_of_workers: Configured worker count from AWS.
        glue_version: Glue version from AWS (e.g., '5.0', '6.0').
        execution_class: Execution class from AWS ('STANDARD' or 'FLEX').
    """

    attempt: int
    started_on: datetime
    timeout: timedelta
    worker_type: str
    number_of_workers: int
    glue_version: str
    execution_class: str = "STANDARD"

    def get_remaining_time(self) -> timedelta:
        """Calculate remaining execution time before job timeout.

        Returns:
            Remaining execution time, or timedelta(0) if timed out.
        """
        deadline = self.started_on + self.timeout
        return max(timedelta(0), deadline - datetime.now(UTC))


# AWS IAM permission error codes mapped to GluePermissionError.
_PERMISSION_ERROR_CODES: frozenset[str] = frozenset(
    {
        "AccessDeniedException",
        "UnauthorizedOperation",
    },
)


@dataclass(frozen=True, kw_only=True)
class SparkJobContext:
    """Immutable runtime context for Spark Glue jobs.

    Attributes:
        glue: Initialized GlueContext instance.
        job: Curated static metadata for the current job.
        run: Lazy-loaded AWS Glue job run telemetry from AWS API.
    """

    glue: GlueContext
    job: SparkJobInfo

    @cached_property
    def run(self) -> SparkJobRun:
        """Lazy-loaded AWS Glue job run telemetry from AWS API."""
        # 1. Fetch job run details and translate service/network errors
        try:
            job_run = boto3.client("glue").get_job_run(
                JobName=self.job.name,
                RunId=self.job.run_id,
            )["JobRun"]
        except ClientError as exc:
            if (
                exc.response.get("Error", {}).get("Code", "")
                not in _PERMISSION_ERROR_CODES
            ):
                raise
            raise GluePermissionError(
                self.job.name,
                "glue:GetJobRun",
            ) from exc
        except (EndpointConnectionError, ConnectTimeoutError) as exc:
            raise GlueConnectionError(self.job.name) from exc

        # 2. Map verified payload into domain telemetry model
        return SparkJobRun(
            attempt=job_run["Attempt"],
            started_on=job_run["StartedOn"],
            timeout=timedelta(minutes=job_run["Timeout"]),
            worker_type=job_run["WorkerType"],
            number_of_workers=job_run["NumberOfWorkers"],
            glue_version=job_run["GlueVersion"],
            execution_class=job_run.get("ExecutionClass", "STANDARD"),
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
            business_args, glue_args = resolve_arguments(sys.argv)

            # 2. Parse and validate business payload
            parsed_args = parse_arguments(entrypoint, business_args)

            # 3. Build runtime context and curate job metadata
            ctx = SparkJobContext(
                glue=GlueContext(SparkContext.getOrCreate()),
                job=SparkJobInfo.from_args(glue_args),
            )

            # 4. Initialize AWS Glue job lifecycle
            glue_job = Job(ctx.glue)
            glue_job.init(ctx.job.name, glue_args)

            # 5. Execute user entrypoint with business payload
            entrypoint(parsed_args, ctx)

            # 6. Commit bookmarks and job state
            glue_job.commit()

        return wrapper
