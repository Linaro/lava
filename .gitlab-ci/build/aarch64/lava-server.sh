#!/bin/sh

set -e

export DOCKER_BUILDKIT=1

if [ "$1" = "setup" ]
then
  set -x
  docker login -u gitlab-ci-token -p $CI_JOB_TOKEN $CI_REGISTRY
  apk add git python3
else
  set -x

  # Default values
  IMAGE_NAME=${IMAGE_NAME:-"hub.lavasoftware.org/lava/lava/aarch64/lava-server"}

  # Build the image name
  IMAGE_TAG=$(./lava_common/version.py)
  IMAGE="$IMAGE_NAME:$IMAGE_TAG"
  # Build the base image name
  BASE_IMAGE_NAME="$IMAGE_NAME-base"
  BASE_IMAGE_TAG=$(./lava_common/version.py $(git log -n 1 --format="%H" docker/))
  BASE_IMAGE="$BASE_IMAGE_NAME:$BASE_IMAGE_TAG"
  BASE_IMAGE_NEW="$BASE_IMAGE_NAME:$IMAGE_TAG"

  # Pull the base image from cache (local or remote) or build it
  docker inspect $BASE_IMAGE 2>/dev/null || docker pull $BASE_IMAGE 2>/dev/null || docker build -t $BASE_IMAGE docker/aarch64/lava-server-base
  # Create a tag with the current version tag
  docker tag $BASE_IMAGE $BASE_IMAGE_NEW

  # Build the image
  echo "$IMAGE_TAG" > lava_common/VERSION
  DOCKER_BUILDKIT=1 docker build -t $IMAGE --build-arg base_image="$BASE_IMAGE_NEW" -f docker/aarch64/lava-server/Dockerfile .

  # Push only for tags or master
  if [ "$CI_COMMIT_REF_SLUG" = "master" -o -n "$CI_COMMIT_TAG" ]
  then
    docker push $BASE_IMAGE
    docker push $BASE_IMAGE_NEW
    docker push $IMAGE
  fi
fi
