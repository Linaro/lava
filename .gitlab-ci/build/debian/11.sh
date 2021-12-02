#!/bin/sh

set -e

if [ "$1" = "setup" ]
then
  true
else
  set -x
  # build the full package, including original source for bullseye.
  ./share/debian-dev-build.sh -o _build -s bullseye
  debc $(find _build -name 'lava_*_amd64.changes' 2>/dev/null|head -n1)

  # Check dependencies
  .gitlab-ci/build/debian/check-debian-deps.py --suite bullseye --package lava-common _build/lava-common_*bullseye*
  .gitlab-ci/build/debian/check-debian-deps.py --suite bullseye --package lava-dispatcher _build/lava-dispatcher_*bullseye*
  .gitlab-ci/build/debian/check-debian-deps.py --suite bullseye --package lava-dispatcher-host _build/lava-dispatcher-host_*bullseye*
  .gitlab-ci/build/debian/check-debian-deps.py --suite bullseye --package lava-server _build/lava-server_*bullseye*
fi
