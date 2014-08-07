.. index:: Virtual Machine groups

.. _vm_groups:

Virtual Machine Groups
######################

Virtual machine (VM) groups are a special type of multinode test job,
where dynamically allocated virtual machines participate in a single
test job.

To submit a VM group test job, you need:

- a device that supports virtualization (at the time of writing Arndale
  and Versatile Express boards are known to have it).

- system images for the host system and for the VM's'. The host system
  image needs to include ``openssh-server``.

- the instance configured to support a ``kvm-arm`` :term:`device type`.

A VM group test job consists of a ``vm_group`` attribute, specifying
the host machine and a list of VM's that will spawned on the host.

See :ref:`writing_multinode` for more information on VMGroup test
definitions. Virtual Machine groups are an extension of MultiNode, so
the definition which would be resubmitted as a new VMGroup job will
be the VMGroup Definition.

Example job definition::

    {
      "timeout": 18000,
      "job_name": "vm-groups basic test case",
      "logging_level": "DEBUG",
      "vm_group": {
        "host": {
          "device_type": "arndale",
          "role": "host"
        },
        "auto_start_vms": true,
        "vms": [
          {
            "device_type": "kvm-arm",
            "role": "server"
          },
          {
            "device_type": "kvm-arm",
            "role": "client"
          }
        ]
      },
      "actions": [
        {
          "command": "deploy_linaro_image",
          "parameters": {
            "image": "file:///path/to/host.img",
            "role": "host"
          }
        },
        {
          "command": "deploy_linaro_image",
          "parameters": {
            "image": "file:///path/to/host.img",
            "role": "client"
          }
        },
        {
          "command": "deploy_linaro_image",
          "parameters": {
            "image": "file:///path/to/host.img",
            "role": "server"
          }
        },
        {
          "command": "lava_test_shell",
          "parameters": {
            "testdef_urls": [
              "file:///path/to/mytestdef.yaml"
            ]
          }
        }
      ]
    }

The ``host`` section declares the device that will be used as host for
the VMs. Note the following requirements for system images used for host
devices:

- openssh server must come installed, with ``sftp`` support.

- ``qemu-system`` must be installed (or at least the specific flavor
  that needs to be tested e.g. ``qemu-system-arm``)

The ``auto_start_vms`` attribute is optional, and can be set to
``false`` to make LAVA *not* start the VM's as soon as the host is
booted (the default value is ``true``). In that case, signaling LAVA
when the VM's should be started becomes a responsibility of the test
writer: one has to include a call to ``lava-start-vms`` at a point in
the test code where the VMs should be started, and another call to
``lava-wait-vms`` before the test code finishes to make sure that the
host will wait until the VM's are done before allowing a reboot of the
host. Example::

    #!/bin/sh

    # work work work ... (e.g. build qemu from source)
    lava-start-vms
    # run tests on the host ...
    # done, now wait for VM's to finish
    lava-wait-for-vms


The ``vms`` section contains an array of VM descriptions, which
will be used to instantiate the VMs on the host device. Each item in
that array must have the following mandatory attributes:

- ``device_type``: the type of VM that should be spawned. For now the only
  supported value is ``kvm``, but it will be updated in the future to
  support ``xen`` as well.

- ``role``: like in regular multinode jobs, this indicates a label that
  will be associated with the given VM's and can be used See
  :ref:`multinode` for more information. Always make sure you are clear
  on what ``role`` is assigned to each ``lava_test_shell`` command.
  See :ref:`writing_vm_group_tests`.

- ``image``: which image that should be used to boot the virtual
  machine. Note that you can also use the ``deploy_linaro_kernel``
  action and use separate kernel/dtb/rootfs images.

There are additional parameters that can be used, but are optional:

- ``count``: number of VM's of that given ``role`` to spawn. The default
  value is 1.

- ``launch_with``: a list of commands to be used in the host to spawn
  the VM. The last command in the list has to be the call that attaches
  to the VM console in the current terminal.

- ``shell_prompt``: the shell prompt of the VM, used by LAVA to identify
  that the VM finished booting.

.. _writing_vm_group_tests:

Writing tests for virtual machine groups
========================================

The VMs will run on the host device and LAVA supports running
:ref:`lava_test_shell` on the host and inside each VM.

* The host test shell will start and run its tests and then wait until
  all of the VM test shells have finished.
* If a second test shell command is given for the host, this test shell
  will only operate once all of the VMs have closed, allowing for tests
  to be run to check for a successful clean up on the host device.
* If the host device needs to run tests from multiple repositories,
  see :ref:`tests_and_reboots`.
* See :ref:`writing_multinode` for more on how to communicate between
  the VM and the host using the :ref:`multinode_api`.
* It is not possible to list one test shell for multiple roles, only
  for a single role or all roles. If you have multiple tests to run on
  different VMs, consider whether it is better to have multiple roles,
  each with a ``lava_test_shell`` command or to combine the tests into
  one role and use the :ref:`multinode_api` or other features to
  distinguish one VM from another.
