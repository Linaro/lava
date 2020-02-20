#!/bin/sh

set -e

if [ "$1" = "setup" ]
then
  apt-get -q update
  apt-get install --no-install-recommends --yes python3 python3-voluptuous python3-yaml
else
  # documentation
  PYTHONPATH=. ./share/lava-schema.py job doc/v2/examples/test-jobs/*.yaml

  # lava_dispatcher
  EXCLUDE="bbb-group-vland-alpha.yaml bbb-group-vland-beta.yaml bbb-ssh-guest.yaml kvm-multinode-client.yaml kvm-multinode-server.yaml test_action-1.yaml test_action-2.yaml"
  CMD="--exclude $(echo ${EXCLUDE} | sed "s# # --exclude #g#")"
  PYTHONPATH=. ./share/lava-schema.py job ${CMD} tests/lava_dispatcher/sample_jobs/*.yaml

  # lava_results_app
  PYTHONPATH=. ./share/lava-schema.py job tests/lava_results_app/*.yaml

  # lava_scheduler_app
  EXCLUDE="kvm-multinode-client.yaml kvm-multinode-server.yaml qemu-ssh-guest-1.yaml qemu-ssh-guest-2.yaml qemu-ssh-parent.yaml"
  CMD="--exclude $(echo ${EXCLUDE} | sed "s# # --exclude #g#")"
  PYTHONPATH=. ./share/lava-schema.py job ${CMD} tests/lava_scheduler_app/sample_jobs/*.yaml
  PYTHONPATH=. ./share/lava-schema.py job tests/lava_scheduler_app/health-checks/*.yaml

  PYTHONPATH=. ./share/lava-schema.py device --path etc/dispatcher-config/device-types tests/lava_scheduler_app/devices/*.jinja2
fi
