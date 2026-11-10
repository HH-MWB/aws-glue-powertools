"""Step definitions for the Batch job feature."""

from __future__ import annotations

import sys
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

if TYPE_CHECKING:
    from collections.abc import Iterator

    from features.steps.batch_job_types import BatchJobBehaveContext

from awsglue.context import GlueContext
from behave import given, then, when
from botocore.exceptions import ClientError, EndpointConnectionError
from pydantic import BaseModel

from aws_glue_powertools.exceptions import (
    GlueConnectionError,
    GluePermissionError,
    JobArgumentValidationError,
    UnsupportedArgumentTypeError,
)
from aws_glue_powertools.job import (
    BatchJob,
    SparkJobContext,
    SparkJobInfo,
    SparkJobRun,
)

# =============================================================================
# Helpers & Fixtures
# =============================================================================


@contextmanager
def _capture_error(bdd_context: BatchJobBehaveContext) -> Iterator[None]:
    """Capture Exception on bdd_context.execution_error."""
    try:
        yield
    except Exception as error:  # noqa: BLE001
        bdd_context.execution_error = error


def _create_mock_job_run_payload() -> dict[str, object]:
    """Build mock AWS Glue GetJobRun API response payload."""
    return {
        "JobRun": {
            "Attempt": 2,
            "StartedOn": datetime.now(UTC) - timedelta(minutes=5),
            "Timeout": 60,
            "WorkerType": "G.2X",
            "NumberOfWorkers": 10,
            "GlueVersion": "5.0",
            "ExecutionClass": "STANDARD",
        },
    }


def _patch_glue_client(
    context: BatchJobBehaveContext,
    mock_client: MagicMock,
    run_id: str = "jr_test",
) -> None:
    """Attach mock Glue boto3 client to context and start patcher."""
    context.mock_glue_client = mock_client
    patcher = patch(
        "aws_glue_powertools.job.boto3.client",
        return_value=mock_client,
    )
    context.mock_patcher = patcher
    patcher.start()
    context.tested_job_info = SparkJobInfo(name="test", run_id=run_id)


class _SampleModel(BaseModel):  # type: ignore[explicit-any]
    batch_id: int
    dry_run: bool = False


class _UnsupportedClass:
    pass


# =============================================================================
# Given Steps (Arrange)
# =============================================================================


@given("an entrypoint decorated with BatchJob")
def step_entrypoint_decorated(context: BatchJobBehaveContext) -> None:
    """Prepare an entrypoint decorated with BatchJob()."""

    @BatchJob()
    def entrypoint(args: dict[str, str], ctx: SparkJobContext) -> None:
        if context.raise_in_body:
            raise RuntimeError(context.expected_error_message)
        context.received_args = args
        context.received_context = ctx

    context.entrypoint = entrypoint


@given("an entrypoint decorated with BatchJob expecting a Pydantic model")
def step_entrypoint_with_pydantic_model(
    context: BatchJobBehaveContext,
) -> None:
    """Prepare an entrypoint expecting a Pydantic model."""

    @BatchJob()
    def entrypoint(args: _SampleModel, ctx: SparkJobContext) -> None:
        context.received_args = args
        context.received_context = ctx

    context.entrypoint = entrypoint


@given(
    "an entrypoint decorated with BatchJob "
    "expecting an unsupported model type",
)
def step_entrypoint_with_unsupported_model(
    context: BatchJobBehaveContext,
) -> None:
    """Prepare an entrypoint expecting an unsupported model type."""

    @BatchJob()
    def entrypoint(args: _UnsupportedClass, ctx: SparkJobContext) -> None:
        context.received_args = args
        context.received_context = ctx

    context.entrypoint = entrypoint


@given("Pydantic is not installed")
def step_pydantic_not_installed(context: BatchJobBehaveContext) -> None:
    """Simulate environment where Pydantic is not installed."""
    patcher = patch.dict("sys.modules", {"pydantic": None})
    patcher.start()
    context.pydantic_patcher = patcher


@given(
    "an entrypoint decorated with BatchJob "
    "expecting an invalid dictionary type",
)
def step_entrypoint_with_invalid_dict(
    context: BatchJobBehaveContext,
) -> None:
    """Prepare an entrypoint expecting an invalid dictionary type."""

    @BatchJob()
    def entrypoint(args: dict[str, int], ctx: SparkJobContext) -> None:
        context.received_args = args
        context.received_context = ctx

    context.entrypoint = entrypoint


@given("the AWS Glue service returns job run telemetry")
def step_glue_service_returns_telemetry(
    context: BatchJobBehaveContext,
) -> None:
    """Configure mock Glue client with standard telemetry payload."""
    mock_client = MagicMock()
    mock_client.get_job_run.return_value = _create_mock_job_run_payload()
    _patch_glue_client(context, mock_client)


@given("the job is launched with CLI arguments")
@given("the job is launched with CLI arguments:")
def step_job_launched_with_cli_arguments(
    context: BatchJobBehaveContext,
) -> None:
    """Construct custom argv vector from step table rows."""
    argv = ["script"]
    if context.table:
        for row in context.table:
            argv.extend([row["argument"], row["value"]])
    context.custom_argv = argv


@given(
    "a job run with {timeout:d} minutes timeout"
    " that started {elapsed:d} minutes ago",
)
def step_job_run_with_timing(
    context: BatchJobBehaveContext,
    timeout: int,
    elapsed: int,
) -> None:
    """Create a standalone SparkJobRun instance with timing values."""
    now = datetime.now(UTC)
    context.tested_job_run = SparkJobRun(
        attempt=1,
        started_on=now - timedelta(minutes=elapsed),
        timeout=timeout,
        worker_type="G.1X",
        number_of_workers=2,
        glue_version="5.0",
    )


@given('the entrypoint raises a RuntimeError "{message}"')
def step_entrypoint_raises(
    context: BatchJobBehaveContext,
    message: str,
) -> None:
    """Configure the entrypoint to raise with the given message."""
    context.raise_in_body = True
    context.expected_error_message = message


@given("the AWS Glue service is unreachable due to network timeout")
def step_glue_service_network_timeout(
    context: BatchJobBehaveContext,
) -> None:
    """Configure mock Glue client to simulate network endpoint failure."""
    mock_client = MagicMock()
    mock_client.get_job_run.side_effect = EndpointConnectionError(
        endpoint_url="https://glue.us-east-1.amazonaws.com",
    )
    _patch_glue_client(context, mock_client, run_id="jr_conn")


@given('the AWS Glue service fails with ClientError "{code}"')
def step_glue_service_client_error(
    context: BatchJobBehaveContext,
    code: str,
) -> None:
    """Configure mock Glue client to simulate arbitrary AWS ClientError."""
    mock_client = MagicMock()
    mock_client.get_job_run.side_effect = ClientError(
        {"Error": {"Code": code, "Message": f"AWS error: {code}"}},
        "GetJobRun",
    )
    _patch_glue_client(context, mock_client, run_id="jr_err")


# =============================================================================
# When Steps (Act)
# =============================================================================


@when("the entrypoint is called")
def step_call_entrypoint(context: BatchJobBehaveContext) -> None:
    """Invoke the entrypoint under real Glue/Spark."""
    assert context.entrypoint is not None
    argv = context.custom_argv or sys.argv
    with (
        patch.object(sys, "argv", argv),
        patch("aws_glue_powertools.job.Job") as mock_job_class,
    ):
        with _capture_error(context):
            context.entrypoint()
        mock_job = mock_job_class.return_value
        context.spy_init = mock_job.init
        context.spy_commit = mock_job.commit


@when("accessing lazy job telemetry")
def step_access_lazy_telemetry(context: BatchJobBehaveContext) -> None:
    """Access lazy property on tested_job_info capturing any exception."""
    assert context.tested_job_info is not None
    with _capture_error(context):
        _ = context.tested_job_info.run


@when("calculating remaining execution time")
def step_calculate_remaining_time(context: BatchJobBehaveContext) -> None:
    """Calculate remaining execution time on tested_job_run."""
    assert context.tested_job_run is not None
    context.remaining_millis = (
        context.tested_job_run.get_remaining_time_in_millis()
    )


# =============================================================================
# Then Steps (Assert)
# =============================================================================


# --- Lifecycle ---


@then("the job is initialized")
def step_job_initialized(context: BatchJobBehaveContext) -> None:
    """Assert job.init() was called."""
    assert context.spy_init is not None
    context.spy_init.assert_called_once()


@then("the job is not initialized")
def step_job_not_initialized(context: BatchJobBehaveContext) -> None:
    """Assert job.init() was not called."""
    assert context.spy_init is not None
    context.spy_init.assert_not_called()


@then("the job is committed")
def step_job_committed(context: BatchJobBehaveContext) -> None:
    """Assert job.commit() was called."""
    assert context.spy_commit is not None
    context.spy_commit.assert_called_once()


@then("the job is not committed")
def step_job_not_committed(context: BatchJobBehaveContext) -> None:
    """Assert job.commit() was not called."""
    assert context.spy_commit is not None
    context.spy_commit.assert_not_called()


# --- Context & Arguments ---


@then("the entrypoint receives business arguments and a SparkJobContext")
def step_receives_business_args_and_context(
    context: BatchJobBehaveContext,
) -> None:
    """Assert business args and SparkJobContext were received."""
    assert isinstance(context.received_args, dict)
    assert "JOB_NAME" not in context.received_args
    assert "JOB_RUN_ID" not in context.received_args
    assert isinstance(context.received_context, SparkJobContext)
    assert isinstance(context.received_context.glue, GlueContext)
    assert isinstance(context.received_context.job, SparkJobInfo)


@then(
    "the entrypoint receives a validated Pydantic model "
    "with batch_id {batch_id:d} and dry_run {dry_run}",
)
def step_receives_validated_pydantic_model(
    context: BatchJobBehaveContext,
    batch_id: int,
    dry_run: str,
) -> None:
    """Assert entrypoint received validated Pydantic model."""
    assert isinstance(context.received_args, _SampleModel)
    assert context.received_args.batch_id == batch_id
    expected_dry_run = dry_run.lower() == "true"
    assert context.received_args.dry_run is expected_dry_run


@then("business arguments match exactly")
@then("business arguments match exactly:")
def step_business_args_match_exactly(
    context: BatchJobBehaveContext,
) -> None:
    """Assert business arguments match table key-value pairs exactly."""
    assert isinstance(context.received_args, dict)
    assert context.table is not None
    expected = {row["key"]: row["value"] for row in context.table}
    assert context.received_args == expected


@then("the job metadata matches")
@then("the job metadata matches:")
def step_job_metadata_matches(context: BatchJobBehaveContext) -> None:
    """Assert curated attributes on SparkJobInfo match table values."""
    assert context.received_context is not None
    assert context.table is not None
    job = context.received_context.job
    expected = {row["attribute"]: row["value"] for row in context.table}
    assert job.name == expected["name"]
    assert job.run_id == expected["run_id"]
    assert job.bookmark_option == expected["bookmark_option"]
    assert str(job.auto_scaling_enabled) == expected["auto_scaling_enabled"]
    assert job.temp_dir == expected["temp_dir"]


@then('datalake formats include "{fmt1}" and "{fmt2}"')
def step_datalake_formats_include(
    context: BatchJobBehaveContext,
    fmt1: str,
    fmt2: str,
) -> None:
    """Assert datalake formats tuple contains expected formats."""
    assert context.received_context is not None
    formats = context.received_context.job.datalake_formats
    assert fmt1 in formats
    assert fmt2 in formats


# --- Telemetry ---


@then("accessing job run telemetry calls get_job_run exactly once")
def step_lazy_calls_once(context: BatchJobBehaveContext) -> None:
    """Assert single API call across multiple lazy property accesses."""
    assert context.received_context is not None
    job = context.received_context.job
    assert context.mock_glue_client is not None

    _ = (
        job.run.worker_type,
        job.run.number_of_workers,
        job.run.attempt,
        job.run.started_on,
        job.run.timeout,
        job.run.glue_version,
        job.run.execution_class,
    )
    context.mock_glue_client.get_job_run.assert_called_once()


@then("job run telemetry matches")
@then("job run telemetry matches:")
def step_telemetry_matches(context: BatchJobBehaveContext) -> None:
    """Assert runtime telemetry fields match table values."""
    assert context.received_context is not None
    assert context.table is not None
    run = context.received_context.job.run
    expected = {row["attribute"]: row["value"] for row in context.table}
    assert run.worker_type == expected["worker_type"]
    assert str(run.number_of_workers) == expected["number_of_workers"]
    assert str(run.attempt) == expected["attempt"]
    assert run.glue_version == expected["glue_version"]
    assert run.execution_class == expected["execution_class"]


@then("the remaining time in milliseconds is greater than zero")
def step_remaining_time_positive(context: BatchJobBehaveContext) -> None:
    """Assert remaining time calculation is positive."""
    assert context.remaining_millis is not None
    assert context.remaining_millis > 0


# --- Exception & Error Assertions ---


@then("the entrypoint completes without error")
def step_no_error(context: BatchJobBehaveContext) -> None:
    """Assert no exception was raised."""
    assert context.execution_error is None, (
        f"expected no error, got {context.execution_error!r}"
    )


@then('a RuntimeError "{message}" is propagated to the caller')
def step_exception_propagated(
    context: BatchJobBehaveContext,
    message: str,
) -> None:
    """Assert RuntimeError with expected message reached caller."""
    error = context.execution_error
    assert isinstance(error, RuntimeError), (
        f"expected RuntimeError, got {type(error).__name__}: {error!r}"
    )
    assert str(error) == message, (
        f"expected message {message!r}, got {str(error)!r}"
    )


@then("a PermissionError is raised indicating missing IAM permissions")
def step_permission_error_raised(context: BatchJobBehaveContext) -> None:
    """Assert PermissionError was captured."""
    assert isinstance(context.execution_error, GluePermissionError)
    assert isinstance(context.execution_error, PermissionError)
    assert "glue:GetJobRun" in str(context.execution_error)


@then("a ConnectionError is raised indicating network or VPC failure")
def step_connection_error_raised(context: BatchJobBehaveContext) -> None:
    """Assert ConnectionError was captured."""
    assert isinstance(context.execution_error, GlueConnectionError)
    assert isinstance(context.execution_error, ConnectionError)
    assert "VPC" in str(context.execution_error)


@then('a ClientError "{code}" is propagated to the caller')
def step_client_error_propagated(
    context: BatchJobBehaveContext,
    code: str,
) -> None:
    """Assert ClientError with expected code was propagated."""
    assert isinstance(context.execution_error, ClientError)
    error_dict = context.execution_error.response.get("Error", {})
    assert error_dict.get("Code") == code


@then("a JobArgumentValidationError is propagated to the caller")
def step_arg_validation_error_propagated(
    context: BatchJobBehaveContext,
) -> None:
    """Assert JobArgumentValidationError reached caller."""
    assert isinstance(context.execution_error, JobArgumentValidationError)


@then("an UnsupportedArgumentTypeError is propagated to the caller")
def step_unsupported_type_error_propagated(
    context: BatchJobBehaveContext,
) -> None:
    """Assert UnsupportedArgumentTypeError reached caller."""
    assert isinstance(context.execution_error, UnsupportedArgumentTypeError)
