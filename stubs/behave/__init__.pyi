from collections.abc import Callable
from typing import ParamSpec, TypeVar

_P = ParamSpec("_P")
_R = TypeVar("_R")

def given(
    step_text: str,
    **kwargs: object,
) -> Callable[[Callable[_P, _R]], Callable[_P, _R]]: ...
def when(
    step_text: str,
    **kwargs: object,
) -> Callable[[Callable[_P, _R]], Callable[_P, _R]]: ...
def then(
    step_text: str,
    **kwargs: object,
) -> Callable[[Callable[_P, _R]], Callable[_P, _R]]: ...
