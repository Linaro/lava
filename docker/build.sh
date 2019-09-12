#!/bin/sh
set -e

export DOCKER_BUILDKIT=1

ARCH=$(uname -m)
if [ "$ARCH" = "x86_64" ]
then
  dir="amd64"
else
  dir="aarch64"
fi

IMAGES=$(find $dir -maxdepth 1 -name "*base" -type d \( ! -path './.*' \) \( ! -path . \) | sort | sed "s#^./##")
IMAGES=${1:-$IMAGES}

./docker/share/generate.py
DIFF=$(git diff)
if [ -n "$DIFF" ]
then
  echo "Dockerfiles not up to date"
  exit 1
fi

for image in $IMAGES
do
  echo "$image:"
  echo "* building"
  hash=$(docker build --force-rm -q "$image")
  echo "=> $hash"
  echo "* testing"
  rm -f "$image.log"
  docker run --rm --volume "$PWD/$image/test.sh:/root/test.sh" "$hash" /root/test.sh > "$image.log" 2>&1
  echo "=> done"
  echo
done
