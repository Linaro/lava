#!/bin/bash
# Copyright (C) 2025 Collabora Limited
#
# Author: Igor Ponomarev <igor.ponomarev@collabora.com>
#
# SPDX-License-Identifier: GPL-2.0-or-later

set -eu -o pipefail

if [ "${1:-}" = "setup" ]
then
  apt-get update
  apt-get install --no-install-recommends --yes codespell git ca-certificates
else
  IGNORE_WORDS_FILENAME="$(dirname "${BASH_SOURCE[0]}")"/codespell.ignore

  echo "Adding ${CI_MERGE_REQUEST_PROJECT_URL} as git remote"
  git remote add "upstream" "${CI_MERGE_REQUEST_PROJECT_URL}.git"
  git fetch --depth=50 upstream "$CI_MERGE_REQUEST_TARGET_BRANCH_NAME"

  TARGET_REFSPEC="upstream/${CI_MERGE_REQUEST_TARGET_BRANCH_NAME}"
  REFSPEC_TO_CHECK="${TARGET_REFSPEC}..HEAD"

  echo "Spellchecking $(git log --format=oneline "$REFSPEC_TO_CHECK" -- | wc --lines) commit messages"
  git log --format='%s%n%n%b%n%n' "$REFSPEC_TO_CHECK" -- | codespell --ignore-words="$IGNORE_WORDS_FILENAME" --enable-colors --context 2 -
fi
