"""Step definitions for example feature."""

from behave import given

import aws_glue_powertools


@given("the powertools package is importable")
def step_powertools_importable(_context: object) -> None:
    """Fail if the installed package has no module docstring."""
    if not aws_glue_powertools.__doc__:
        msg = "aws_glue_powertools must have a module docstring"
        raise AssertionError(msg)
