"""Behave test environment hooks (fixtures, setup/teardown)."""

import sys

from pyspark.context import SparkContext


def before_scenario(_context: object, scenario: object) -> None:
    """Set sys.argv for scenarios tagged @glue_job."""
    if "glue_job" in scenario.effective_tags:  # type: ignore[attr-defined]
        sys.argv = ["test_script", "--JOB_NAME", "test"]


def after_scenario(_context: object, scenario: object) -> None:
    """Stop Spark after @glue_job scenarios; uses ``getOrCreate().stop()``."""
    if "glue_job" in scenario.effective_tags:  # type: ignore[attr-defined]
        SparkContext.getOrCreate().stop()
