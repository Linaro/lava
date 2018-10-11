#!/bin/sh

set -e

if [ "$1" = "setup" ]
then
  true
else
  set -x
  ./share/debian-dev-build.sh -p lava -a amd64 -b master -o build
  debc $(find build -name 'lava_*_amd64.changes' 2>/dev/null|head -n1)
fi
