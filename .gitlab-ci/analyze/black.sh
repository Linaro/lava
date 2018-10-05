#!/bin/sh

set -e

if [ "$1" = "setup" ]
then
  set -x
  apt-get update -qq
  # Manually install python3-pkg-resources until black package is fixed
  apt-get install -qq --no-install-recommends -y black python3-pkg-resources
else
  set -x
  LC_ALL=C.UTF-8 LANG=C.UTF-8 black --check $(cat share/black.list)
fi
