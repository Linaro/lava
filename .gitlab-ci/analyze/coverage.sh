#!/bin/sh

COVERAGE_MIN_PERCENTAGE=56

set -e

if [ "$1" = "setup" ]
then
  set -x
  apt-get -q update
  DEPS=$(./share/requires.py -p lava-dispatcher -d debian -s stretch -n)
  apt-get install --no-install-recommends --yes $DEPS
  DEPS=$(./share/requires.py -p lava-dispatcher -d debian -s stretch-backports -n)
  apt-get install --no-install-recommends --yes $DEPS
  DEPS=$(./share/requires.py -p lava-server -d debian -s stretch -n)
  apt-get install --no-install-recommends --yes $DEPS
  DEPS=$(./share/requires.py -p lava-server -d debian -s stretch-backports -n)
  apt-get install --no-install-recommends --yes $DEPS
else
  set -x
  PYTHONPATH=. pytest-3 --cache-clear -v --cov --cov-report=term --cov-report=html --cov-fail-under=$COVERAGE_MIN_PERCENTAGE
fi
