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


@dataclass(frozen=True, slots=True, kw_only=True)
class SparkJobContext:
    """Immutable runtime context for Spark Batch jobs.

    Attributes:
        glue: Initialized GlueContext instance.
    """

    glue: GlueContext


class BatchJob:
    """Spark Batch job lifecycle decorator."""

    def __call__(
        self,
        func: Callable[[dict[str, str], SparkJobContext], None],
    ) -> Callable[[], None]:
        """Wrap an entrypoint accepting (args, context)."""

        @functools.wraps(func)
        def wrapper() -> None:
            args = getResolvedOptions(sys.argv, ["JOB_NAME"])
            ctx = SparkJobContext(
                glue=GlueContext(SparkContext.getOrCreate()),
            )
            job = Job(ctx.glue)
            job.init(args["JOB_NAME"], args)
            func(args, ctx)
            job.commit()

        return wrapper
