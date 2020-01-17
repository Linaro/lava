#!/bin/sh

set -e

if [ "$1" = "setup" ]
then
  true
else
  set -x
  # build the full package, including original source for buster.
  ./share/debian-dev-build.sh -o _build -s buster
  debc $(find _build -name 'lava_*_amd64.changes' 2>/dev/null|head -n1)

  # Check dependencies
  .gitlab-ci/build/debian/check-debian-deps.py --suite buster --package lava-common _build/lava-common_*buster*
  .gitlab-ci/build/debian/check-debian-deps.py --suite buster --package lava-dispatcher _build/lava-dispatcher_*buster*
  .gitlab-ci/build/debian/check-debian-deps.py --suite buster --package lava-server _build/lava-server_*buster*
fi
