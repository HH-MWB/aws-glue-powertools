#!/bin/sh

set -eu

IMAGE="${GLUE_DOCKER_IMAGE:-public.ecr.aws/glue/aws-glue-libs:5}"
WORKSPACE="$(pwd)"
CONTAINER_WORKSPACE="/workspace"

docker run --rm \
    -v "${WORKSPACE}:${CONTAINER_WORKSPACE}" \
    --workdir "${CONTAINER_WORKSPACE}" \
    --entrypoint /bin/bash \
    "${IMAGE}" \
    -lc "\
if ! python3 -m pip install --disable-pip-version-check --quiet --user -e . behave coverage[toml] >/tmp/pip-install.log 2>&1; then \
    cat /tmp/pip-install.log; \
    exit 1; \
fi && \
python3 -m coverage run -m behave --format null && \
python3 -m coverage report"
