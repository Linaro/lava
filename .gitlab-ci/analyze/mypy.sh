#!/bin/bash

set -e

if [ "$1" = "setup" ]
then
  apt-get -q update
  apt-get install --no-install-recommends --yes mypy python3-typeshed
else
  set -x
  FILES=(
    # lava_common
    'lava_common/timeout.py'
    # lava_dispatcher
    'lava_dispatcher/utils/shell.py'
  )
  mypy --python-version 3.11 --pretty --strict --follow-imports=silent "${FILES[@]}"
fi
