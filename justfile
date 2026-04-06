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
    #!/bin/sh
    set -eu
    IMAGE="${GLUE_DOCKER_IMAGE:-public.ecr.aws/glue/aws-glue-libs:5}"
    WORKSPACE="$(pwd)"
    CONTAINER_WORKSPACE="/workspace"
    docker run --rm -i \
        -v "${WORKSPACE}:${CONTAINER_WORKSPACE}" \
        --workdir "${CONTAINER_WORKSPACE}" \
        --entrypoint /bin/bash \
        "${IMAGE}" \
        -l <<'SCRIPT'
    if ! python3 -m pip install --disable-pip-version-check --quiet --user \
            -e . behave coverage[toml] >/tmp/pip-install.log 2>&1; then
        cat /tmp/pip-install.log
        exit 1
    fi

    export COVERAGE_FILE=/tmp/.coverage
    python3 -m coverage run -m behave --format null 2>/tmp/test-stderr.log || {
        cat /tmp/test-stderr.log >&2
        exit 1
    }
    python3 -m coverage report
    SCRIPT
