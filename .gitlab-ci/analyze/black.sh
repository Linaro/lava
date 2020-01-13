#!/bin/sh

set -e

if [ "$1" = "setup" ]
then
  apt-get -q update
  apt-get install --no-install-recommends --yes black
else
  set -x
  LC_ALL=C.UTF-8 LANG=C.UTF-8 black  --exclude "dashboard_app" --check . lava/coordinator/lava-coordinator lava/dispatcher/lava-slave lava/dispatcher/lava-run lava_dispatcher_host/lava-dispatcher-host
fi
