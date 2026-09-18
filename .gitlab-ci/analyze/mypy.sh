#!/bin/bash

set -e

if [ "$1" = "setup" ]
then
  apt-get -q update
  apt-get install --no-install-recommends --yes mypy python3-typeshed python3-sentry-sdk python3-magic python3-setproctitle
else
  set -x
  # Single source of truth: [tool.pyrefly] project-includes in pyproject.toml
  mapfile -t FILES < <(python3 -c 'import tomllib; print("\n".join(tomllib.load(open("pyproject.toml", "rb"))["tool"]["pyrefly"]["project-includes"]))')
  mypy --python-version 3.11 --pretty --strict --follow-imports=silent "${FILES[@]}"
fi
