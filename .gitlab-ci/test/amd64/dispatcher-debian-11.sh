#!/bin/sh

set -e

if [ "$1" = "setup" ]
then
  set -x
  apt-get -q update
  DEPS=$(./share/requires.py -p lava-dispatcher -d debian -s bullseye -n)
  apt-get install --no-install-recommends --yes $DEPS
  DEPS=$(./share/requires.py -p lava-dispatcher -d debian -s bullseye -n -u)
  apt-get install --no-install-recommends --yes $DEPS
else
  set -x
  python3 -m pytest \
      --color=yes \
      --pythonwarnings=default \
      --cache-clear --verbose \
      --junitxml=dispatcher.xml \
    tests/lava_dispatcher \
    tests/lava_dispatcher_host \
    tests/lava_coordinator "$@"
fi
