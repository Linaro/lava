#!/bin/sh

set -e

if [ -z "$1" ]; then
	echo "Usage: <package>"
	exit 1
fi

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
dch -v ${VERSION}-1 -D unstable "Local developer build"
debuild -sa -uc -us
cd ${DIR}
rm -rf ${DIR}/pkg-${NAME}
rm -rf ${DIR}/${NAME}-${VERSION}
if [ -x /usr/bin/dcmd ]; then
	dcmd ls ${DIR}/${NAME}_${VERSION}*.changes
else
	echo ${DIR}
	ls ${DIR}
fi
