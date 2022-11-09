#!/bin/sh

set -e

if [ "$1" = "setup" ]
then
  apt-get -q update
  apt-get install --no-install-recommends --yes black isort
else
  set -x
  PYTHON_MODULES=". lava/coordinator/lava-coordinator lava/dispatcher/lava-run lava/dispatcher/lava-worker lava_dispatcher_host/lava-docker-worker lava_dispatcher_host/lava-dispatcher-host"
  LC_ALL=C.UTF-8 LANG=C.UTF-8 isort --check --diff --profile black ${PYTHON_MODULES}
  LC_ALL=C.UTF-8 LANG=C.UTF-8 black  --check --diff ${PYTHON_MODULES}
fi
