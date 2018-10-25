#!/bin/sh

set -e

if [ "$1" = "setup" ]
then
  set -x
  DEPS=$(./share/requires.py -p lava-dispatcher -d debian -s buster -n)
  apt-get install --no-install-recommends --yes $DEPS
  DEPS=$(./share/requires.py -p lava-dispatcher -d debian -s buster -n -u)
  apt-get install --no-install-recommends --yes $DEPS
else
  set -x
  PYTHONPATH=. py.test-3 --cache-clear -v --junitxml=dispatcher.xml lava_dispatcher/test
fi
