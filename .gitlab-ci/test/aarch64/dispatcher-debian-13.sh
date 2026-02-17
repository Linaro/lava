#!/bin/sh

set -e

if [ "$1" = "setup" ]
then
  set -x
  apt-get -q update
  DEPS=$(./share/requires.py -p lava-dispatcher -d debian -s trixie -n)
  apt-get install --no-install-recommends --yes $DEPS
  DEPS=$(./share/requires.py -p lava-dispatcher -d debian -s trixie -n -u)
  apt-get install --no-install-recommends --yes $DEPS
else
  set -x
  python3 -m pytest \
      --color=yes \
      --pythonwarnings=default \
      -r a \
      --cache-clear --verbose \
      --junitxml=dispatcher.xml \
      --random-order --random-order-bucket=global \
    tests/lava_dispatcher \
    tests/lava_dispatcher_host \
    tests/lava_coordinator "$@"
fi
