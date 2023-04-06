#!/bin/sh

COVERAGE_MIN_PERCENTAGE=60

set -e

if [ "$1" = "setup" ]
then
  set -x
  apt-get -q update
  DEPS=$(./share/requires.py -p lava-dispatcher -d debian -s bullseye -n)
  apt-get install --no-install-recommends --yes $DEPS
  DEPS=$(./share/requires.py -p lava-dispatcher -d debian -s bullseye -n -u)
  apt-get install --no-install-recommends --yes $DEPS
  DEPS=$(./share/requires.py -p lava-common -d debian -s bullseye -n)
  apt-get install --no-install-recommends --yes $DEPS
  DEPS=$(./share/requires.py -p lava-server -d debian -s bullseye -n)
  apt-get install --no-install-recommends --yes $DEPS
  DEPS=$(./share/requires.py -p lava-server -d debian -s bullseye -n -u)
  apt-get install --no-install-recommends --yes $DEPS
else
  set -x
  # Due to a but somewhere in pytest or coverage, the htmlcov is not generated
  # by pytest but can be generated in a second step.
  python3 -m pytest --cache-clear -v --cov --cov-report=term --cov-fail-under=$COVERAGE_MIN_PERCENTAGE tests/
  python3 -m coverage html
fi
