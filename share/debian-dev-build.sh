#!/bin/bash

set -e

SUITE=unstable
DIR="../build-area/"
SCRATCH="lavadevscratch"
BRANCH="master"
DEBUILD_OPTS=" -sa"
GBP_OPTS="--git-no-pristine-tar --git-no-overlay "

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
GBP_OPTS+=" --git-export-dir=${DIR}"

# store the current branch name
BRANCH=`git branch | grep \* | cut -d ' ' -f2`

function finish {
  git checkout ${BRANCH}
  git branch -D ${SCRATCH}
}

if [ -x ./version.py ]; then
  # native version for developer build
  VERSION=`python3 ./version.py |tr - .`
else
  echo "[LAVA-DEV] Unable to find ./version.py"
  exit 1
fi

if [ ! -x /usr/bin/gbp ]; then
    echo "[LAVA-DEV] This script needs git-buildpackage to be installed"
    exit 2
fi

dpkg-checkbuilddeps
fakeroot debian/rules clean
LOCAL=`git ls-files -m -o --exclude-standard|wc -l`
if [ ${LOCAL} != 0 ]; then
    echo "[LAVA-DEV] You have uncommitted changes in your source tree:"
    git status
    exit 3
fi

# only trap here to avoid branch changes without a branch
trap finish EXIT

if [ -d './dist/' ]; then
    rm -f ./dist/*
fi

if [ -d .git ]; then
  LOG=`git log -n1 --pretty=format:"Last change %h by %an, %ar. %s%n" --no-merges`
fi
NAME=`dpkg-parsechangelog |grep Source|cut -d" " -f2`

# from here on, errors should clean up
git checkout -b ${SCRATCH}
export GIT_COMMITTER_NAME="lava-dev debian build script"
export GIT_COMMITTER_EMAIL="lava-dev@lavasoftware.org"
export GIT_AUTHOR_NAME="lava-dev debian build script"
export GIT_AUTHOR_EMAIL="lava-dev@lavasoftware.org"
export DEBEMAIL=lava-dev@lavasoftware.org
export DEBFULLNAME=lava-dev debian build script

# convert to a native package to include local changes.
echo "3.0 (native)" > debian/source/format
git add debian/source/format
cat << EOF > debian/gbp.conf
[DEFAULT]
overlay = False
pristine-tar = False
cleaner = true
EOF
git add debian/gbp.conf
dch -b -v "${VERSION}+${SUITE}" -D ${SUITE} "Local developer native build for ${SUITE}"
if [ -n "${LOG}" ]; then
  dch -a "${LOG}"
fi
git add debian
git commit -m "Local developer native build for ${SUITE}"

CHANGES="${DIR}/${NAME}_${VERSION}*.changes"
gbp buildpackage ${GBP_OPTS} --git-debian-branch=${SCRATCH} --git-builder="debuild ${DEBUILD_OPTS}"
echo
echo ${LOG}
echo
echo Use "zless /usr/share/doc/${NAME}/changelog.Debian.gz"
echo to view the changelog, once packages are installed.
echo
if [ -x /usr/bin/dcmd ]; then
    dcmd ls ${CHANGES}
fi
