#!/bin/sh

set -e

if [ "$1" = "setup" ]
then
  set -x
  apt-get -q update
  DEPS=$(./share/requires.py -p lava-server -d debian -s bullseye -n)
  apt-get install --no-install-recommends --yes $DEPS
  DEPS=$(./share/requires.py -p lava-server -d debian -s bullseye -n -u)
  apt-get install --no-install-recommends --yes $DEPS
else
  set -x
  python3 -m pytest \
      --color=yes \
      --pythonwarnings=default \
      --cache-clear --verbose \
      --junitxml=server.xml \
    tests/lava_common \
    tests/lava_scheduler_app \
    tests/lava_results_app \
    tests/linaro_django_xmlrpc \
    tests/lava_rest_app \
    tests/lava_server "$@"
fi
