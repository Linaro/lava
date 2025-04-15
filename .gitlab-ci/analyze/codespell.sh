#!/bin/sh

set -e

if [ "$1" = "setup" ]
then
  apt-get install --no-install-recommends --yes codespell
else
  IGNORE_WORDS_FILENAME="$(dirname "$0")"/codespell.ignore

  codespell \
    --enable-colors \
    --context 2 \
    --skip='tmp,.git,*.svg,*.pyc,*.png,*.gif,*.doctree,*.pickle,*.po,*.woff,*.woff2,*.ico,*.odg,*.dia,*.sw*,tags,jquery*.js,anchor-v*.js,kernel*.txt' \
    --ignore-words="$IGNORE_WORDS_FILENAME" \
    "$@"
fi
