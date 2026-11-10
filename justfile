# Default recipe: display list of available recipes in logical order.
[private]
default:
    @just --list --unsorted

# =============================================================================
# Development & Quality
# =============================================================================

# Initialize local development environment (Python, dependencies, git hooks).
init:
    uv python install
    uv sync --group dev
    uv run pre-commit install

# Run pre-commit hooks on all or specified files (e.g. `just lint` or `just lint ruff-check`).
lint *ARGS="--all-files":
    uv run pre-commit run {{ARGS}}

# =============================================================================
# Testing & Coverage
# =============================================================================

# Run Behave tests inside the AWS Glue Docker container.
test *ARGS:
    @just _run-in-glue test {{ARGS}}

# Run tests with coverage report and generate coverage.xml.
coverage *ARGS:
    @just _run-in-glue coverage {{ARGS}}

# =============================================================================
# Private Helpers
# =============================================================================

# Execute test/coverage workloads inside the official AWS Glue Docker container.
[private]
_run-in-glue MODE *ARGS:
    #!/bin/sh
    set -eu

    # Resolve and validate Glue Docker image (defaults to 6.0; supports 5.0, 5.1, 6.0).
    if [ -z "${GLUE_DOCKER_IMAGE:-}" ]; then
        case "${GLUE_VERSION:-6.0}" in
            5.0) GLUE_TAG="5" ;;
            5.1) GLUE_TAG="5.1" ;;
            6.0) GLUE_TAG="6.0" ;;
            *)
                echo "Error: GLUE_VERSION must be 5.0, 5.1, or 6.0 (got '${GLUE_VERSION}')" >&2
                exit 1
                ;;
        esac
        GLUE_DOCKER_IMAGE="public.ecr.aws/glue/aws-glue-libs:${GLUE_TAG}"
    fi

    WORKSPACE="$(pwd)"
    CONTAINER_WORKSPACE="/workspace"

    docker run --rm -i \
        -v "${WORKSPACE}:${CONTAINER_WORKSPACE}" \
        --workdir "${CONTAINER_WORKSPACE}" \
        --entrypoint /bin/bash \
        "${GLUE_DOCKER_IMAGE}" \
        -l -s -- "{{MODE}}" {{ARGS}} <<'SCRIPT'
    set -eu

    MODE="$1"; shift

    # Install the package in editable mode alongside test dependencies.
    if ! python3 -m pip install --disable-pip-version-check --quiet --user \
            -e ".[parser]" behave coverage >/tmp/pip-install.log 2>&1; then
        cat /tmp/pip-install.log
        exit 1
    fi

    # Run either with coverage reporting or standard test execution.
    if [ "$MODE" = "coverage" ]; then
        export COVERAGE_FILE=/tmp/.coverage
        python3 -m coverage run -m behave "$@"
        python3 -m coverage report
        python3 -m coverage xml -o coverage.xml
    else
        python3 -m behave "$@"
    fi
    SCRIPT
