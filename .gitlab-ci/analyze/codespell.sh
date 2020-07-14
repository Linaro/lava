#!/bin/sh

set -e

if [ "$1" = "setup" ]
then
  apt-get install --no-install-recommends --yes codespell
else
  exec codespell \
    --skip='tmp,.git,*.svg,*.pyc,*.png,*.gif,*.doctree,*.pickle,*.po,*.woff,*.woff2,*.ico,*.odg,*.dia,*.sw*,tags,jquery*.js,anchor-v*.js,kernel*.txt' \
    --ignore-words=$(dirname $0)/codespell.ignore \
    "$@"
fi
