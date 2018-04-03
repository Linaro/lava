#!/bin/sh

set -x
set -e

PEP8=1
PYTEST=0
ALL=1

while getopts ":pya" opt; do
  case $opt in
    p)
      # pep8 only
      PEP8=2
      ;;
    y)
      # use py.test
      PYTEST=1
      ;;
    a)
      # python3 unit tests
      ALL=1
      ;;
    \?)
      echo "Usage:"
      echo "-p - pep8 only"
      echo "-y - use py.test"
      echo "-a - run all tests: pep8 and python3"
      echo "Invalid option: -$OPTARG" >&2
      exit 1
      ;;
  esac
done

shift $((OPTIND -1))

echo "Checking pep8"
pep8 --ignore E501,E722 --exclude=".eggs/*" .

if [ ${PEP8} = 2 ]; then
    exit 0
fi

echo "Removing old .pyc files"
echo
find . -name '*.pyc' -delete
rm -rf ./.cache/

echo "Starting unit tests"
echo

if [ ${ALL} = 1 ]; then
  if [ ${PYTEST} = 1 ]; then
    py.test-3 -v lava_dispatcher/test
  else
    python3 -m unittest discover -v lava_dispatcher/test
  fi
fi
