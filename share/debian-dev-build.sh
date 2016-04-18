#!/bin/sh

set -e

BRANCH=master
ARCH=''

while getopts ":p:a:b:" opt; do
  case $opt in
    p)
      NAME=$OPTARG
      ;;
    a)
      ARCH=$OPTARG
      set +e
      chk=`dpkg-architecture -a$ARCH > /dev/null 2>&1 ; echo $?`
      set -e
      if [ $chk != 0 ]; then
          echo "Did not recognise ${ARCH} as a Debian architecture name. Exit."
          exit 1
      fi
      ARCH="-a${ARCH} -b"
      ;;
    b)
      BRANCH=$OPTARG
      ;;
    \?)
      echo "Invalid option: -$OPTARG" >&2
      ;;
  esac
done

if [ -z "$NAME" ]; then

    echo "Usage: -p <package> [-a <architecture> -b <branch>]"
    echo "Builds a sourceful package locally, using debuild."
    echo "If architecture is a known Debian architecture, build"
    echo "a binary-only package for this architecture. e.g. armhf or arm64"
    echo "Branch specifies the packaging branch to use from github."
    exit 1
fi
if [ -x ./version.py ]; then
  VERSION=`python ./version.py`
else
  VERSION=`python setup.py --version`
fi
if [ -d './dist/' ]; then
    rm -f ./dist/*
fi
python setup.py sdist
if [ -d .git ]; then
  LOG=`git log -n1 --pretty=format:"Last change %h by %an, %ar. %s%n" --no-merges`
fi
if [ ! -e ./dist/${NAME}-${VERSION}.tar.gz ]; then
	# setuptools/pkg-resources in jessie silently converts + to -
	# setuptools/pkg-resource in unstable requires + and disallows -
	VERSION=`echo ${VERSION}| sed -e 's/\([0-9]\)+/\1-/'`
fi
DIR=`mktemp -d`
if [ -f "./dist/${NAME}-${VERSION}.tar.gz" ]; then
  mv -v ./dist/${NAME}-${VERSION}.tar.gz ${DIR}/${NAME}_${VERSION}.orig.tar.gz
else
  echo "WARNING: broken setuptools tarball - Debian bug #786977"
  mv -v ./dist/${NAME}*.tar.gz ${DIR}/${NAME}_${VERSION}.orig.tar.gz
fi
cd ${DIR}
git clone https://github.com/Linaro/pkg-${NAME}.git
tar -xzf ${NAME}_${VERSION}.orig.tar.gz
if [ ! -d ${DIR}/${NAME}-${VERSION} ]; then
  mv -v ${DIR}/${NAME}-* ${DIR}/${NAME}-${VERSION}
fi
cd ${DIR}/pkg-${NAME}/
git checkout ${BRANCH}
dpkg-checkbuilddeps
git archive ${BRANCH} debian | tar -x -C ../${NAME}-${VERSION}
cd ${DIR}/${NAME}-${VERSION}
dch -v ${VERSION}-1 -D unstable "Local developer build"
if [ -n "${LOG}" ]; then
  dch -a "${LOG}"
fi
debuild -sa -uc -us $ARCH
cd ${DIR}
rm -rf ${DIR}/pkg-${NAME}
rm -rf ${DIR}/${NAME}-${VERSION}
echo
echo ${LOG}
echo
echo Use "zless /usr/share/doc/${NAME}/changelog.Debian.gz"
echo to view the changelog, once packages are installed.
echo
if [ -x /usr/bin/dcmd ]; then
    dcmd ls ${DIR}/${NAME}_${VERSION}*.changes
else
    echo ${DIR}
    ls ${DIR}
fi
