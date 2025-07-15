#!/bin/sh

set -e

if [ "$1" = "setup" ]
then
  apt-get -q update
  apt-get install --no-install-recommends --yes mypy python3-typeshed
else
  set -x
  FILES="lava_dispatcher/utils/shell.py lava_common/timeout.py"
  mypy --python-version 3.11 --pretty --strict --follow-imports=silent $FILES
fi
