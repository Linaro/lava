#!/bin/sh

set -e

if [ "$1" = "setup" ]
then
  true
else
  set -x

  # Check if the variables are defined
  if [ -z "$LAVAFED_CONTAINER_NAME" ]
  then
    echo "LAVAFED_CONTAINER_NAME is empty"
    exit 1
  fi

  # Build the image tag
  IMAGE_TAG="$CI_REGISTRY_IMAGE/amd64/lava-server"
  if [ -n "$CI_COMMIT_TAG" ]
  then
    IMAGE_TAG="$IMAGE_TAG:$CI_COMMIT_TAG"
  else
    IMAGE_TAG="$IMAGE_TAG:$(./lava_common/version.py)"
  fi

  # Check if the container is running
  version=$(docker container ls --filter name="$LAVAFED_CONTAINER_NAME" --format "{{.Image}}")
  if [ "$version" = "$IMAGE_TAG" ]
  then
    echo "Already running latest version"
    exit 0
  fi

  # Pull the image before stopping the container to reduce downtime
  echo "Pulling new image"
  docker pull "$IMAGE_TAG"

  if [ -n "$version" ]
  then
    echo "Stopping the container"
    docker container stop --time 20 "$LAVAFED_CONTAINER_NAME"
    docker container rm "$LAVAFED_CONTAINER_NAME"
  fi

  docker run --name "$LAVAFED_CONTAINER_NAME" -d \
      --restart always \
      --add-host "postgresql:172.17.0.1" \
      -p 9000:80 -p 6500:5500 -p 6555:5555 -p 6556:5556 \
      -v "/etc/lavafed/lava-dispatcher/certificates.d/:/etc/lava-dispatcher/certificates.d/" \
      -v "/etc/lavafed/lava-server/instance.conf:/etc/lava-server/instance.conf" \
      -v "/etc/lavafed/lava-server/lava-logs:/etc/lava-server/lava-logs" \
      -v "/etc/lavafed/lava-server/lava-master:/etc/lava-server/lava-master" \
      -v "/etc/lavafed/lava-server/lava-server.conf:/etc/apache2/sites-enabled/lava-server.conf" \
      -v "/etc/lavafed/lava-server/settings.conf:/etc/lava-server/settings.conf" \
      -v "lavafed-master-jobs:/var/lib/lava-server/default/media/" \
      -e SERVICES="apache2 lava-publisher lava-scheduler gunicorn" \
      "$IMAGE_TAG"
fi
