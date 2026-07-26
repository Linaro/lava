#!/bin/sh

set -e

if [ "$1" = "setup" ]
then
  set -x
  #uv tool install zensical
else
  set -x
  uvx zensical build -f doc/mkdocs.yml
fi
