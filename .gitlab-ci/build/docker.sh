#!/bin/sh

set -e

export DOCKER_BUILDKIT=1

if [ "$1" = "setup" ]
then
  set -x
  docker login -u gitlab-ci-token -p $CI_JOB_TOKEN $CI_REGISTRY
  apk add git python3
else
  # image to build
  SERVICE="$1"

  if [ "$SERVICE" != "dispatcher" ] && [ "$SERVICE" != "server" ]
  then
    echo "Invalid service '$SERVICE'"
    echo "Valid values: 'dispatcher' or 'server'"
    exit 1
  fi

  BASE_DIR=$(realpath "$(dirname "$(realpath "$0")")/../../")
  cd "$BASE_DIR"

  # Current architecture
  [ "$(uname -m)" = "x86_64" ] && ARCH="amd64" || ARCH="$(uname -m)"
  # Default values
  CI_REGISTRY_IMAGE=${CI_REGISTRY_IMAGE:-"hub.lavasoftware.org/lava/lava"}
  IMAGE_NAME=${IMAGE_NAME:-"$CI_REGISTRY_IMAGE/$ARCH/lava-$SERVICE"}

  # Build the image name
  IMAGE_TAG=$(./lava_common/version.py)
  IMAGE="$IMAGE_NAME:$IMAGE_TAG"
  # Build the base image name
  BASE_IMAGE_NAME="$IMAGE_NAME-base"
  BASE_IMAGE_TAG=$(./lava_common/version.py "$(git log -n 1 --format="%H" docker/)")
  BASE_IMAGE="$BASE_IMAGE_NAME:$BASE_IMAGE_TAG"
  BASE_IMAGE_NEW="$BASE_IMAGE_NAME:$IMAGE_TAG"

  # Pull the base image from cache (local or remote) or build it
  echo "Base images:"
  echo "* old: $BASE_IMAGE"
  docker inspect "$BASE_IMAGE" 2>/dev/null >/dev/null || docker pull "$BASE_IMAGE" 2>/dev/null || true
  # Rebuild without cache on master and when tagging
  if [ "$CI_COMMIT_REF_SLUG" = "master" ] || [ -n "$CI_COMMIT_TAG" ]
  then
    NO_CACHE="--no-cache"
  fi
  docker build $NO_CACHE -t "$BASE_IMAGE" docker/lava-"$SERVICE"-base
  # Create a tag with the current version tag
  echo "* new: $BASE_IMAGE_NEW"
  docker tag "$BASE_IMAGE" "$BASE_IMAGE_NEW"

  # Build the image
  echo "Build $IMAGE"
  docker build -t "$IMAGE" --build-arg base_image="$BASE_IMAGE_NEW" --build-arg lava_version="$IMAGE_TAG" -f docker/lava-"$SERVICE"/Dockerfile .

  # Push only for tags or master
  if [ "$CI_COMMIT_REF_SLUG" = "master" ] || [ -n "$CI_COMMIT_TAG" ]
  then
    docker push "$BASE_IMAGE"
    docker push "$BASE_IMAGE_NEW"
    docker push "$IMAGE"
  fi
fi
