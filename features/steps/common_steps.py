"""Shared Behave step definitions for BatchJob execution and lifecycle."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING
from unittest.mock import patch

from behave import given, then, when

from features.helpers import capture_error, make_batch_entrypoint

if TYPE_CHECKING:
    from features.steps.context_types import BatchJobBehaveContext


# =============================================================================
# Given Steps (Arrange)
# =============================================================================


@given("an entrypoint decorated with BatchJob")
def step_entrypoint_decorated(context: BatchJobBehaveContext) -> None:
    """Prepare a standard dict-typed entrypoint decorated with BatchJob."""
    context.entrypoint = make_batch_entrypoint(context)


@given("the caller passes CLI arguments:")
def step_caller_passes_cli_arguments(
    context: BatchJobBehaveContext,
) -> None:
    """Construct custom argv vector from step table rows."""
    argv = ["script"]
    if context.table:
        for row in context.table:
            argv.extend([row["argument"], row["value"]])
    context.custom_argv = argv


# =============================================================================
# When Steps (Act)
# =============================================================================


@when("the caller runs the entrypoint")
def step_caller_runs_entrypoint(context: BatchJobBehaveContext) -> None:
    """Invoke the entrypoint under patched sys.argv and Glue Job."""
    assert context.entrypoint is not None
    argv = context.custom_argv or sys.argv
    with (
        patch.object(sys, "argv", argv),
        patch("aws_glue_powertools.jobs.spark.Job") as mock_job_class,
    ):
        with capture_error(context):
            context.entrypoint()
        mock_job = mock_job_class.return_value
        context.spy_init = mock_job.init
        context.spy_commit = mock_job.commit


# =============================================================================
# Then Steps (Assert)
# =============================================================================


@then("the Glue job is initialized")
def step_job_initialized(context: BatchJobBehaveContext) -> None:
    """Assert job.init() was called once."""
    assert context.spy_init is not None
    context.spy_init.assert_called_once()


@then("the Glue job is not initialized")
def step_job_not_initialized(context: BatchJobBehaveContext) -> None:
    """Assert job.init() was not called."""
    assert context.spy_init is not None
    context.spy_init.assert_not_called()


@then("the Glue job is committed")
def step_job_committed(context: BatchJobBehaveContext) -> None:
    """Assert job.commit() was called once."""
    assert context.spy_commit is not None
    context.spy_commit.assert_called_once()


@then("the Glue job is not committed")
def step_job_not_committed(context: BatchJobBehaveContext) -> None:
    """Assert job.commit() was not called."""
    assert context.spy_commit is not None
    context.spy_commit.assert_not_called()
