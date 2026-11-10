"""Argument parsing and type validation for Glue batch jobs."""

from __future__ import annotations

import inspect
import typing
from collections.abc import Mapping
from typing import TYPE_CHECKING, TypeGuard, cast

from aws_glue_powertools.exceptions import (
    JobArgumentValidationError,
    UnsupportedArgumentTypeError,
)

if TYPE_CHECKING:
    from collections.abc import Callable
    from typing import TypeVar

    from pydantic import BaseModel

    _ArgsT = TypeVar("_ArgsT")
    _ContextT = TypeVar("_ContextT")

__all__ = ["parse_arguments"]


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


def _is_pydantic_model(target: object) -> TypeGuard[type[BaseModel]]:
    """Return True if target is a subclass of Pydantic BaseModel."""
    try:
        from pydantic import BaseModel  # noqa: PLC0415
    except ImportError:
        return False
    return isinstance(target, type) and issubclass(target, BaseModel)


def _validate_pydantic(
    target: type[BaseModel],
    args: dict[str, str],
) -> object:
    """Validate raw arguments using model's model_validate method."""
    from pydantic import ValidationError  # noqa: PLC0415

    try:
        return target.model_validate(args)
    except ValidationError as exc:
        raise JobArgumentValidationError(target, exc) from exc


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

    if _is_pydantic_model(target):
        return cast("_ArgsT", _validate_pydantic(target, args))

    raise UnsupportedArgumentTypeError(target)
