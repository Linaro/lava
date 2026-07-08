#!/bin/sh

set -ex

if [ "$1" = "setup" ]
then
  uv sync --frozen --all-extras
else
  uv run --frozen --all-extras -- pre-commit run pylint --show-diff-on-failure --color=always --all-files
fi
