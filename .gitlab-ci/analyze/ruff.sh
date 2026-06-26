#!/bin/sh

set -ex

if [ "$1" = "setup" ]
then
  uv sync --frozen --all-extras
else
  PYTHON_MODULES=". lava/coordinator/lava-coordinator lava/dispatcher/lava-run lava/dispatcher/lava-worker lava_dispatcher_host/lava-docker-worker lava_dispatcher_host/lava-dispatcher-host"
  uv run --frozen --all-extras -- pre-commit run ruff-check --show-diff-on-failure --color=always --all-files
  uv run --frozen --all-extras -- pre-commit run ruff-format --show-diff-on-failure --color=always --all-files
fi
