"""Types for Batch job Behave ``context`` attributes."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Callable
    from datetime import timedelta
    from unittest.mock import MagicMock

    from behave.model import Table

    from aws_glue_powertools.jobs.spark import SparkJobContext


class BatchJobBehaveContext(Protocol):
    """Attributes set and read by batch job step definitions."""

    # Behave harness and isolation
    table: Table | None
    saved_argv: list[str] | None

    # Arrange state
    entrypoint: Callable[[], None] | None
    custom_argv: list[str] | None
    raise_in_body: bool
    expected_error_message: str
    telemetry_action: str | None
    mock_glue_client: MagicMock | None
    mock_patcher: object | None
    pydantic_patcher: object | None

    # Act and assert state
    spy_init: MagicMock | None
    spy_commit: MagicMock | None
    received_args: object | None
    received_context: SparkJobContext | None
    execution_error: Exception | None
    remaining_time: timedelta | None
