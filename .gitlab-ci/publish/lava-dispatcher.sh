#!/bin/sh

set -e

if [ "$1" = "setup" ]
then
  set -x
  docker login -u gitlab-ci-token -p $CI_JOB_TOKEN $CI_REGISTRY
  apk add git
else
  set -x

  # Build the image tag
  if [ "$CI_COMMIT_TAG" ]
  then
    IMAGE_TAG="$IMAGE_TAG:$CI_COMMIT_TAG"
  else
    IMAGE_TAG="$IMAGE_TAG/$CI_COMMIT_REF_SLUG:$(git describe)"
  fi

  git clone https://git.lavasoftware.org/lava/pkg/docker.git
  pkg_common=$(find build -name "lava-common_*.deb")
  pkg_dispatcher=$(find build -name "lava-dispatcher_*.deb")
  cp $pkg_common docker/lava-dispatcher/lava-common.deb
  cp $pkg_dispatcher docker/lava-dispatcher/lava-dispatcher.deb
  docker build -t $IMAGE_TAG docker/lava-dispatcher

  # Push only for tags or master
  if [ "$CI_COMMIT_REF_SLUG" = "master" -o -n "$CI_COMMIT_TAG" ]
  then
    docker push $IMAGE_TAG
  fi
fi
