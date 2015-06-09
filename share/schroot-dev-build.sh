#!/bin/sh

set -e

if [ -z "$3" ]; then
	echo "Usage: <package> <chroot> <suite>"
	echo "A suitable schroot must already have been prepared"
	echo "and the Debian unstable LAVA dependencies made available"
	echo "inside that chroot."
	exit 1
fi

chroot=$2
suite=$3
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
dch --force-distribution -v ${VERSION}-1 -D ${suite} "Local developer build"
if [ -n "${LOG}" ]; then
  dch -a ${LOG}
fi
sbuild -A -s -c ${chroot} -d ${suite}
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
