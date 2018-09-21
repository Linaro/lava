#!/bin/sh

set -e

if [ "$1" = "setup" ]
then
  set -x
  apt-get install --no-install-recommends --yes $(./share/requires.py -p lava-dispatcher -d debian -s buster -n)
else
  set -x
  PYTHONPATH=. py.test-3 --cache-clear -v --junitxml=dispatcher.xml lava_dispatcher/test
fi
