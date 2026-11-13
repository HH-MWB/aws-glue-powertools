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
    # Behave harness and isolation
    ("saved_argv", None),
    # Arrange state
    ("entrypoint", None),
    ("custom_argv", None),
    ("raise_in_body", False),
    ("expected_error_message", ""),
    ("telemetry_action", None),
    ("mock_glue_client", None),
    ("mock_patcher", None),
    ("pydantic_patcher", None),
    # Act and assert state
    ("spy_init", None),
    ("spy_commit", None),
    ("received_args", None),
    ("received_context", None),
    ("execution_error", None),
    ("remaining_time", None),
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


def _stop_patchers(context: object) -> None:
    """Stop and clear any active unittest mock patchers on context."""
    for patcher_attr in ("mock_patcher", "pydantic_patcher"):
        patcher = getattr(context, patcher_attr, None)
        if patcher is not None:
            patcher.stop()
            setattr(context, patcher_attr, None)


def _spark_was_initialized(context: object) -> bool:
    """Return True if the scenario initialized a Glue/Spark job."""
    spy_init = getattr(context, "spy_init", None)
    call_count: object = getattr(spy_init, "call_count", 0)
    return isinstance(call_count, int) and call_count > 0


# =============================================================================
# Behave Lifecycle Hooks
# =============================================================================


def before_scenario(context: object, _scenario: object) -> None:
    """Initialize scenario context, isolate sys.argv, and capture stderr."""
    for attr, val in _DEFAULT_SCENARIO_ATTRIBUTES:
        setattr(context, attr, val)
    context.saved_argv = list(sys.argv)  # type: ignore[attr-defined]
    sys.argv = list(_DEFAULT_GLUE_ARGV)
    _stderr_capture.start()


def after_scenario(context: object, scenario: object) -> None:
    """Restore sys.argv, stop patchers/Spark, and restore captured stderr."""
    _stop_patchers(context)
    saved_argv = getattr(context, "saved_argv", None)
    if saved_argv is not None:
        sys.argv = saved_argv
    if _spark_was_initialized(context):
        SparkContext.getOrCreate().stop()
    is_failed = getattr(scenario, "status", None) == "failed"
    _stderr_capture.stop(dump=is_failed)
