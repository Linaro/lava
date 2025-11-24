#!/bin/sh

set -e

if [ "$1" = "setup" ]
then
  set -x
  apt-get -q update
  apt-get install --no-install-recommends --yes pylint python3-pylint-django
else
  set -x
  # See pyproject.toml for the list of enabled and disabled checks
  DJANGO_SETTINGS_MODULE=lava_server.settings.dev \
  PYTHONPATH=. \
    pylint --verbose \
      lava \
      lava_common \
      lava_dispatcher \
      lava_dispatcher_host \
      lava_rest_app \
      lava_results_app \
      lava_scheduler_app \
      lava_server \
      linaro_django_xmlrpc \
      share \
      tests \
      lava/dispatcher/lava-run \
      lava/dispatcher/lava-worker \
      "$@"
fi
