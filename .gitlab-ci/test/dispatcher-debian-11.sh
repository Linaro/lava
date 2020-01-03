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
  PYTHONPATH=. pytest-3 --cache-clear -v --junitxml=dispatcher.xml tests/lava_dispatcher
  PYTHONPATH=. pytest-3 --cache-clear -v --junitxml=dispatcher-host.xml tests/lava_dispatcher_host
  PYTHONPATH=. pytest-3 --cache-clear -v --junitxml=coordinator.xml tests/lava_coordinator
fi
