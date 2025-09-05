#!/bin/sh

COVERAGE_MIN_PERCENTAGE=60

set -e

if [ "$1" = "setup" ]
then
  set -x
  apt-get -q update
  DEPS=$(./share/requires.py -p lava-dispatcher -d debian -s bookworm -n)
  apt-get install --no-install-recommends --yes $DEPS
  DEPS=$(./share/requires.py -p lava-dispatcher -d debian -s bookworm -n -u)
  apt-get install --no-install-recommends --yes $DEPS
  DEPS=$(./share/requires.py -p lava-common -d debian -s bookworm -n)
  apt-get install --no-install-recommends --yes $DEPS
  DEPS=$(./share/requires.py -p lava-server -d debian -s bookworm -n)
  apt-get install --no-install-recommends --yes $DEPS
  DEPS=$(./share/requires.py -p lava-server -d debian -s bookworm -n -u)
  apt-get install --no-install-recommends --yes $DEPS
else
  set -x
  python3 -m pytest --cache-clear -v \
    --numprocesses=auto \
    --cov --cov-report=term \
    --cov-report xml:coverage.xml \
    --cov-report html:htmlcov \
    --cov-fail-under="$COVERAGE_MIN_PERCENTAGE" \
    tests/ "$@"
fi
