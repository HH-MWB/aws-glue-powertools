"""Step definitions for typed business argument parsing and validation."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

from behave import given, then

from aws_glue_powertools.exceptions import (
    JobArgumentValidationError,
    UnsupportedArgumentTypeError,
)
from features.helpers import (
    UNSUPPORTED_TYPE_MAP,
    CollectionDataclass,
    LifecycleDataclass,
    SampleModel,
    make_batch_entrypoint,
    make_scalar_dataclass,
    parse_expected,
    verify_dataclass_table,
)

if TYPE_CHECKING:
    from features.steps.context_types import BatchJobBehaveContext


# =============================================================================
# Given Steps (Arrange)
# =============================================================================

# --- Entrypoint Schemas ---


@given(
    "an entrypoint decorated with BatchJob expecting a dataclass "
    'with scalar field "{field_name}" of type "{type_name}"',
)
def step_entrypoint_with_scalar_field(
    context: BatchJobBehaveContext,
    field_name: str,
    type_name: str,
) -> None:
    """Prepare dynamic single-field scalar dataclass entrypoint."""
    cls = make_scalar_dataclass(field_name, type_name)
    context.entrypoint = make_batch_entrypoint(context, cls)


@given(
    "an entrypoint decorated with BatchJob expecting a collection dataclass",
)
def step_entrypoint_with_collection_dataclass(
    context: BatchJobBehaveContext,
) -> None:
    """Prepare an entrypoint expecting CollectionDataclass."""
    context.entrypoint = make_batch_entrypoint(context, CollectionDataclass)


@given(
    "an entrypoint decorated with BatchJob expecting a lifecycle dataclass",
)
def step_entrypoint_with_lifecycle_dataclass(
    context: BatchJobBehaveContext,
) -> None:
    """Prepare an entrypoint expecting LifecycleDataclass."""
    context.entrypoint = make_batch_entrypoint(context, LifecycleDataclass)


@given("an entrypoint decorated with BatchJob expecting a Pydantic model")
def step_entrypoint_with_pydantic_model(
    context: BatchJobBehaveContext,
) -> None:
    """Prepare an entrypoint expecting SampleModel."""
    context.entrypoint = make_batch_entrypoint(context, SampleModel)


@given(
    'an entrypoint decorated with BatchJob expecting argument type "{spec}"',
)
def step_entrypoint_with_unsupported_type(
    context: BatchJobBehaveContext,
    spec: str,
) -> None:
    """Prepare an entrypoint expecting the named unsupported type."""
    target_type = UNSUPPORTED_TYPE_MAP[spec]
    context.entrypoint = make_batch_entrypoint(context, target_type)


# --- Optional Dependencies ---


@given("the optional Pydantic package is not installed")
def step_pydantic_not_installed(context: BatchJobBehaveContext) -> None:
    """Simulate an environment without optional pydantic installed."""
    patcher = patch.dict("sys.modules", {"pydantic": None})
    patcher.start()
    context.pydantic_patcher = patcher


# =============================================================================
# Then Steps (Assert)
# =============================================================================

# --- Parsed Model Assertions ---


@then(
    'the entrypoint receives a dataclass with "{field_name}" '
    'equal to "{expected_str}"',
)
def step_receives_dataclass_scalar_field(
    context: BatchJobBehaveContext,
    field_name: str,
    expected_str: str,
) -> None:
    """Assert received dataclass field matches parsed expected value."""
    assert context.received_args is not None
    actual = getattr(context.received_args, field_name)
    expected = parse_expected(expected_str, actual)
    assert actual == expected
    assert type(actual) is type(expected)


@then("the entrypoint receives a dataclass matching:")
def step_receives_validated_dataclass(
    context: BatchJobBehaveContext,
) -> None:
    """Assert received dataclass fields, types, and values match the table."""
    assert context.received_args is not None
    assert context.table is not None
    verify_dataclass_table(context.received_args, context.table)


@then('the received dataclass has no "{attr}" attribute')
def step_received_dataclass_missing_attr(
    context: BatchJobBehaveContext,
    attr: str,
) -> None:
    """Assert unknown CLI parameter was not attached to the dataclass."""
    assert context.received_args is not None
    assert not hasattr(context.received_args, attr)


@then(
    "the entrypoint receives a Pydantic model "
    "with batch_id {batch_id:d} and dry_run {dry_run}",
)
def step_receives_validated_pydantic_model(
    context: BatchJobBehaveContext,
    batch_id: int,
    dry_run: str,
) -> None:
    """Assert entrypoint received validated Pydantic model."""
    assert isinstance(context.received_args, SampleModel)
    assert context.received_args.batch_id == batch_id
    expected_dry_run = dry_run.lower() == "true"
    assert context.received_args.dry_run is expected_dry_run


# --- Validation & Type Error Assertions ---


@then("the caller receives JobArgumentValidationError")
def step_arg_validation_error_propagated(
    context: BatchJobBehaveContext,
) -> None:
    """Assert JobArgumentValidationError reached caller."""
    assert isinstance(context.execution_error, JobArgumentValidationError)


@then("the caller receives UnsupportedArgumentTypeError")
def step_unsupported_type_error_propagated(
    context: BatchJobBehaveContext,
) -> None:
    """Assert UnsupportedArgumentTypeError reached caller."""
    assert isinstance(context.execution_error, UnsupportedArgumentTypeError)
