#!/bin/sh

set -e

if [ "$1" = "setup" ]
then
  echo "nothing to do"
else
  set -x
  pycodestyle --ignore E501,E203,W503,W504 .
fi
