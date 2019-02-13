#!/bin/sh

set -e

if [ "$1" = "setup" ]
then
  apt-get -q update
  apt-get install --no-install-recommends --yes python3 python3-nose python3-voluptuous python3-yaml
else
  # documentation
  EXCLUDE="artifact-conversion-download.yaml bbb-2serial.yaml bbb-lxc-ssh-guest.yaml first-multinode-job.yaml hi6220-hikey-bl.yaml hikey-new-connection.yaml multiple-serial-ports-lxc.yaml mustang-ssh-guest.yaml namespace-connections-example1.yaml qemu-debian-installer.yaml second-multinode-job.yaml x15-recovery.yaml"
  CMD="--exclude $(echo ${EXCLUDE} | sed "s# # --exclude #g#")"
  PYTHONPATH=. ./share/lava-schema.py job ${CMD} doc/v2/examples/test-jobs/*.yaml

  # lava_dispatcher
  EXCLUDE="basics.yaml bbb-group-vland-alpha.yaml bbb-group-vland-beta.yaml bbb-ssh-guest.yaml download.yaml hi6220-recovery.yaml hikey-console.yaml kvm-multinode-client.yaml kvm-multinode-server.yaml kvm-repeat.yaml test_action-1.yaml test_action-2.yaml x15-recovery.yaml"
  CMD="--exclude $(echo ${EXCLUDE} | sed "s# # --exclude #g#")"
  PYTHONPATH=. ./share/lava-schema.py job ${CMD} lava_dispatcher/tests/sample_jobs/*.yaml

  # lava_results_app
  PYTHONPATH=. ./share/lava-schema.py job lava_results_app/tests/*.yaml

  # lava_scheduler_app
  EXCLUDE="bbb-bbb-vland-group.yaml bbb-cubie-vlan-group.yaml bbb-qemu-multinode.yaml hikey_multinode.yaml kvm-multinode.yaml kvm-multinode-client.yaml kvm-multinode-server.yaml lxc-multinode.yaml mustang-ssh-multinode.yaml nexus4_multinode.yaml panda-lxc-aep.yaml qemu-ssh-guest-1.yaml qemu-ssh-guest-2.yaml qemu-ssh-guest.yaml qemu-ssh-parent.yaml x86-vlan.yaml"
  CMD="--exclude $(echo ${EXCLUDE} | sed "s# # --exclude #g#")"
  PYTHONPATH=. ./share/lava-schema.py job ${CMD} lava_scheduler_app/tests/sample_jobs/*.yaml
fi
