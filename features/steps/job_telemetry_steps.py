"""Step definitions for lazy job run telemetry and execution timing."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

from behave import given, then
from botocore.exceptions import ClientError, EndpointConnectionError

from aws_glue_powertools.exceptions import (
    GlueConnectionError,
    GluePermissionError,
)
from features.helpers import make_batch_entrypoint, patch_glue_client

if TYPE_CHECKING:
    from features.steps.context_types import BatchJobBehaveContext


# =============================================================================
# Mock Helpers
# =============================================================================


def _mock_job_run_response(
    context: BatchJobBehaveContext,
    job_run: dict[str, object],
) -> None:
    """Mock Glue GetJobRun to return the provided JobRun payload."""
    mock_client = MagicMock()
    mock_client.get_job_run.return_value = {"JobRun": job_run}
    patch_glue_client(context, mock_client)


def _mock_job_run_error(
    context: BatchJobBehaveContext,
    error: Exception,
) -> None:
    """Mock Glue GetJobRun to raise the provided exception."""
    mock_client = MagicMock()
    mock_client.get_job_run.side_effect = error
    patch_glue_client(context, mock_client)


# =============================================================================
# Given Steps (Arrange)
# =============================================================================

# --- Entrypoints ---


@given("a BatchJob entrypoint that reads all job run telemetry")
def step_entrypoint_reads_telemetry(context: BatchJobBehaveContext) -> None:
    """Prepare a BatchJob entrypoint that reads all ctx.run telemetry."""
    context.telemetry_action = "read_all"
    context.entrypoint = make_batch_entrypoint(context)


@given("a BatchJob entrypoint that reads remaining execution time")
def step_entrypoint_checks_remaining_time(
    context: BatchJobBehaveContext,
) -> None:
    """Prepare a BatchJob entrypoint that reads remaining run time."""
    context.telemetry_action = "remaining_time"
    context.entrypoint = make_batch_entrypoint(context)


# --- AWS Glue Telemetry Payloads ---


@given("AWS Glue returns job run details:")
def step_glue_returns_telemetry(context: BatchJobBehaveContext) -> None:
    """Configure mock Glue client using telemetry values from step table."""
    assert context.table is not None
    fields = {row["field"]: row["value"] for row in context.table}
    _mock_job_run_response(
        context,
        {
            "Attempt": int(fields["attempt"]),
            "StartedOn": datetime.now(UTC) - timedelta(minutes=5),
            "Timeout": int(fields["timeout_minutes"]),
            "WorkerType": fields["worker_type"],
            "NumberOfWorkers": int(fields["number_of_workers"]),
            "GlueVersion": fields["glue_version"],
            "ExecutionClass": fields["execution_class"],
        },
    )


@given(
    "AWS Glue returns a job run with a {timeout:d} minute timeout"
    " started {elapsed:d} minutes ago",
)
def step_glue_returns_timing(
    context: BatchJobBehaveContext,
    timeout: int,
    elapsed: int,
) -> None:
    """Configure mock Glue client with timeout and elapsed duration."""
    _mock_job_run_response(
        context,
        {
            "Attempt": 1,
            "StartedOn": datetime.now(UTC) - timedelta(minutes=elapsed),
            "Timeout": timeout,
            "WorkerType": "G.1X",
            "NumberOfWorkers": 2,
            "GlueVersion": "5.0",
        },
    )


# --- AWS Glue Service Errors ---


@given('AWS Glue returns error "{code}"')
def step_glue_service_client_error(
    context: BatchJobBehaveContext,
    code: str,
) -> None:
    """Configure mock Glue client to raise an AWS ClientError."""
    _mock_job_run_error(
        context,
        ClientError(
            {"Error": {"Code": code, "Message": f"AWS error: {code}"}},
            "GetJobRun",
        ),
    )


@given("AWS Glue fails with a network timeout")
def step_glue_service_network_timeout(
    context: BatchJobBehaveContext,
) -> None:
    """Configure mock Glue client to simulate network endpoint failure."""
    _mock_job_run_error(
        context,
        EndpointConnectionError(
            endpoint_url="https://glue.us-east-1.amazonaws.com",
        ),
    )


# =============================================================================
# Then Steps (Assert)
# =============================================================================

# --- Telemetry Fetch & Fields ---


@then("AWS Glue receives one request for job run details")
def step_telemetry_fetched_once(context: BatchJobBehaveContext) -> None:
    """Assert AWS Glue GetJobRun API was invoked exactly once."""
    assert context.mock_glue_client is not None
    context.mock_glue_client.get_job_run.assert_called_once()


@then("the job run telemetry matches:")
def step_telemetry_matches(context: BatchJobBehaveContext) -> None:
    """Assert runtime telemetry fields match table values."""
    assert context.received_context is not None
    assert context.table is not None
    run = context.received_context.run
    expected = {row["attribute"]: row["value"] for row in context.table}
    actual = {
        "worker_type": run.worker_type,
        "number_of_workers": str(run.number_of_workers),
        "attempt": str(run.attempt),
        "timeout": str(run.timeout),
        "glue_version": run.glue_version,
        "execution_class": run.execution_class,
    }
    assert actual == expected


# --- Error Translation ---


@then('the caller receives GluePermissionError requiring "{action}"')
def step_permission_error_raised(
    context: BatchJobBehaveContext,
    action: str,
) -> None:
    """Assert GluePermissionError mentioning the IAM action was raised."""
    assert isinstance(context.execution_error, GluePermissionError)
    assert isinstance(context.execution_error, PermissionError)
    assert action in str(context.execution_error)


@then("the caller receives GlueConnectionError for VPC or network failure")
def step_connection_error_raised(context: BatchJobBehaveContext) -> None:
    """Assert GlueConnectionError mentioning VPC failure was raised."""
    assert isinstance(context.execution_error, GlueConnectionError)
    assert isinstance(context.execution_error, ConnectionError)
    assert "VPC" in str(context.execution_error)


@then('the caller receives ClientError "{code}"')
def step_client_error_propagated(
    context: BatchJobBehaveContext,
    code: str,
) -> None:
    """Assert ClientError with expected AWS error code reached caller."""
    assert isinstance(context.execution_error, ClientError)
    error_dict = context.execution_error.response.get("Error", {})
    assert error_dict.get("Code") == code


# --- Remaining Execution Time ---


@then("the remaining execution time is {expectation}")
def step_remaining_time(
    context: BatchJobBehaveContext,
    expectation: str,
) -> None:
    """Assert remaining execution time satisfies expected bound."""
    assert context.remaining_time is not None
    if expectation == "zero":
        assert context.remaining_time == timedelta(0)
        return
    assert expectation == "greater than zero"
    assert context.remaining_time > timedelta(0)
