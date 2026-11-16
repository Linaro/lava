#!/bin/sh

set -e

if [ "$1" = "setup" ]
then
  apt-get build-dep --yes .
  apt-get install --no-install-recommends --yes lintian
else
  set -x
  # build the full package, including original source
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

  # Lint the build. share/debian-dev-build.sh turns the package native
  # and adds a dev changelog entry, which triggers the suppressed source
  # tags. They do not apply to real uploads.
  # trixie's lintian is older than the packaging: it does not know the
  # newer tags used in overrides (alien-tag) and flags debian/watch,
  # Standards-Version and Priority, which newer lintian accepts.
  lintian --version
  lintian --fail-on error,warning --info \
    --suppress-tags no-nmu-in-changelog,odd-historical-debian-changelog-version,source-nmu-has-incorrect-version-number \
    --suppress-tags alien-tag,debian-watch-file-in-native-package,missing-debian-watch-file-standard,newer-standards-version,recommended-field \
    _build/lava_*trixie*_amd64.changes
fi
