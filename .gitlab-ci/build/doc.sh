#!/bin/sh

set -e

if [ "$1" = "setup" ]
then
  set -x
  apt-get update -qq
  apt-get install --no-install-recommends -y git make python3 python3-sphinx python3-sphinx-bootstrap-theme
else
  set -x
  make -C doc/v2 html
fi
