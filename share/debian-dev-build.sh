#!/bin/bash

set -e

SUITE=unstable
DIR="../build-area/"
DEBUILD_OPTS=" -sa"

while getopts ":a:o:s:B" opt; do
  case $opt in
    a)
      ARCH=$OPTARG
      set +e
      chk=`dpkg-architecture -a$ARCH > /dev/null 2>&1 ; echo $?`
      set -e
      if [ $chk != 0 ]; then
          echo "Did not recognise ${ARCH} as a Debian architecture name. Exit."
          exit 1
      fi
      # preserve the .dsc
      DEBUILD_OPTS=" -a${ARCH}"
      ;;
    B)
      # only build arch:any binary packages
      DEBUILD_OPTS=" -B"
      ;;
    s)
      SUITE=$OPTARG
      ;;
    o)
      DIR=`readlink -f $OPTARG`
      ;;
    \?)
      echo "[LAVA-DEV] Invalid option: -$OPTARG" >&2
      echo
      echo "Usage: [-a <architecture> -o <directory> -s <suite> -B]"
      echo
      echo "If architecture is a known Debian architecture, build"
      echo "a binary-only package for this architecture. e.g. armhf or arm64"
      echo "Builds a sourceful native package locally, using debuild."
      echo "Specify the build directory using -o - default ../build-area"
      echo "Use -B to only build the architecture specific binary package"
      echo "e.g. when building lava-dispatcher on arm64."
      exit 1
      ;;
  esac
done

# lintian is disabled because it will complain about the
# change to a native build.
DEBUILD_OPTS=" --no-lintian -uc -us ${DEBUILD_OPTS}"

if [ ! -d ${DIR} ]; then
  mkdir ${DIR}
fi

if [ -x ./lava_common/version.py ]; then
  # native version for developer build
  VERSION=`python3 ./lava_common/version.py |tr - .`
else
  echo "[LAVA-DEV] Unable to find ./lava_common/version.py"
  exit 1
fi

RELEASE=9999
if [ "${SUITE}" != "unstable" -a "${SUITE}" != "sid" ]; then
  RELEASE="$(distro-info --release --$(distro-info --alias=${SUITE}))"
fi

dpkg-checkbuilddeps
LOCAL=`git diff | wc -l`
if [ ${LOCAL} != 0 ]; then
    echo "[LAVA-DEV] You have uncommitted changes in your source tree:"
    git status
    exit 3
fi

if [ -d './dist/' ]; then
    rm -f ./dist/*
fi

if [ -d .git ]; then
  LOG=`git log -n1 --pretty=format:"Last change %h by %an, %ar. %s%n" --no-merges`
fi
NAME=`dpkg-parsechangelog |grep Source|cut -d" " -f2`

BUILDDIR="${DIR}/lava-${VERSION}"
mkdir -p "${BUILDDIR}"
git archive HEAD | tar xf - -C "${BUILDDIR}"
cd "${BUILDDIR}"

export GIT_COMMITTER_NAME="lava-dev debian build script"
export GIT_COMMITTER_EMAIL="lava-dev@lavasoftware.org"
export GIT_AUTHOR_NAME="lava-dev debian build script"
export GIT_AUTHOR_EMAIL="lava-dev@lavasoftware.org"
export DEBEMAIL=lava-dev@lavasoftware.org
export DEBFULLNAME=lava-dev debian build script

# Save the version string
echo "${VERSION}" > lava_common/VERSION

# convert to a native package to include local changes.
echo "3.0 (native)" > debian/source/format
BUILD_SUITE="${SUITE}"
dch --force-distribution -b -v "${VERSION}+${RELEASE}+${SUITE}" -D ${BUILD_SUITE} "Local developer native build for ${BUILD_SUITE}"
if [ -n "${LOG}" ]; then
  dch -a "${LOG}"
fi

debuild ${DEBUILD_OPTS}
cd -

CHANGES="${DIR}/${NAME}_${VERSION}*.changes"
echo
echo ${LOG}
echo
echo Use "zless /usr/share/doc/${NAME}/changelog.Debian.gz"
echo to view the changelog, once packages are installed.
echo
if [ -x /usr/bin/dcmd ]; then
    dcmd ls ${CHANGES}
fi
