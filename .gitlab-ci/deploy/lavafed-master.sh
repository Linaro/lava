#!/bin/sh

set -e

if [ "$1" = "setup" ]
then
  true
else
  set -x

  # Check if the variables are defined
  if [ -z "$LAVAFED_PATH" ]
  then
    echo "LAVAFED_PATH is empty"
    exit 1
  elif [ -z "$LAVAFED_CONTAINER_NAME" ]
    echo "LAVAFED_CONTAINER_NAME is empty"
    exit 1
  fi

  # Build the image tag
  IMAGE_TAG="$CI_REGISTRY_IMAGE/amd64/lava-server"
  if [ -n "$CI_COMMIT_TAG" ]
  then
    IMAGE_TAG="$IMAGE_TAG:$CI_COMMIT_TAG"
  else
    IMAGE_TAG="$IMAGE_TAG:$CI_COMMIT_REF_SLUG-$(./version.py)"
  fi

  # Check if the container is running
  hash=$(docker container ls --filter name="$LAVAFED_CONTAINER_NAME" --quiet)
  if [ -n "$hash" ]
  then
    echo "Stopping the container"
    docker container stop --time 20 "$LAVAFED_CONTAINER_NAME"
  fi

  cd "$LAVAFED_PATH"
  docker run --name "$LAVAFED_CONTAINER_NAME" --rm -d \
      -p 9000:80 -p 6500:5500 -p 6555:5555 -p 6556:5556 \
      -v "/home/lavafed/lava-master/certificates.d/:/etc/lava-dispatcher/certificates.d/" \
      -v "/home/lavafed/lava-master/instance.conf:/etc/lava-server/instance.conf" \
      -v "/home/lavafed/lava-master/lava-logs:/etc/lava-server/lava-logs" \
      -v "/home/lavafed/lava-master/lava-master:/etc/lava-server/lava-master" \
      -v "/home/lavafed/lava-master/lava-server.conf:/etc/apache2/sites-enabled/lava-server.conf" \
      -v "/home/lavafed/lava-master/settings.conf:/etc/lava-server/settings.conf" \
      -v "lavafed-master-db:/var/lib/postgresql/9.6/main/" \
      -v "lavafed-master-jobs:/var/lib/lava-server/default/media/" \
      "$IMAGE_TAG"
fi
