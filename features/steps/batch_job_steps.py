"""Step definitions for the Batch job feature."""

from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING
from unittest.mock import patch

if TYPE_CHECKING:
    from collections.abc import Iterator

    from features.steps.batch_job_types import BatchJobBehaveContext

from behave import given, then, when

from aws_glue_powertools.job import BatchJob


@contextmanager
def _capture_error(bdd_context: BatchJobBehaveContext) -> Iterator[None]:
    """Capture RuntimeError on bdd_context.execution_error."""
    try:
        yield
    except RuntimeError as error:
        bdd_context.execution_error = error


def _reset_context(context: BatchJobBehaveContext) -> None:
    context.raise_in_body = False
    context.execution_error = None
    context.expected_error_message = ""
    context.entrypoint = None
    context.spy_init = None
    context.spy_commit = None


@given("a script entrypoint decorated with BatchJob")
def step_decorated_entrypoint(context: BatchJobBehaveContext) -> None:
    """Prepare a callable to wrap with BatchJob when invoked."""
    _reset_context(context)

    def entrypoint() -> None:
        if context.raise_in_body:
            raise RuntimeError(context.expected_error_message)

    context.entrypoint = entrypoint


@given('the entrypoint raises a RuntimeError "{message}"')
def step_entrypoint_raises(
    context: BatchJobBehaveContext,
    message: str,
) -> None:
    """Configure the entrypoint to raise with the given message."""
    context.raise_in_body = True
    context.expected_error_message = message


@when("the entrypoint is called")
def step_call_entrypoint(context: BatchJobBehaveContext) -> None:
    """Invoke the entrypoint wrapped with BatchJob under real Glue/Spark."""
    assert context.entrypoint is not None
    with patch("aws_glue_powertools.job.Job") as mock_job_class:
        batch_job = BatchJob()
        mock_job = mock_job_class.return_value
        with _capture_error(context):
            batch_job(context.entrypoint)()
        context.spy_init = mock_job.init
        context.spy_commit = mock_job.commit


@given("a BatchJob context manager")
def step_context_manager(context: BatchJobBehaveContext) -> None:
    """Prepare state for a context-manager scenario."""
    _reset_context(context)


@given('the managed block raises a RuntimeError "{message}"')
def step_managed_block_raises(
    context: BatchJobBehaveContext,
    message: str,
) -> None:
    """Configure the managed block to raise with the given message."""
    context.raise_in_body = True
    context.expected_error_message = message


@when("the managed block is executed")
def step_run_managed_block(context: BatchJobBehaveContext) -> None:
    """Run the managed block with real Glue/Spark objects."""
    with patch("aws_glue_powertools.job.Job") as mock_job_class:
        batch_job = BatchJob()
        mock_job = mock_job_class.return_value
        with _capture_error(context), batch_job:
            if context.raise_in_body:
                raise RuntimeError(context.expected_error_message)
        context.spy_init = mock_job.init
        context.spy_commit = mock_job.commit


@then("the entrypoint completes without error")
@then("the managed block completes without error")
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
    """Assert RuntimeError with the expected message reached the caller."""
    error = context.execution_error
    assert isinstance(error, RuntimeError), (
        f"expected RuntimeError, got {type(error).__name__}: {error!r}"
    )
    assert str(error) == message, (
        f"expected message {message!r}, got {str(error)!r}"
    )


@then("the job is initialized")
def step_job_initialized(context: BatchJobBehaveContext) -> None:
    """Assert job.init() was called exactly once."""
    assert context.spy_init is not None
    context.spy_init.assert_called_once()


@then("the job is committed")
def step_job_committed(context: BatchJobBehaveContext) -> None:
    """Assert job.commit() was called exactly once."""
    assert context.spy_commit is not None
    context.spy_commit.assert_called_once()


@then("the job is not committed")
def step_job_not_committed(context: BatchJobBehaveContext) -> None:
    """Assert job.commit() was not called."""
    assert context.spy_commit is not None
    context.spy_commit.assert_not_called()
