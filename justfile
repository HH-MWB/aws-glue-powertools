# Default: show recipe list
[private]
default:
    @just --list

# Initialize local dev environment.
init:
    uv python install
    uv sync --group dev
    uv run pre-commit install

# Run pre-commit on staged files.
lint:
    uv run pre-commit run

# Run tests and show coverage report.
test:
    uv run coverage run -m behave --format null
    uv run coverage report
