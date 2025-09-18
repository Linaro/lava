#!/bin/sh

set -e

if [ "$1" = "setup" ]
then
  set -x
  apt-get -q update
  DEPS=$(./share/requires.py -p lava-server -d debian -s bookworm -n)
  apt-get install --no-install-recommends --yes $DEPS
  sudo -u postgres psql -c "CREATE DATABASE devel ;"
else
  set -x
  python3 ./manage.py makemigrations --verbosity 3 --no-input --check --dry-run
fi
