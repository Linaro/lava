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
  pkg_server=$(find build -name "lava-server_*.deb")
  pkg_server_doc=$(find build -name "lava-server-doc_*.deb")
  cp $pkg_common docker/lava-server/lava-common.deb
  cp $pkg_server docker/lava-server/lava-server.deb
  cp $pkg_server_doc docker/lava-server/lava-server-doc.deb
  docker build -t $IMAGE_TAG:$VERSION docker/lava-server
  if [ "$CI_COMMIT_REF_NAME" = "master" ]
  then
    docker push $IMAGE_TAG:$VERSION
  fi
fi
