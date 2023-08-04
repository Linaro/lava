#!/bin/sh

set -e

if [ "$1" = "setup" ]
then
  set -x
  apt-get -q update
  DEPS=$(./share/requires.py -p lava-server -d debian -s bookworm -n)
  apt-get install --no-install-recommends --yes $DEPS
  DEPS=$(./share/requires.py -p lava-server -d debian -s bookworm -n -u)
  apt-get install --no-install-recommends --yes $DEPS
else
  set -x
  python3 -m pytest \
      --numprocesses=auto \
      --color=yes \
      --pythonwarnings=default \
      -r a \
      --cache-clear --verbose \
      --junitxml=server.xml \
      --random-order --random-order-bucket=global \
    tests/lava_common \
    tests/lava_scheduler_app \
    tests/lava_results_app \
    tests/linaro_django_xmlrpc \
    tests/lava_rest_app \
    tests/lava_server "$@"
fi
