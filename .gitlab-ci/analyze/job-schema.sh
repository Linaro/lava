#!/bin/sh

set -e

if [ "$1" = "setup" ]
then
  apt-get -q update
  apt-get install --no-install-recommends --yes python3 python3-nose python3-voluptuous python3-yaml
else
  # documentation
  EXCLUDE="bbb-2serial.yaml bbb-lxc-ssh-guest.yaml hikey-new-connection.yaml multiple-serial-ports-lxc.yaml mustang-ssh-guest.yaml"
  CMD="--exclude $(echo ${EXCLUDE} | sed "s# # --exclude #g#")"
  PYTHONPATH=. ./share/lava-schema.py job ${CMD} doc/v2/examples/test-jobs/*.yaml

  # lava_dispatcher
  EXCLUDE="basics.yaml bbb-group-vland-alpha.yaml bbb-group-vland-beta.yaml bbb-ssh-guest.yaml hikey-console.yaml kvm-multinode-client.yaml kvm-multinode-server.yaml kvm-repeat.yaml test_action-1.yaml test_action-2.yaml"
  CMD="--exclude $(echo ${EXCLUDE} | sed "s# # --exclude #g#")"
  PYTHONPATH=. ./share/lava-schema.py job ${CMD} lava_dispatcher/tests/sample_jobs/*.yaml

  # lava_results_app
  PYTHONPATH=. ./share/lava-schema.py job lava_results_app/tests/*.yaml

  # lava_scheduler_app
  EXCLUDE="kvm-multinode-client.yaml kvm-multinode-server.yaml mustang-ssh-multinode.yaml qemu-ssh-guest-1.yaml qemu-ssh-guest-2.yaml qemu-ssh-parent.yaml"
  CMD="--exclude $(echo ${EXCLUDE} | sed "s# # --exclude #g#")"
  PYTHONPATH=. ./share/lava-schema.py job ${CMD} lava_scheduler_app/tests/sample_jobs/*.yaml
fi
