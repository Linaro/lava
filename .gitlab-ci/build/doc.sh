#!/bin/sh

set -e

if [ "$1" = "setup" ]
then
  set -x
  apt-get update -qq
  apt-get install --no-install-recommends -y git mkdocs-material python3-pymdownx
else
  set -x
  mkdocs build -f doc/mkdocs.yml
fi
