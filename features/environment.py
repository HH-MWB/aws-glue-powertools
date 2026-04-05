"""Behave test environment hooks (fixtures, setup/teardown)."""


def after_scenario(context: object, _scenario: object) -> None:
    """Clean up any temporary workspace created for a scenario."""
    temporary_directory = getattr(context, "temporary_directory", None)
    if temporary_directory is not None:
        temporary_directory.cleanup()
