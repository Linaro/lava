#!/bin/sh

set -e

export UV_PYTHON=3.11

if [ "$1" = "setup" ]
then
  set -x
  uv sync --frozen --all-extras
else
  set -x
  uv run --frozen --all-extras -- pre-commit run --show-diff-on-failure --color=always --all-files
fi
