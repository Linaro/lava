#!/bin/sh
#
# Copyright (C) 2026 LAVA contributors
#
# SPDX-License-Identifier: GPL-2.0-or-later
#
# Verify that a binary package only ships the Python modules and executables
# that belong to it. The Debian build splits the source tree across the binary
# packages by invoking setup.py once per component (see debian/rules). A
# misconfiguration (for example declaring package discovery in pyproject.toml)
# can make setuptools ship every module or every script in every package. This
# guards against that regression.
#
# Usage: check-debian-contents.sh <package-name> <file.deb>

set -eu

DIST_PACKAGES="./usr/lib/python3/dist-packages/"
BIN_DIR="./usr/bin/"

# Expected Python modules for a given binary package. This should match each
# Debian package's Python "packages" list in setup.py.
modules_for() {
  case "$1" in
    lava-common)          echo "lava_common" ;;
    lava-coordinator)     echo "lava" ;;
    lava-dispatcher)      echo "lava_dispatcher" ;;
    lava-dispatcher-host) echo "lava_dispatcher_host" ;;
    lava-server)          echo "lava_rest_app lava_results_app lava_scheduler_app lava_server linaro_django_xmlrpc" ;;
    *) return 1 ;;
  esac
}

# Expected executables under /usr/bin for a given binary package. This should
# match each Debian package's "scripts" list in setup.py.
binaries_for() {
  case "$1" in
    lava-common)          echo "" ;;
    lava-coordinator)     echo "lava-coordinator" ;;
    lava-dispatcher)      echo "lava-outerr lava-run lava-worker" ;;
    lava-dispatcher-host) echo "lava-dispatcher-host lava-docker-worker lava-dispatcher-host-server" ;;
    lava-server)          echo "lava-server" ;;
    *) return 1 ;;
  esac
}

PACKAGE="${1:?usage: check-debian-contents.sh <package> <file.deb>}"
DEB="${2:?usage: check-debian-contents.sh <package> <file.deb>}"

# Expected contents for this package.
ALLOWED_MODULES=$(modules_for "$PACKAGE") || { echo "Unknown package: $PACKAGE" >&2; exit 2; }
ALLOWED_BINARIES=$(binaries_for "$PACKAGE")

# True if $1 appears as a word in the list $2. Word splitting handles lists
# separated by whitespace (e.g. spaces or newlines).
in_list() {
  needle="$1"
  for w in $2; do
    [ "$w" = "$needle" ] && return 0
  done
  return 1
}

failures=0

# Compare the expected and present contents for one location, reporting any
# leaked (unexpected) or missing entries. $1 is a human-readable label used in
# messages, $2 the allowed list and $3 the list actually present in the deb.
compare() {
  label="$1"
  allowed="$2"
  present="$3"

  # Only the expected entries may be present; anything else is a leak.
  for p in $present; do
    if ! in_list "$p" "$allowed"; then
      echo "* $p [UNEXPECTED $label - does not belong to this package]"
      failures=$((failures + 1))
    fi
  done

  # Every expected entry must be present.
  for a in $allowed; do
    if ! in_list "$a" "$present"; then
      echo "* $a [MISSING $label]"
      failures=$((failures + 1))
    fi
  done

  return 0
}

# Get Python module names under dist-packages, ignoring metadata directories.
PRESENT_MODULES=$(dpkg-deb -c "$DEB" \
  | awk '{print $NF}' \
  | sed -n "s#^${DIST_PACKAGES}##p" \
  | cut -d/ -f1 \
  | grep -vE '^$|\.(egg-info|dist-info|pth)$' \
  | sort -u || true)

# Get executable names directly under /usr/bin. Field 6 is the path even for
# symlinks (where $NF would be the link target instead of the link name).
PRESENT_BINARIES=$(dpkg-deb -c "$DEB" \
  | awk '{print $6}' \
  | sed -n "s#^${BIN_DIR}##p" \
  | cut -d/ -f1 \
  | grep -vE '^$' \
  | sort -u || true)

compare "module" "$ALLOWED_MODULES" "$PRESENT_MODULES"
compare "binary" "$ALLOWED_BINARIES" "$PRESENT_BINARIES"

if [ "$failures" -eq 0 ]; then
  echo "$PACKAGE: contents OK (modules: $ALLOWED_MODULES; binaries: ${ALLOWED_BINARIES:-none})"
fi

[ "$failures" -eq 0 ]
