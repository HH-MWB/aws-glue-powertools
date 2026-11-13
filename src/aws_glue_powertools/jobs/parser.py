"""Argument parsing and type validation for Glue jobs."""

from __future__ import annotations

import dataclasses
import inspect
import types
import typing
from collections.abc import Mapping
from datetime import date, datetime, time
from typing import TYPE_CHECKING, TypeGuard, cast
from uuid import UUID

from aws_glue_powertools.exceptions import (
    JobArgumentValidationError,
    UnsupportedArgumentTypeError,
)

if TYPE_CHECKING:
    from collections.abc import Callable
    from typing import TypeVar

    from _typeshed import DataclassInstance
    from pydantic import BaseModel

    _ArgsT = TypeVar("_ArgsT")
    _ContextT = TypeVar("_ContextT")

__all__ = ["parse_arguments"]

# =============================================================================
# Constants & Lookup Tables
# =============================================================================

_BOOL_MAP: dict[str, bool] = {
    "True": True,
    "true": True,
    "False": False,
    "false": False,
}
_SCALAR_PARSERS: dict[object, Callable[[str], object]] = {
    str: str,
    int: int,
    float: float,
    bool: _BOOL_MAP.__getitem__,
    UUID: UUID,
    datetime: datetime.fromisoformat,
    date: date.fromisoformat,
    time: time.fromisoformat,
}
_SUPPORTED_COLLECTIONS: frozenset[type] = frozenset(
    {list, tuple, set, frozenset},
)
_UNION_ORIGINS: tuple[object, ...] = (
    typing.Union,  # pyright: ignore[reportDeprecated]
    types.UnionType,
)


# =============================================================================
# Target Type Resolution
# =============================================================================


def _get_target_type(
    entrypoint: Callable[[_ArgsT, _ContextT], None],
) -> object:
    """Extract type annotation of the entrypoint's first parameter."""
    param = next(iter(inspect.signature(entrypoint).parameters), None)
    return typing.get_type_hints(entrypoint).get(param) if param else None


def _is_valid_mapping(target: object) -> bool:
    """Return True if target is dict, Mapping, or [str, str] mapping."""
    return (typing.get_origin(target) or target) in (
        dict,
        Mapping,
    ) and typing.get_args(target) in ((), (str, str))


# =============================================================================
# Dataclass Parser (Standard Library)
# =============================================================================


def _is_dataclass(target: object) -> TypeGuard[type[DataclassInstance]]:
    """Return True if target is a dataclass type."""
    return isinstance(target, type) and dataclasses.is_dataclass(target)


def _unwrap_optional(hint: object) -> object:
    """Unwrap Optional[T] / T | None to its inner type."""
    if typing.get_origin(hint) not in _UNION_ORIGINS:
        return hint

    # Filter out None to extract the wrapped inner type
    non_none = [a for a in typing.get_args(hint) if a is not types.NoneType]
    if len(non_none) == 1:
        return non_none[0]

    # Reject multi-variant unions (e.g. int | str)
    raise UnsupportedArgumentTypeError(hint)


def _collection_parser(
    origin: type,
    hint: object,
) -> Callable[[str], object]:
    """Return string parser for collection or raise if unsupported."""
    type_args = [a for a in typing.get_args(hint) if a is not Ellipsis]

    # Bare collections (e.g. list, set) default element type to str
    if not type_args:
        return lambda raw: origin() if not raw else origin(raw.split(","))

    # Parameterized collections (e.g. list[int], tuple[str, ...])
    if (
        len(type_args) == 1
        and type_args[0] in _SCALAR_PARSERS
        and type_args[0] is not bool
    ):
        parse_item = _SCALAR_PARSERS[type_args[0]]
        return lambda raw: (
            origin()
            if not raw
            else origin(parse_item(x) for x in raw.split(","))
        )

    # Reject unsupported item types or heterogeneous collections
    raise UnsupportedArgumentTypeError(hint)


def _get_parser(hint: object) -> Callable[[str], object]:
    """Return a string parser for the type hint or raise if unsupported."""
    base = _unwrap_optional(hint)

    # Fast table lookup for scalars (e.g. int, bool, UUID, datetime)
    if base in _SCALAR_PARSERS:
        return _SCALAR_PARSERS[base]

    # Check for supported collection types (e.g. list, tuple, set)
    origin = typing.get_origin(base) or base
    if origin in _SUPPORTED_COLLECTIONS:
        return _collection_parser(cast("type", origin), base)

    # Reject any other unsupported type (e.g. complex, custom class)
    raise UnsupportedArgumentTypeError(base)


def _parse_dataclass(
    target: type[DataclassInstance],
    args: dict[str, str],
) -> object:
    """Parse and validate a dataclass from business arguments."""
    hints = typing.get_type_hints(target)

    # Schema validation: resolve field parsers (fails fast if unsupported)
    parsers = {
        field.name: _get_parser(hints.get(field.name, field.type))
        for field in dataclasses.fields(target)
        if field.init
    }

    # Argument parsing & instantiation: convert CLI values and construct model
    try:
        kwargs = {
            name: parsers[name](args[name]) for name in parsers if name in args
        }
        return target(**kwargs)
    except (ValueError, KeyError, TypeError) as exc:
        raise JobArgumentValidationError(target, exc) from exc


# =============================================================================
# Pydantic Model Parser (Optional Dependency)
# =============================================================================


def _is_pydantic_model(target: object) -> TypeGuard[type[BaseModel]]:
    """Return True if target is a subclass of Pydantic BaseModel."""
    try:
        from pydantic import BaseModel  # noqa: PLC0415
    except ImportError:
        return False
    return isinstance(target, type) and issubclass(target, BaseModel)


def _parse_pydantic(
    target: type[BaseModel],
    args: dict[str, str],
) -> object:
    """Parse and validate arguments using model's model_validate method."""
    from pydantic import ValidationError  # noqa: PLC0415

    try:
        return target.model_validate(args)
    except ValidationError as exc:
        raise JobArgumentValidationError(target, exc) from exc


# =============================================================================
# Public Entrypoint
# =============================================================================


def parse_arguments(
    entrypoint: Callable[[_ArgsT, _ContextT], None],
    args: dict[str, str],
) -> _ArgsT:
    """Parse business arguments into the type expected by the entrypoint.

    Args:
        entrypoint: Decorated job entrypoint function.
        args: Raw business argument key-value pairs.

    Returns:
        Validated model instance or raw dictionary matching entrypoint type.

    Raises:
        JobArgumentValidationError: If arguments fail model validation.
        UnsupportedArgumentTypeError: If argument type hint is unsupported.
    """
    target = _get_target_type(entrypoint)

    if target is None or _is_valid_mapping(target):
        return cast("_ArgsT", args)

    if _is_dataclass(target):
        return cast("_ArgsT", _parse_dataclass(target, args))

    if _is_pydantic_model(target):
        return cast("_ArgsT", _parse_pydantic(target, args))

    raise UnsupportedArgumentTypeError(target)
