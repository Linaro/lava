#!/bin/sh

set -e

if [ "$1" = "setup" ]
then
  set -x
  apt-get -q update
  DEPS=$(./share/requires.py -p lava-server -d debian -s stretch -n)
  apt-get install --no-install-recommends --yes $DEPS
  DEPS=$(./share/requires.py -p lava-server -d debian -s stretch-backports -n)
  apt-get install --no-install-recommends --yes -t stretch-backports $DEPS
  DEPS=$(./share/requires.py -p lava-server -d debian -s stretch -n -u)
  apt-get install --no-install-recommends --yes $DEPS
  DEPS=$(./share/requires.py -p lava-server -d debian -s stretch-backports -n -u)
  apt-get install --no-install-recommends --yes -t stretch-backports $DEPS
else
  set -x
  PYTHONPATH=. pytest-3 --cache-clear -v --junitxml=common.xml lava_common/test
  PYTHONPATH=. pytest-3 --cache-clear --ds lava_server.settings.development -v --junitxml=server.xml lava_scheduler_app/tests lava_results_app/tests linaro_django_xmlrpc/tests.py lava_rest_app/tests.py
fi
