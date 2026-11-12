"""Shared test schemas, mock fixtures, and assertion helpers."""

from __future__ import annotations

import ast
import dataclasses
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import TYPE_CHECKING
from unittest.mock import patch

from awsglue.context import GlueContext
from pydantic import BaseModel

from aws_glue_powertools.jobs.spark import BatchJob, SparkJobContext

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator
    from unittest.mock import MagicMock

    from behave.model import Table

    from features.steps.context_types import BatchJobBehaveContext


# =============================================================================
# Test Argument Schemas
# =============================================================================


@dataclass
class SampleDataclass:
    """Sample dataclass covering supported scalars, collections, and flags."""

    batch_id: int
    name: str
    rate: float
    dry_run: bool = False
    tags: list[str] = field(default_factory=list)
    scores: list[int] = field(default_factory=list)
    items: list = field(default_factory=list)  # type: ignore[type-arg]
    modes: tuple[str, ...] = field(default_factory=tuple)
    raw_tuple: tuple = field(default_factory=tuple)  # type: ignore[type-arg]
    unique_ids: set[int] = field(default_factory=set)
    raw_set: set = field(default_factory=set)  # type: ignore[type-arg]
    rates: frozenset[float] = field(default_factory=frozenset)
    raw_frozenset: frozenset = (  # type: ignore[type-arg]
        field(default_factory=frozenset)
    )
    optional_note: str | None = None
    derived_field: str = field(init=False, default="computed")


@dataclass
class DataclassWithUnsupportedField:
    """Dataclass containing an unsupported dictionary field."""

    config: dict[str, object]


@dataclass
class DataclassWithUnsupportedList:
    """Dataclass containing an unsupported boolean list field."""

    flags: list[bool]


@dataclass
class DataclassWithUnsupportedTuple:
    """Dataclass containing an unsupported heterogeneous tuple field."""

    coordinates: tuple[int, str]


@dataclass
class DataclassWithUnion:
    """Dataclass containing an unsupported multi-type union field."""

    val: int | str | None = None


class SampleModel(BaseModel):  # type: ignore[explicit-any]
    """Sample Pydantic model for typed argument validation."""

    batch_id: int
    dry_run: bool = False


class UnsupportedClass:
    """Arbitrary non-dataclass, non-Pydantic user class."""


UNSUPPORTED_TYPE_MAP: dict[str, object] = {
    "dict[str, int]": dict[str, int],
    "dataclass dict[str, object]": DataclassWithUnsupportedField,
    "dataclass list[bool]": DataclassWithUnsupportedList,
    "dataclass tuple[int, str]": DataclassWithUnsupportedTuple,
    "dataclass int | str | None": DataclassWithUnion,
    "custom class": UnsupportedClass,
}


# =============================================================================
# Arrange & Act Helpers
# =============================================================================


def patch_glue_client(
    context: BatchJobBehaveContext,
    mock_client: MagicMock,
) -> None:
    """Attach mock Glue boto3 client to context and start patcher."""
    context.mock_glue_client = mock_client
    patcher = patch(
        "aws_glue_powertools.jobs.spark.boto3.client",
        return_value=mock_client,
    )
    context.mock_patcher = patcher
    patcher.start()


def _run_telemetry_action(
    context: BatchJobBehaveContext,
    ctx: SparkJobContext,
) -> None:
    """Execute any configured telemetry action inside an active job body."""
    if context.telemetry_action == "read_all":
        _ = (
            ctx.run.worker_type,
            ctx.run.number_of_workers,
            ctx.run.attempt,
            ctx.run.started_on,
            ctx.run.timeout,
            ctx.run.glue_version,
            ctx.run.execution_class,
        )
    elif context.telemetry_action == "remaining_time":
        context.remaining_time = ctx.run.get_remaining_time()


def make_batch_entrypoint(
    context: BatchJobBehaveContext,
    arg_type: object | None = None,
) -> Callable[[], None]:
    """Build a BatchJob-decorated entrypoint with the given arg annotation."""

    def entrypoint(args: object, ctx: SparkJobContext) -> None:
        if context.raise_in_body:
            raise RuntimeError(context.expected_error_message)
        context.received_args = args
        context.received_context = ctx
        _run_telemetry_action(context, ctx)

    entrypoint.__annotations__["args"] = (
        dict[str, str] if arg_type is None else arg_type
    )
    return BatchJob()(entrypoint)


@contextmanager
def capture_error(bdd_context: BatchJobBehaveContext) -> Iterator[None]:
    """Capture any raised exception onto bdd_context.execution_error."""
    try:
        yield
    except Exception as error:  # noqa: BLE001
        bdd_context.execution_error = error


# =============================================================================
# Assert Helpers
# =============================================================================

_EMPTY_COLLECTION_FACTORIES: dict[str, Callable[[], object]] = {
    "set()": set,
    "frozenset()": frozenset,
}


def is_spark_job_context(obj: object) -> bool:
    """Return True if obj is a SparkJobContext with GlueContext."""
    return isinstance(obj, SparkJobContext) and isinstance(
        obj.glue,
        GlueContext,
    )


def parse_expected(raw: str, actual: object) -> object:
    """Parse a Gherkin expectation cell into a typed Python value."""
    if isinstance(actual, str):
        return raw
    if raw in _EMPTY_COLLECTION_FACTORIES:
        return _EMPTY_COLLECTION_FACTORIES[raw]()
    if raw.startswith("frozenset(") and raw.endswith(")"):
        inner: object = ast.literal_eval(raw[10:-1])
        assert isinstance(inner, set)
        return frozenset(inner)
    parsed: object = ast.literal_eval(raw)
    return parsed


def _assert_field_types(field_types: dict[str, str], table: Table) -> None:
    """Assert declared dataclass field types match the Gherkin type column."""
    for row in table:
        name = row["field"]
        assert field_types[name] == row["type"], (
            f"field {name!r}: expected type {row['type']!r}, "
            f"got {field_types[name]!r}"
        )


def verify_dataclass_table(
    received: SampleDataclass,
    table: Table,
) -> None:
    """Assert dataclass fields, optional declared types, and values match."""
    fields = dataclasses.fields(received)
    expected = {row["field"]: row["value"] for row in table}
    assert set(expected) == {f.name for f in fields}
    if "type" in table.headings:
        field_types = {
            f.name: str(f.type) if f.init else f"{f.type} (init=False)"
            for f in fields
        }
        _assert_field_types(field_types, table)
    for field_name, raw_expected in expected.items():
        actual = getattr(received, field_name)
        assert actual == parse_expected(raw_expected, actual)
