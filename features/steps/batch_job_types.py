"""Types for Batch job Behave ``context`` attributes."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Callable
    from unittest.mock import MagicMock

    from behave.model import Table

    from aws_glue_powertools.job import (
        SparkJobContext,
        SparkJobInfo,
        SparkJobRun,
    )


class BatchJobBehaveContext(Protocol):
    """Attributes set and read by batch job step definitions."""

    table: Table | None
    raise_in_body: bool
    execution_error: Exception | None
    expected_error_message: str
    entrypoint: Callable[[], None] | None
    custom_argv: list[str] | None
    spy_init: MagicMock | None
    spy_commit: MagicMock | None
    received_args: object | None
    received_context: SparkJobContext | None
    mock_glue_client: MagicMock | None
    mock_patcher: object | None
    pydantic_patcher: object | None
    tested_job_info: SparkJobInfo | None
    tested_job_run: SparkJobRun | None
    remaining_millis: int | None
