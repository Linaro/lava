#!/bin/sh

set -e

if [ -z "$1" ]; then
    echo "Usage: <package> [<architecture>]"
    echo "If architecture is a known Debian architecture, build"
    echo "a binary-only package for this architecture."
    echo "e.g. armhf or arm64"
    exit 1
fi

if [ -n "$2" ]; then
    set +e
    chk=`dpkg-architecture -a$2 > /dev/null 2>&1 ; echo $?`
    set -e
    if [ $chk = 0 ]; then
        echo "Building for architecture $2"
        arch="-a$2 -b"
    else
        echo "Did not recognise $2 as a Debian architecture name. Exit."
        exit 1
    fi
fi
PWD=`pwd`
NAME=${1}
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
DIR=`mktemp -d`
if [ -f './dist/${NAME}-${VERSION}.tar.gz' ]; then
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
dpkg-checkbuilddeps
git archive master debian | tar -x -C ../${NAME}-${VERSION}
cd ${DIR}/${NAME}-${VERSION}
dch -v ${VERSION}-1 -D unstable "Local developer build"
if [ -n "${LOG}" ]; then
  dch -a ${LOG}
fi
debuild -sa -uc -us $arch
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
