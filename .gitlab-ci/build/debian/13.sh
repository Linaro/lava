#!/bin/sh

set -e

if [ "$1" = "setup" ]
then
  apt-get build-dep --yes .
else
  set -x
  # build the full package, including original source for bookworm.
  ./share/debian-dev-build.sh -o _build -s trixie
  debc $(find _build -name 'lava_*_amd64.changes' 2>/dev/null|head -n1)

  # Check dependencies
  .gitlab-ci/build/debian/check-debian-deps.py --suite trixie --package lava-common _build/lava-common_*trixie*
  .gitlab-ci/build/debian/check-debian-deps.py --suite trixie --package lava-dispatcher _build/lava-dispatcher_*trixie*
  .gitlab-ci/build/debian/check-debian-deps.py --suite trixie --package lava-dispatcher-host _build/lava-dispatcher-host_*trixie*
  .gitlab-ci/build/debian/check-debian-deps.py --suite trixie --package lava-server _build/lava-server_*trixie*

  # Check each package only ships its own Python modules & /usr/bin scripts
  .gitlab-ci/build/debian/check-debian-contents.sh lava-common _build/lava-common_*trixie*.deb
  .gitlab-ci/build/debian/check-debian-contents.sh lava-coordinator _build/lava-coordinator_*trixie*.deb
  .gitlab-ci/build/debian/check-debian-contents.sh lava-dispatcher _build/lava-dispatcher_*trixie*.deb
  .gitlab-ci/build/debian/check-debian-contents.sh lava-dispatcher-host _build/lava-dispatcher-host_*trixie*.deb
  .gitlab-ci/build/debian/check-debian-contents.sh lava-server _build/lava-server_*trixie*.deb
fi
