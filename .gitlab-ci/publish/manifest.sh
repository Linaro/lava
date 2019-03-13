#!/bin/sh

set -e

if [ "$1" = "setup" ]
then
  set -x
  docker login -u gitlab-ci-token -p $CI_JOB_TOKEN $CI_REGISTRY
  apk add git python3
else
  set -x

  # Build the image tag
  if [ -n "$CI_COMMIT_TAG" ]
  then
    IMAGE_TAG="$CI_COMMIT_TAG"
  else
    IMAGE_TAG="$(./version.py)"
  fi

  DOCKER_CLI_EXPERIMENTAL=enabled docker manifest create $CI_REGISTRY_IMAGE/lava-dispatcher:$IMAGE_TAG $CI_REGISTRY_IMAGE/amd64/lava-dispatcher:$IMAGE_TAG $CI_REGISTRY_IMAGE/aarch64/lava-dispatcher:$IMAGE_TAG
  DOCKER_CLI_EXPERIMENTAL=enabled docker manifest push $CI_REGISTRY_IMAGE/lava-dispatcher:$IMAGE_TAG

  DOCKER_CLI_EXPERIMENTAL=enabled docker manifest create $CI_REGISTRY_IMAGE/lava-server:$IMAGE_TAG $CI_REGISTRY_IMAGE/amd64/lava-server:$IMAGE_TAG $CI_REGISTRY_IMAGE/aarch64/lava-server:$IMAGE_TAG
  DOCKER_CLI_EXPERIMENTAL=enabled docker manifest push $CI_REGISTRY_IMAGE/lava-server:$IMAGE_TAG
fi
