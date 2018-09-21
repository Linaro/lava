#!/bin/sh

set -e

if [ "$1" = "setup" ]
then
  true
else
  set -x
  export SP_VERSION=$(echo "$CI_SERVER_VERSION" | sed 's/^\([0-9]*\)\.\([0-9]*\).*/\1-\2-stable/')
  docker run --env SAST_CONFIDENCE_LEVEL="${SAST_CONFIDENCE_LEVEL:-3}" \
             --volume "$PWD:/code" \
             --volume /var/run/docker.sock:/var/run/docker.sock \
             "registry.gitlab.com/gitlab-org/security-products/sast:$SP_VERSION" /app/bin/run /code
fi
