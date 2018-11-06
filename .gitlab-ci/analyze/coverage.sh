#!/bin/sh

set -e

if [ "$1" = "setup" ]
then
  set -x
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
  PYTHONPATH=. pytest-3 --cache-clear -v --cov --cov-report= lava_dispatcher/test
  PYTHONPATH=. pytest-3 --cache-clear -v --ds lava_server.settings.development --cov --cov-append --cov-report= lava_scheduler_app/tests lava_results_app/tests linaro_django_xmlrpc/tests.py
  PYTHONPATH=. pytest-3 --cache-clear -v --cov --cov-append --cov-report=term --cov-report=html lava_common/test
fi
