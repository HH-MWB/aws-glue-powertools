"""Automatic Glue batch job management."""

from __future__ import annotations

import functools
import sys
from typing import TYPE_CHECKING

from awsglue.context import GlueContext
from awsglue.job import Job
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext

if TYPE_CHECKING:
    from collections.abc import Callable
    from types import TracebackType
    from typing import Self


class BatchJob:
    """Decorator and context manager for automatic Glue batch job handling.

    Builds ``SparkContext``, ``GlueContext``, and ``Job`` at construction.
    Resolves argv and calls ``job.init()`` on context entry, and
    ``job.commit()`` only when the block exits without an exception.
    """

    def __init__(self) -> None:
        """Create Spark/Glue contexts and the Glue ``Job`` instance."""
        spark_context = SparkContext()
        glue_context = GlueContext(spark_context)
        self._job = Job(glue_context)

    def __enter__(self) -> Self:
        """Resolve job args from argv and initialize the Glue job."""
        args = getResolvedOptions(sys.argv, ["JOB_NAME"])
        self._job.init(args["JOB_NAME"], args)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Commit only when the block exits without an exception."""
        if exc_type is None:
            self._job.commit()

    def __call__(self, func: Callable[[], None]) -> Callable[[], None]:
        """Wrap a parameterless entrypoint (e.g. ``main``)."""

        @functools.wraps(func)
        def wrapper() -> None:
            with self:
                func()

        return wrapper
