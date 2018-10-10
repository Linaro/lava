#!/bin/sh

set -e

if [ "$1" = "setup" ]
then
  echo "nothing to do"
else
  set -x
  LC_ALL=C.UTF-8 LANG=C.UTF-8 black --check $(cat share/black.list)
fi
