#!/bin/sh

set -ex

export UV_PYTHON=3.11

if [ "$1" = "setup" ]
then
  uv sync --frozen --all-extras
else
  uv run --frozen --all-extras -- pre-commit run --show-diff-on-failure --color=always --all-files
fi
