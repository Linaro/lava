#!/bin/sh

set -e

if [ "$1" = "setup" ]
then
  apt-get -q update
  apt-get install --no-install-recommends --yes python3 radon
else
  set -x
  export LC_ALL=C.UTF-8
  export LANG=C.UTF-8
  python3 .gitlab-ci/analyze/parse.py
fi
