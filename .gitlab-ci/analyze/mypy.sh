#!/bin/bash

set -e

if [ "$1" = "setup" ]
then
  apt-get -q update
  apt-get install --no-install-recommends --yes mypy python3-typeshed python3-sentry-sdk python3-magic
else
  set -x
  FILES=(
    # lava_common
    'lava_common/constants.py'
    'lava_common/converters.py'
    'lava_common/decorators.py'
    'lava_common/device_mappings.py'
    'lava_common/exceptions.py'
    'lava_common/jinja.py'
    'lava_common/log.py'
    'lava_common/timeout.py'
    'lava_common/utils.py'
    'lava_common/version.py'
    'lava_common/worker.py'
    'lava_common/yaml.py'
    # lava_dispatcher
    'lava_dispatcher/actions/base_strategy.py'
    'lava_dispatcher/actions/boot_strategy.py'
    'lava_dispatcher/actions/deploy_strategy.py'
    'lava_dispatcher/actions/test_strategy.py'
    'lava_dispatcher/utils/compression.py'
    'lava_dispatcher/utils/contextmanager.py'
    'lava_dispatcher/utils/decorator.py'
    'lava_dispatcher/utils/filesystem.py'
    'lava_dispatcher/utils/installers.py'
    'lava_dispatcher/utils/network.py'
    'lava_dispatcher/utils/shell.py'
    'lava_dispatcher/utils/strings.py'
    'lava_dispatcher/utils/vcs.py'
    'lava_dispatcher/connection.py'
    'lava_dispatcher/deployment_data.py'
  )
  mypy --python-version 3.11 --pretty --strict --follow-imports=silent "${FILES[@]}"
fi
