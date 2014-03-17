.. index:: Virtual Machine groups

.. _vm_groups:

Virtual Machine Groups
######################

Virtual machine (VM) groups are a special type of multinode test job,
where dynamically allocated virtual machines participate.

To submit a VM group test job, you need:

- a device that supports virtualization (at the time of writing Arndale
  and Versatile Express boards are known to have it).

- system images for the host system and for the VM's'.

A VM group test job consists of a ``vm_group`` attribute, specifying
the host machine and a list of VM's that will spawned on the host.

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
        "vms": [
          {
            "device_type": "kvm",
            "role": "server"
          },
          {
            "device_type": "kvm",
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

.. _nested_vms:

The ``vms`` section contains an array of VM descriptions, which
will be used to instantiate the VMs on the host device. Each item in
that array must have the following mandatory attributes:

- ``device_type``: the type of VM that should be spawned. For now the only
  supported value is ``kvm``, but it will be updated in the future to
  support ``xen`` as well.

- ``role``: like in regular multinode jobs, this indicates a label that
  will be associated with the given VM's and can be used See
  :ref:`multinode` for more information.

- ``image``: which image that should be used to boot the virtual machine.


There are additional parameters that can be used, but are optional:

- ``count``: number of VM's of that given ``role`` to spawn. The default
  value is 1.

- ``launch_with``: a list of commands to be used in the host to spawn
  the VM. The last command in the list has to be the call that attaches
  to the VM console in the current terminal.

- ``shell_prompt``: the shell prompt of the VM, used by LAVA to identify
  that the VM finished booting.
