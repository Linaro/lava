#!/bin/sh
set -e

IMAGES=$(find . -maxdepth 1 -name "*base" -type d \( ! -path './.*' \) \( ! -path . \) | sort | sed "s#^./##")
IMAGES=${1:-$IMAGES}

for image in $IMAGES
do
  echo "$image:"
  echo "* building"
  hash=$(docker build --force-rm -q "$image")
  echo "=> $hash"
  echo "* testing"
  docker run --rm --volume "$PWD/$image/test.sh:/root/test.sh" --volume "$PWD/$image/:/root/image" "$hash" /root/test.sh > "$image.log" 2>&1
  echo "=> done"
  echo
done
