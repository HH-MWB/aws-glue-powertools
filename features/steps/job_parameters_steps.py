"""Step definitions for CLI parameter filtering and metadata mapping."""

from __future__ import annotations

from typing import TYPE_CHECKING

from behave import then

if TYPE_CHECKING:
    from features.steps.context_types import BatchJobBehaveContext


# =============================================================================
# Then Steps (Assert)
# =============================================================================


@then("the entrypoint receives exact business arguments:")
def step_business_args_match_exactly(
    context: BatchJobBehaveContext,
) -> None:
    """Assert business arguments match table key-value pairs exactly."""
    assert isinstance(context.received_args, dict)
    assert context.table is not None
    expected = {row["key"]: row["value"] for row in context.table}
    assert context.received_args == expected


@then("the job metadata matches:")
def step_job_metadata_matches(context: BatchJobBehaveContext) -> None:
    """Assert curated attributes on SparkJobInfo match table values."""
    assert context.received_context is not None
    assert context.table is not None
    job = context.received_context.job
    expected = {row["attribute"]: row["value"] for row in context.table}
    actual = {
        "name": job.name,
        "run_id": job.run_id,
        "bookmark_option": job.bookmark_option,
        "auto_scaling_enabled": str(job.auto_scaling_enabled).lower(),
        "datalake_formats": ", ".join(job.datalake_formats),
        "temp_dir": job.temp_dir,
    }
    assert actual == expected
