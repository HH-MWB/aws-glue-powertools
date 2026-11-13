"""Shared test schemas, mock fixtures, and assertion helpers."""

from __future__ import annotations

import ast
import dataclasses
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import date, datetime, time
from typing import TYPE_CHECKING, cast
from unittest.mock import patch
from uuid import UUID

from awsglue.context import GlueContext
from pydantic import BaseModel

from aws_glue_powertools.jobs.spark import BatchJob, SparkJobContext

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Iterator
    from unittest.mock import MagicMock

    from _typeshed import DataclassInstance
    from behave.model import Table

    from features.steps.context_types import BatchJobBehaveContext


# =============================================================================
# Test Argument Schemas
# =============================================================================

SCALAR_TYPE_MAP: dict[str, type] = {
    "int": int,
    "str": str,
    "float": float,
    "bool": bool,
    "UUID": UUID,
    "datetime": datetime,
    "date": date,
    "time": time,
}


def make_scalar_dataclass(field_name: str, type_name: str) -> type:
    """Build dynamic single-field dataclass for scalar parsing tests."""
    target_type = SCALAR_TYPE_MAP[type_name]
    return dataclasses.make_dataclass(
        "DynamicScalarDataclass",
        [(field_name, target_type)],
    )


@dataclass
class CollectionDataclass:
    """Dataclass covering parameterized and bare collection containers."""

    scores: list[int] = field(default_factory=list)
    modes: tuple[str, ...] = field(default_factory=tuple)
    unique_ids: set[int] = field(default_factory=set)
    rates: frozenset[float] = field(default_factory=frozenset)
    items: list = field(default_factory=list)  # type: ignore[type-arg]
    raw_tuple: tuple = field(default_factory=tuple)  # type: ignore[type-arg]
    raw_set: set = field(default_factory=set)  # type: ignore[type-arg]
    raw_frozenset: frozenset = (  # type: ignore[type-arg]
        field(default_factory=frozenset)
    )


@dataclass
class LifecycleDataclass:
    """Dataclass covering required, default, optional, and derived fields."""

    required_val: str
    default_val: str = "default"
    optional_val: str | None = None
    derived_field: str = field(init=False, default="computed")


class SampleModel(BaseModel):  # type: ignore[explicit-any]
    """Sample Pydantic model for typed argument validation."""

    batch_id: int
    dry_run: bool = False


# --- Unsupported Argument Schemas ---


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


def is_spark_job_context(obj: object) -> bool:
    """Return True if obj is a SparkJobContext with GlueContext."""
    return isinstance(obj, SparkJobContext) and isinstance(
        obj.glue,
        GlueContext,
    )


# --- Gherkin Cell Parsing ---

_EMPTY_COLLECTION_FACTORIES: dict[str, Callable[[], object]] = {
    "set()": set,
    "frozenset()": frozenset,
}
_SPECIAL_SCALARS: tuple[type, ...] = (UUID, datetime, date, time)


def _convert_item(
    value: str,
    target_type: type,
) -> UUID | datetime | date | time:
    """Convert raw string to the target type."""
    if target_type is UUID:
        return UUID(value)
    if target_type is datetime:
        return datetime.fromisoformat(value)
    if target_type is date:
        return date.fromisoformat(value)
    return time.fromisoformat(value)


def _parse_collection(actual: object, parsed: object) -> object:
    """Convert parsed collection items to typed objects if needed."""
    if isinstance(actual, (list, tuple, set, frozenset)) and actual:
        first = next(iter(actual))
        if isinstance(first, _SPECIAL_SCALARS):
            origin = type(actual)
            elem_type = type(first)
            return origin(
                _convert_item(x, elem_type)
                for x in cast("Iterable[str]", parsed)
            )
    return parsed


def parse_expected(raw: str, actual: object) -> object:
    """Parse a Gherkin expectation cell into a typed Python value."""
    if isinstance(actual, str):
        return raw
    if raw in _EMPTY_COLLECTION_FACTORIES:
        return _EMPTY_COLLECTION_FACTORIES[raw]()
    if isinstance(actual, _SPECIAL_SCALARS):
        return _convert_item(raw, type(actual))
    if raw.startswith("frozenset(") and raw.endswith(")"):
        inner: object = ast.literal_eval(raw[10:-1])
        assert isinstance(inner, set)
        parsed: object = frozenset(inner)
    else:
        parsed = ast.literal_eval(raw)
    return _parse_collection(actual, parsed)


def _assert_field_types(field_types: dict[str, str], table: Table) -> None:
    """Assert declared dataclass field types match the Gherkin type column."""
    for row in table:
        name = row["field"]
        assert field_types[name] == row["type"], (
            f"field {name!r}: expected type {row['type']!r}, "
            f"got {field_types[name]!r}"
        )


def verify_dataclass_table(
    received: object,
    table: Table,
) -> None:
    """Assert dataclass fields, optional declared types, and values match."""
    fields = dataclasses.fields(cast("DataclassInstance", received))
    expected = {row["field"]: row["value"] for row in table}
    assert set(expected).issubset({f.name for f in fields})
    if "type" in table.headings:
        field_types = {
            f.name: str(f.type) if f.init else f"{f.type} (init=False)"
            for f in fields
        }
        _assert_field_types(field_types, table)
    for field_name, raw_expected in expected.items():
        actual = getattr(received, field_name)
        assert actual == parse_expected(raw_expected, actual)
