"""Types for Batch job Behave ``context`` attributes."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Callable
    from unittest.mock import MagicMock


class BatchJobBehaveContext(Protocol):
    """Attributes set and read by batch job step definitions."""

    raise_in_body: bool
    execution_error: RuntimeError | None
    expected_error_message: str
    entrypoint: Callable[[], None] | None
    spy_init: MagicMock | None
    spy_commit: MagicMock | None
