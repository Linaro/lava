#!/bin/sh

set -e

if [ "$1" = "setup" ]
then
  set -x
  docker login -u gitlab-ci-token -p $CI_JOB_TOKEN $CI_REGISTRY
  apk add git python3
else
  set -x

  # Build the image name
  IMAGE_TAG=${CI_COMMIT_TAG:-$(./version.py)}
  IMAGE="$IMAGE_NAME:$IMAGE_TAG"
  # Build the base image name
  BASE_IMAGE_NAME="$IMAGE_NAME-base"
  BASE_IMAGE_TAG=$(./version.py $(git log -n 1 --format="%H" docker/))
  BASE_IMAGE="$BASE_IMAGE_NAME:$BASE_IMAGE_TAG"
  BASE_IMAGE_NEW="$BASE_IMAGE_NAME:$IMAGE_TAG"

  # Pull the base image from cache (local or remote) or build it
  docker inspect $BASE_IMAGE 2>/dev/null || docker pull $BASE_IMAGE 2>/dev/null || docker build -t $BASE_IMAGE docker/amd64/lava-dispatcher-base
  # Create a tag with the current version tag
  docker tag $BASE_IMAGE $BASE_IMAGE_NEW

  # Build the image
  pkg_lxc=$(find _build -name "lava-lxc-mocker_*.deb")
  pkg_common=$(find _build -name "lava-common_*.deb")
  pkg_dispatcher=$(find _build -name "lava-dispatcher_*.deb")
  cp $pkg_lxc docker/amd64/lava-dispatcher/lava-lxc.deb
  cp $pkg_common docker/amd64/lava-dispatcher/lava-common.deb
  cp $pkg_dispatcher docker/amd64/lava-dispatcher/lava-dispatcher.deb
  docker build -t $IMAGE --build-arg base_image="$BASE_IMAGE_NEW" docker/amd64/lava-dispatcher

  # Push only for tags or master
  if [ "$CI_COMMIT_REF_SLUG" = "master" -o -n "$CI_COMMIT_TAG" ]
  then
    docker push $BASE_IMAGE
    docker push $BASE_IMAGE_NEW
    docker push $IMAGE
  fi
fi
