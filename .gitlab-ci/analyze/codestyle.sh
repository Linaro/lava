#!/bin/sh

set -e

if [ "$1" = "setup" ]
then
  set -x
  apt-get update -qq
  apt-get install --no-install-recommends -y pycodestyle
else
  set -x
  pycodestyle --ignore E501,E203,W503 .
fi
