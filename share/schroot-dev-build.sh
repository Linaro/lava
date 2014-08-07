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
VERSION=`python ./version.py`
if [ -d './dist/' ]; then
	rm -f ./dist/*
fi
python setup.py sdist
DIR=`mktemp -d`
mv -v ./dist/${NAME}-${VERSION}.tar.gz ${DIR}/${NAME}_${VERSION}.orig.tar.gz
cd ${DIR}
git clone https://github.com/Linaro/pkg-${NAME}.git
tar -xzf ${NAME}_${VERSION}.orig.tar.gz
cd ${DIR}/pkg-${NAME}/
dpkg-checkbuilddeps
git archive master debian | tar -x -C ../${NAME}-${VERSION}
cd ${DIR}/${NAME}-${VERSION}
dch --force-distribution -v ${VERSION}-1ubuntu1 -D ${suite} "Local developer build"
sbuild -A -s -c ${chroot} -d ${suite}
cd ${DIR}
rm -rf ${DIR}/pkg-${NAME}
rm -rf ${DIR}/${NAME}-${VERSION}
if [ -x /usr/bin/dcmd ]; then
	dcmd ls ${DIR}/${NAME}_${VERSION}*.changes
else
	echo ${DIR}
	ls ${DIR}
fi
