#!/bin/sh

set -e

if [ "$1" = "setup" ]
then
  set -x
  docker login -u gitlab-ci-token -p $CI_JOB_TOKEN $CI_REGISTRY
  apk add git
else
  set -x
  VERSION=$(git describe)
  git clone https://git.lavasoftware.org/lava/pkg/docker.git
  pkg_common=$(find build -name "lava-common_*.deb")
  pkg_dispatcher=$(find build -name "lava-dispatcher_*.deb")
  cp $pkg_common docker/lava-dispatcher/lava-common.deb
  cp $pkg_dispatcher docker/lava-dispatcher/lava-dispatcher.deb
  docker build -t $IMAGE_TAG:$VERSION docker/lava-dispatcher
  if [ "$CI_COMMIT_REF_NAME" = "master" -o -n "$CI_COMMIT_TAG" ]
  then
    docker push $IMAGE_TAG:$VERSION
  fi
fi
