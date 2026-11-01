"""Automatic Glue batch job lifecycle management."""

from __future__ import annotations

import functools
import sys
from dataclasses import dataclass
from typing import TYPE_CHECKING

from awsglue.context import GlueContext
from awsglue.job import Job
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext

if TYPE_CHECKING:
    from collections.abc import Callable
    from types import TracebackType


@dataclass(frozen=True, slots=True, kw_only=True)
class SparkJobContext:
    """Immutable runtime context for Spark Batch jobs.

    Attributes:
        glue_context: Initialized GlueContext instance.
    """

    glue_context: GlueContext


class BatchJob:
    """Spark Batch job lifecycle manager (decorator & context manager)."""

    def __init__(self) -> None:
        """Initialize the batch job manager."""
        super().__init__()
        self._job: Job | None = None

    def __enter__(self) -> tuple[dict[str, str], SparkJobContext]:
        """Resolve CLI options from argv and initialize the Glue job."""
        args = getResolvedOptions(sys.argv, ["JOB_NAME"])
        sc = SparkContext.getOrCreate()
        gc = GlueContext(sc)
        self._job = Job(gc)
        self._job.init(args["JOB_NAME"], args)
        return args, SparkJobContext(glue_context=gc)

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        _val: BaseException | None,
        _tb: TracebackType | None,
    ) -> None:
        """Commit job bookmarks only on successful completion."""
        try:
            if exc_type is None and self._job is not None:
                self._job.commit()
        finally:
            self._job = None

    def __call__(
        self,
        func: Callable[[dict[str, str], SparkJobContext], None],
    ) -> Callable[[], None]:
        """Wrap an entrypoint accepting (args, context)."""

        @functools.wraps(func)
        def wrapper() -> None:
            with self as (args, ctx):
                func(args, ctx)

        return wrapper
