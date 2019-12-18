#!/bin/sh

set -e

if [ "$1" = "setup" ]
then
  set -x
  apt-get -q update
  DEPS=$(./share/requires.py -p lava-server -d debian -s buster -n)
  apt-get install --no-install-recommends --yes $DEPS
  DEPS=$(./share/requires.py -p lava-server -d debian -s buster -n -u)
  apt-get install --no-install-recommends --yes $DEPS
else
  set -x
  PYTHONPATH=. pytest-3 --cache-clear -W ignore::DeprecationWarning -v --junitxml=common.xml tests/lava_common
  PYTHONPATH=. pytest-3 --cache-clear -W ignore::DeprecationWarning \
  --ds lava_server.settings.development -v --junitxml=server.xml \
  tests/lava_scheduler_app tests/lava_results_app tests/linaro_django_xmlrpc tests/lava_rest_app tests/lava_server
fi
