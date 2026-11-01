"""Step definitions for the Batch job feature."""

from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING
from unittest.mock import patch

if TYPE_CHECKING:
    from collections.abc import Iterator

    from features.steps.batch_job_types import BatchJobBehaveContext

from awsglue.context import GlueContext
from behave import given, then, when

from aws_glue_powertools.job import BatchJob, SparkJobContext

# =============================================================================
# Helpers
# =============================================================================


@contextmanager
def _capture_error(bdd_context: BatchJobBehaveContext) -> Iterator[None]:
    """Capture Exception on bdd_context.execution_error."""
    try:
        yield
    except Exception as error:  # noqa: BLE001
        bdd_context.execution_error = error


def _reset_context(context: BatchJobBehaveContext) -> None:
    context.raise_in_body = False
    context.execution_error = None
    context.expected_error_message = ""
    context.entrypoint = None
    context.spy_init = None
    context.spy_commit = None
    context.received_args = None
    context.received_context = None


# =============================================================================
# Given Steps (Setup)
# =============================================================================


@given("an entrypoint decorated with BatchJob")
def step_entrypoint_decorated(context: BatchJobBehaveContext) -> None:
    """Prepare an entrypoint decorated with BatchJob()."""
    _reset_context(context)

    @BatchJob()
    def entrypoint(args: dict[str, str], ctx: SparkJobContext) -> None:
        if context.raise_in_body:
            raise RuntimeError(context.expected_error_message)
        context.received_args = args
        context.received_context = ctx

    context.entrypoint = entrypoint


@given('the entrypoint raises a RuntimeError "{message}"')
def step_entrypoint_raises(
    context: BatchJobBehaveContext,
    message: str,
) -> None:
    """Configure the entrypoint to raise with the given message."""
    context.raise_in_body = True
    context.expected_error_message = message


# =============================================================================
# When Steps (Execution)
# =============================================================================


@when("the entrypoint is called")
def step_call_entrypoint(context: BatchJobBehaveContext) -> None:
    """Invoke the entrypoint under real Glue/Spark."""
    assert context.entrypoint is not None
    with patch("aws_glue_powertools.job.Job") as mock_job_class:
        with _capture_error(context):
            context.entrypoint()
        mock_job = mock_job_class.return_value
        context.spy_init = mock_job.init
        context.spy_commit = mock_job.commit


# =============================================================================
# Then Steps (Assertions)
# =============================================================================

# --- Lifecycle: Initialization ---


@then("the job is initialized")
def step_job_initialized(context: BatchJobBehaveContext) -> None:
    """Assert job.init() was called."""
    assert context.spy_init is not None
    context.spy_init.assert_called_once()


# --- Parameter & Context Injection ---


@then("the entrypoint receives job arguments and a SparkJobContext")
def step_receives_args_and_context(context: BatchJobBehaveContext) -> None:
    """Assert args and SparkJobContext were received."""
    assert context.received_args is not None
    assert context.received_args.get("JOB_NAME") == "test"
    assert isinstance(context.received_context, SparkJobContext)
    assert isinstance(context.received_context.glue, GlueContext)


# --- Execution Outcomes ---


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


# --- Lifecycle: Commit / Teardown ---


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
