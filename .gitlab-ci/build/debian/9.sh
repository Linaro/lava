#!/bin/sh

set -e

if [ "$1" = "setup" ]
then
  true
else
  set -x
  # build the full package, including original source, for stretch.
  ./share/debian-dev-build.sh -o _build -s stretch
  debc $(find _build -name 'lava_*_amd64.changes' 2>/dev/null|head -n1)

  # Check dependencies
  .gitlab-ci/build/debian/check-debian-deps.py --suite stretch-backports --package lava-common _build/lava-common_*stretch*
  .gitlab-ci/build/debian/check-debian-deps.py --suite stretch-backports --package lava-dispatcher _build/lava-dispatcher_*stretch*
  .gitlab-ci/build/debian/check-debian-deps.py --suite stretch-backports --package lava-server _build/lava-server_*stretch*
fi
