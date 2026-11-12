"""Step definitions for Glue batch job lifecycle scenarios."""

from __future__ import annotations

from typing import TYPE_CHECKING

from behave import given, then

from aws_glue_powertools.jobs.spark import SparkJobInfo
from features.helpers import is_spark_job_context

if TYPE_CHECKING:
    from features.steps.context_types import BatchJobBehaveContext


# =============================================================================
# Given Steps (Arrange)
# =============================================================================


@given('the entrypoint raises RuntimeError "{message}"')
def step_entrypoint_raises(
    context: BatchJobBehaveContext,
    message: str,
) -> None:
    """Configure the entrypoint body to raise RuntimeError."""
    context.raise_in_body = True
    context.expected_error_message = message


# =============================================================================
# Then Steps (Assert)
# =============================================================================


@then("the entrypoint receives business arguments and a SparkJobContext")
def step_receives_business_args_and_context(
    context: BatchJobBehaveContext,
) -> None:
    """Assert business args dictionary and SparkJobContext were received."""
    assert context.execution_error is None
    assert isinstance(context.received_args, dict)
    assert "JOB_NAME" not in context.received_args
    assert "JOB_RUN_ID" not in context.received_args
    assert context.received_context is not None
    assert is_spark_job_context(context.received_context)
    assert isinstance(context.received_context.job, SparkJobInfo)


@then('the caller receives RuntimeError "{message}"')
def step_caller_receives_runtime_error(
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
