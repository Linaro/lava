#!/bin/sh

set -e

if [ "$1" = "setup" ]
then
  echo "nothing to do"
else
  set -x
  export LC_ALL=C.UTF-8
  export LANG=C.UTF-8
  apt -y -q install python3 radon
  python3 .gitlab-ci/analyze/parse.py
fi
