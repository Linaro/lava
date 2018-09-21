#!/bin/sh

set -e

if [ "$1" = "setup" ]
then
  true
else
  set -x
  ./share/debian-dev-build.sh -p lava -a amd64 -b master -o build
fi
