#!/bin/sh

set -e

if [ "$1" = "setup" ]
then
  set -x
  apt-get -q update
  apt-get install --no-install-recommends --yes git python3-jinja2 python3-yaml
else
  set -x
  ./docker/share/generate.py
  if [ -n "$(git diff)" ]
  then
    exit 1
  fi
fi
