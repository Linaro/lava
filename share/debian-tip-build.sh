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
suite=unstable
schroot=sid-amd64-sbuild
cd /home/buildd/git/${NAME}
git pull
if [ -f ../latest-${NAME} ]; then
	LATEST=`cat ../latest-${NAME}`
	NOW=`git log -n1 |grep commit`
	if [ "$LATEST" = "$NOW" ]; then
		echo Latest git commit built was: ${LATEST}
		exit 0
	fi
fi
VERSION=`python ./version.py`
if [ -d './dist/' ]; then
	rm -f ./dist/*
fi
python setup.py sdist 2>&1
DIR=`mktemp -d`
mkdir ${DIR}/${NAME}-${VERSION}
mv -v ./dist/${NAME}-${VERSION}.tar.gz ${DIR}/${NAME}_${VERSION}.orig.tar.gz
cd ../pkg-${NAME}
git pull
dpkg-checkbuilddeps
git archive master debian | tar -x -C ${DIR}/${NAME}-${VERSION}
cd ${DIR}/${NAME}-${VERSION}
dch --force-distribution -v ${VERSION}-1 -D unstable "Staging incremental build" 2>&1
#debuild -sa -uc -us $arch
sbuild -A -s -c ${schroot} -d ${suite}
cd ${DIR}
rm -rf ${DIR}/pkg-${NAME}
rm -rf ${DIR}/${NAME}-${VERSION}
reprepro -b /home/buildd/debian include sid ${DIR}/${NAME}_${VERSION}*.changes
cd /home/buildd/git/${NAME}
git log -n1 |grep commit > /home/buildd/git/latest-${NAME}
rm -rf ${DIR}/
reprepro -b /home/buildd/debian ls ${NAME}

