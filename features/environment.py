"""Behave test environment hooks (fixtures, setup/teardown)."""

from __future__ import annotations

import io
import logging
import os
import sys
import tempfile
from typing import IO

from pyspark.context import SparkContext

# =============================================================================
# Scenario State & Fixtures
# =============================================================================

_DEFAULT_SCENARIO_ATTRIBUTES: tuple[tuple[str, object], ...] = (
    ("raise_in_body", False),
    ("execution_error", None),
    ("expected_error_message", ""),
    ("entrypoint", None),
    ("custom_argv", None),
    ("spy_init", None),
    ("spy_commit", None),
    ("received_args", None),
    ("received_context", None),
    ("mock_glue_client", None),
    ("mock_patcher", None),
    ("pydantic_patcher", None),
    ("tested_job_info", None),
    ("tested_job_run", None),
    ("remaining_millis", None),
)

_DEFAULT_GLUE_ARGV: tuple[str, ...] = (
    "test_script",
    "--JOB_NAME",
    "test",
    "--JOB_RUN_ID",
    "jr_test",
)

# =============================================================================
# Output Isolation & Diagnostics
# =============================================================================

# In-memory buffer capturing py4j logs without leaking to stderr
_py4j_log_stream = io.StringIO()
_py4j_handler = logging.StreamHandler(_py4j_log_stream)
_py4j_logger = logging.getLogger("py4j")
_py4j_logger.addHandler(_py4j_handler)
_py4j_logger.propagate = False


class _StderrCapture:
    """Redirect and capture OS file descriptor 2 (stderr).

    Buffers C-level and JVM stderr output (e.g. OpenJDK incubator warnings
    and Spark Log4j startup banners). If a scenario fails, the buffer is
    dumped to stderr for debugging; otherwise it is cleanly discarded.
    """

    def __init__(self) -> None:
        self.saved_fd: int | None = None
        self.captured: IO[bytes] | None = None

    def start(self) -> None:
        """Start redirecting OS stderr to a temporary buffer."""
        self.captured = tempfile.TemporaryFile(mode="w+b")  # noqa: SIM115
        self.saved_fd = os.dup(2)
        os.dup2(self.captured.fileno(), 2)

    def stop(self, *, dump: bool = False) -> None:
        """Restore OS stderr, dumping buffered output on failure."""
        if self.saved_fd is not None and self.captured is not None:
            os.dup2(self.saved_fd, 2)
            os.close(self.saved_fd)
            self.saved_fd = None
            if dump:
                self.captured.seek(0)
                sys.stderr.write(self.captured.read().decode(errors="replace"))
            self.captured.close()
            self.captured = None


_stderr_capture = _StderrCapture()

# =============================================================================
# Behave Lifecycle Hooks
# =============================================================================


def before_scenario(context: object, scenario: object) -> None:
    """Initialize scenario context attributes and argv before execution."""
    for attr, val in _DEFAULT_SCENARIO_ATTRIBUTES:
        setattr(context, attr, val)
    if "glue_job" in scenario.effective_tags:  # type: ignore[attr-defined]
        _stderr_capture.start()
        sys.argv = list(_DEFAULT_GLUE_ARGV)


def after_scenario(context: object, scenario: object) -> None:
    """Tear down Spark, cleanup mock patches, and restore captured stderr."""
    for patcher_attr in ("mock_patcher", "pydantic_patcher"):
        patcher = getattr(context, patcher_attr, None)
        if patcher is not None:
            patcher.stop()
            setattr(context, patcher_attr, None)
    if "glue_job" in scenario.effective_tags:  # type: ignore[attr-defined]
        SparkContext.getOrCreate().stop()
    is_failed = getattr(scenario, "status", None) == "failed"
    _stderr_capture.stop(dump=is_failed)
