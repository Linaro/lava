.. _available_actions:

List of available dispatcher actions
####################################

Dispatcher actions are of two main types:

* General purpose actions for systems based on OpenEmbedded, Debian or Ubuntu
* :ref:`android_specific_actions`

These actions are routinely tested as part of the LAVA functional tests
and results are available in this :term:`bundle stream` page:

https://staging.validation.linaro.org/dashboard/streams/anonymous/lava-functional-tests/bundles/

Individual tests are listed using the ``job_name`` in the linked JSON. To
see all results just for one job, enter the ``job_name`` in the Search
box of the bundle stream page.

General purpose actions
***********************

These actions are commonly used with test images based on OpenEmbedded,
Debian or Ubuntu.

.. index:: deploy_linaro_image

.. _deploy_linaro_image:

Deploying an image to a device
==============================

Use the ``deploy_linaro_image`` action or the equivalent ``deploy_image``
action to deploy a test image onto a target. Typically this is the first
command that runs in any LAVA test job::

 {
    "actions": [
        {
            "command": "deploy_linaro_image",
            "parameters": {
                "image": "http://images.validation.linaro.org/kvm-debian-wheezy.img.gz"
            }
        }
    ]
 }

Example functional test: **kvm-single-node**:

http://git.linaro.org/lava-team/lava-functional-tests.git/blob/HEAD:/single-node-job/neil.williams/kvm-single-node.json

Available parameters
--------------------

* :term:`hwpack`: Linaro style hardware pack. Usually contains a boot
  loader(s), kernel, dtb, ramdisk. The parameter accepts http, local
  and scp urls::

   http://myserver.com/hw-pack.tar.gz
   file:///home/user/hw-pack.tar.gz
   scp://username@myserver.com:/home/user/hw-pack.tar.gz

* :term:`rootfs`: A tarball for the root file system.
  The parameter accepts http, local and scp urls::

   http://myserver.com/rootfs.tar.gz
   file:///home/user/rootfs.tar.gz
   scp://username@myserver.com:/home/user/rootfs.tar.gz

* image: A prebuilt image that includes both a hwpack and a rootfs or
  the equivalent binaries. The parameter accepts http, local and scp
  urls::

   http://myserver.com/prebuilt.img.gz
   file:///home/user/prebuilt.img.gz
   scp://username@myserver.com:/home/user/prebuilt.img.gz

* rootfstype: This is the filesystem type for the rootfs.
  (i.e. ext2, ext3, ext4...). The parameter accepts
  any string and is optional.

* bootloadertype: The type of bootloader a target is using.
  The parameter accepts any string and is optional.
  The default is ``u_boot``.

* ``login_prompt``: A string that will match a login prompt.
  The parameter accepts any string and is optional.

* ``username``: A string that represents a username. This will be sent
  to the login prompt. The parameter accepts any string and is optional.

* ``password_prompt``: A string that will match a password prompt.
  The parameter accepts any string and is optional.

* ``password``: A string that represents a password. This will be sent
  to the password prompt. The parameter accepts any string and is optional.

* ``login_commands``: An array of strings that will be sent to the target after login.
  The parameter accepts any strings and is optional.

* :term:`role`: Determines which devices in a MultiNode group will
  use this action. The parameter accepts any string, the string must
  exactly match one of the roles specified in the :term:`device group`.

* customize: A optional parameter for customizing the prebuilt image or
  the image made by a hwpack and a rootfs before testing.
  The formation of this parameter is::

   "customize": {
       "<source file url>": ["<destination image path 1>", "<destination image path 2>"],
       "<source image path>": ["<destination image path 1>", "delete"]
       }

  The <source file url> accepts http, local and scp urls::

   http://myserver.com/myfile
   file:///home/user/myfile
   scp://username@myserver.com:/home/user/myfile

  The <source image path> accepts the path of the file/dir in the image,
  the definition of the path is <partition>:<path>, for example::

   boot:/EFI/BOOT/
   rootfs:/home/user/myfile

  The <destination image path> is a array, that means we can copy
  the source file/dir to multidestination. And all the destination paths
  must be the "image path"(<partition>:<path>), it could be a non-existent
  file or dir.

  If the <destination image path> is dir name(end up with '/'),
  the source file/dir will be copied to that dir.
  If the <destination image path> is file name, the source file will
  be copied and renamed to that path.

  If you want to delete the file/dir in the original image, you can add
  a "delete" in the destination path array. It only affects the item
  which uses <source image path> as the source.

  Please check the example below.

::

 {
    "actions": [
        {
            "command": "deploy_linaro_image",
            "parameters": {
                "rootfs": "http://<server>/<hw_pack>.tar.gz",
                "hwpack": "http://<server>/<rootfs>.tar.gz",
                "bootloadertype": "uefi",
                "customize": {
                    "http://myserver.com/myfile": ["boot:/"],
                    "boot:/img.axf": ["rootfs:/tekkamanninja/", "delete"]
                }
            }
        }
    ]
 }

Example functional test: **model-express-group-multinode**:

http://git.linaro.org/lava-team/lava-functional-tests.git/blob/HEAD:/multi-node-job/neil.williams/fastmodel-vexpress-group.json

Example functional test: **model-customize-image-singlenode**:

https://git.linaro.org/people/fu.wei/lava-test-job-definition_example.git/blob/refs/heads/master:/LAVA/file_injection_in_deploy_linaro_image.json

.. index:: deploy_linaro_kernel

.. _deploy_linaro_kernel:

Deploying a Linaro kernel
=========================

Use ``deploy_linaro_kernel`` to deploy a kernel and other bits. To use this
deployment action the target's boot loader must be capable of network booting.::

   {
      "command": "deploy_linaro_kernel",
      "parameters": {
        "kernel": "http://community.validation.linaro.org/images/beagle/zImage",
        "ramdisk": "http://community.validation.linaro.org/images/beagle/uInitrd",
        "dtb": "http://community.validation.linaro.org/images/beagle/omap3-beagle-xm.dtb",
        "rootfs": "http://community.validation.linaro.org/images/qemu/beagle-nano.img.gz"
    }

Example functional test: **bootloader-lava-test-shell-multinode**:

http://git.linaro.org/lava-team/lava-functional-tests.git/blob/HEAD:/multi-node-job/bootloader/bootloader-lava-test-shell-multinode.json

**qemu-kernel-boot**:

http://git.linaro.org/lava-team/lava-functional-tests.git/blob/HEAD:/single-node-job/qemu/qemu-arm-kernel-boot.json

Available parameters
--------------------

* ``kernel``: A kernel image. The :term:`boot tag` for this parameter is `{KERNEL}`.
  The parameter accepts any string and is required.

* ``ramdisk``: A ramdisk image. The :term:`boot tag` for this parameter is `{RAMDISK}`.
  The parameter accepts any string and is optional.

* ``dtb``: A flattened device tree blob. The :term:`boot tag` for this parameter is `{DTB}`.
  The parameter accepts any string and is optional.

* :term:`rootfs`: A root filesystem image. This parameter assumes that
  the target's boot loader can deliver the image to a storage device. The :term:`boot tag`
  for this parameter is `{ROOTFS}`. The parameter accepts any string and is optional.

* ``nfsrootfs``: A tarball for the root file system. LAVA will extract
  this tarball and create an NFS mount point dynamically. The :term:`boot tag` for this
  parameter is `{NFSROOTFS}`. The parameter accepts any string and is optional.

* ``bootloader``: A boot loader image. This parameter assumes that
  the target's boot loader can deliver the boot loader image to a storage device.
  The :term:`boot tag` for this parameter is `{BOOTLOADER}`. The parameter accepts
  any string and is optional.

* ``firmware``: A firmware image. This parameter assumes that
  the target's boot loader can deliver the firmware image to a storage device.
  The :term:`boot tag` for this parameter is `{FIRMWARE}`. The parameter accepts
  any string and is optional.

* ``rootfstype``: This is the filesystem type for the rootfs.
  (i.e. ext2, ext3, ext4...). The parameter accepts
  any string and is optional.

* ``bootloadertype``: The type of bootloader a target is using.
  The parameter accepts any string and is optional.
  The default is ``u_boot``.

* ``target_type``: The type of distribution a target is using. This is useful
  when using a ``nfsrootfs`` or a ramdisk that have distribution specific dependencies.
  The parameter accepts any of the following strings:
  ``ubuntu`` ``oe`` ``fedora`` or ``android``. The default is ``oe``.

* ``login_prompt``: A string that will match a login prompt.
  The parameter accepts any string and is optional.

* ``username``: A string that represents a username. This will be sent
  to the login prompt. The parameter accepts any string and is optional.

* ``password_prompt``: A string that will match a password prompt.
  The parameter accepts any string and is optional.

* ``password``: A string that represents a password. This will be sent
  to the password prompt. The parameter accepts any string and is optional.

* ``login_commands``: An array of strings that will be sent to the target after login.
  The parameter accepts any strings and is optional.

* :term:`role`: Determines which devices in a MultiNode group will
  use this action. The parameter accepts any string, the string must
  exactly match one of the roles specified in the :term:`device group`.

.. index:: boot_linaro_image

.. _boot_linaro_image:

Booting a test image
====================

Use the ``boot_linaro_image`` action or the direct equivalent ``boot_image``
action to boot a test image that was deployed using the ``deploy_linaro_image``
or ``deploy_image`` actions::

 {
    "actions": [
        {
            "command": "deploy_linaro_image",
            "parameters": {
                "image": "http://images.validation.linaro.org/kvm-debian-wheezy.img.gz"
            }
        },
        {
            "command": "boot_linaro_image"
        }
    ]
 }


.. note:: It is not necessary to use ``boot_linaro_image`` or ``boot_image``
          if the next action in the test is ``lava_test_shell``.

Example functional test: **kvm-kernel-boot**:

http://git.linaro.org/lava-team/lava-functional-tests.git/blob/HEAD:/single-node-job/qemu/kvm-kernel-boot.json

.. index:: interactive boot commands

.. _interactive_boot_cmds:

Interactive boot commands
-------------------------

::

 {
    "actions": [
        {
            "command": "boot_linaro_image",
            "parameters": {
                "boot_cmds": [
                    "setenv autoload no",
                    "setenv pxefile_addr_r '0x50000000'",
                    "setenv kernel_addr_r '0x80200000'",
                    "setenv initrd_addr_r '0x81000000'",
                    "setenv fdt_addr_r '0x815f0000'",
                    "setenv initrd_high '0xffffffff'",
                    "setenv fdt_high '0xffffffff'",
                    "setenv loadkernel 'tftp ${kernel_addr_r} {KERNEL}'",
                    "setenv loadinitrd 'tftp ${initrd_addr_r} {RAMDISK}; setenv initrd_size ${filesize}'",
                    "setenv loadfdt 'tftp ${fdt_addr_r} {DTB}'",
                    "setenv bootargs 'console=ttyO0,115200n8 root=/dev/ram0 ip=:::::eth0:dhcp'",
                    "setenv bootcmd 'dhcp; setenv serverip {SERVER_IP}; run loadkernel; run loadinitrd; run loadfdt; bootz ${kernel_addr_r} ${initrd_addr_r} ${fdt_addr_r}'",
                    "boot"
                    ]
            }
        }
    ]
 }

Example functional test: **bootloader-lava-test-shell-multinode**:

http://git.linaro.org/lava-team/lava-functional-tests.git/blob/HEAD:/multi-node-job/bootloader/bootloader-lava-test-shell-multinode.json

Available parameters
--------------------

* ``interactive_boot_cmds``: boolean, defaults to false.
* ``options``: Optional array of strings which will be passed as boot commands.
* :term:`role`: Determines which devices in a MultiNode group will
  use this action. The parameter accepts any string, the string must
  exactly match one of the roles specified in the :term:`device group`.

.. _running_lava_test_shell:

Running tests in the test image
===============================

Use ``lava_test_shell`` to boot the deployed image and invoke a set of
tests defined in a YAML file::

 {
    "actions": [
        {
            "command": "deploy_linaro_image",
            "parameters": {
                "image": "http://images.validation.linaro.org/kvm-debian-wheezy.img.gz"
            }
        },
        {
            "command": "lava_test_shell",
            "parameters": {
                "testdef_repos": [
                    {
                        "git-repo": "http://git.linaro.org/git/people/neil.williams/temp-functional-tests.git",
                        "testdef": "multinode/multinode03.yaml"
                    }
                ]
            }
        }
    ]
 }

Example functional test: **kvm-group-multinode**:

http://git.linaro.org/lava-team/lava-functional-tests.git/blob/HEAD:/multi-node-job/neil.williams/kvm-only-group.json

To run multiple tests without a reboot in between each test run, extra ``testdef_repos`` can be listed::

 {
    "actions": [
        {
            "command": "lava_test_shell",
            "parameters": {
                "testdef_repos": [
                    {
                        "git-repo": "git://git.linaro.org/qa/test-definitions.git",
                        "testdef": "ubuntu/smoke-tests-basic.yaml"
                    },
                    {
                        "git-repo": "http://git.linaro.org/git/lava-team/lava-functional-tests.git",
                        "testdef": "lava-test-shell/multi-node/multinode02.yaml"
                    }
                ],
                "timeout": 900
            }
        }
    ]
 }

Example functional test: **model-express-group-multinode**:

http://git.linaro.org/lava-team/lava-functional-tests.git/blob/HEAD:/multi-node-job/neil.williams/fastmodel-vexpress-group.json

To run multiple tests with a reboot in between each test run, add extra ``lava_test_shell``
actions::

 {
    "actions": [
        {
            "command": "lava_test_shell",
            "parameters": {
                "testdef_repos": [
                    {
                        "git-repo": "git: //git.linaro.org/qa/test-definitions.git",
                        "testdef": "ubuntu/smoke-tests-basic.yaml"
                    }
                ],
                "timeout": 900
            }
        },
        {
            "command": "lava_test_shell",
            "parameters": {
                "testdef_repos": [
                    {
                        "git-repo": "http://git.linaro.org/lava-team/lava-functional-tests.git",
                        "testdef": "lava-test-shell/multi-node/multinode02.yaml"
                    }
                ],
                "timeout": 900
            }
        }
    ]
 }

Example functional test: **bootloader-lava-test-shell-multinode**:

http://git.linaro.org/lava-team/lava-functional-tests.git/blob/HEAD:/multi-node-job/bootloader/bootloader-lava-test-shell-multinode.json

Example functional test with skipping installation steps:  **kvm**:

https://git.linaro.org/qa/test-definitions.git/blob/HEAD:/ubuntu/kvm.yaml

To run tests with skipping all installation steps, i.e. neither additional packages nor hackbench will be installed::

 {
    "actions": [
        {
            "command": "lava_test_shell",
            "parameters": {
                "testdef_repos": [
                    {
                        "git-repo": "git://git.linaro.org/qa/test-definitions.git",
                        "testdef": "ubuntu/kvm.yaml"
                    }
                ],
                "skip_install": "all",
                "timeout": 900
            }
        }
    ]
 }

To run tests with skipping only installation of a hackbench::

 {
    "actions": [
        {
            "command": "lava_test_shell",
            "parameters": {
                "testdef_repos": [
                    {
                        "git-repo": "git://git.linaro.org/qa/test-definitions.git",
                        "testdef": "ubuntu/kvm.yaml"
                    }
                ],
                "skip_install": "steps",
                "timeout": 900
            }
        }
    ]
 }

To run tests with skipping installation of packages, but with insatallation of a hackbench::

 {
    "actions": [
        {
            "command": "lava_test_shell",
            "parameters": {
                "testdef_repos": [
                    {
                        "git-repo": "git://git.linaro.org/qa/test-definitions.git",
                        "testdef": "ubuntu/kvm.yaml"
                    }
                ],
                "skip_install": "deps",
                "timeout": 900
            }
        }
    ]
 }

.. _lava_test_shell_parameters:

Available parameters
--------------------

* ``testdef_repos``: See :ref:`test_repos`.
* ``testdef_urls``: URL of the test definition when not using a version
  control repository.
* ``timeout``: Allows you set a timeout for the action. Any integer
  value, optional.
* :term:`role`: Determines which devices in a MultiNode group will
  use this action. The parameter accepts any string, the string must
  exactly match one of the roles specified in the :term:`device group`.
* ``skip_install``: This parameter allows to skip particular install step
  in the YAML test definition. The parameter accepts any string and is optional.
  Available options known by the dispatcher are:

  ``all``: skip all installation steps

  ``deps``: skip installation of packages dependencies, :ref:`handling_dependencies`

  ``repos``: skip cloning of repositories, :ref:`adding_repositories`

  ``steps``: skip running installation steps, :ref:`install_steps`

  The default is None, i.e. nothing is skipped.

.. _android_specific_actions:

Android specific actions
************************

.. _deploy_linaro_android_image:

Deploying a Linaro Android image
================================

Use ``deploy_linaro_android_image`` to deploy an Android test image
onto a target. Typically this is the first command that runs in any
LAVA job to test Android::

 {
    "actions": [
        {
            "command": "deploy_linaro_android_image",
            "parameters": {
                "boot": "http://<server>/boot.bz2",
                "data": "http://http://<server>/userdata.bz2",
                "system": "http://http://<server>/system.bz2"
            }
        }
    ]
 }

Example functional test: **master-lava-android-test-multinode**:

http://git.linaro.org/lava-team/lava-functional-tests.git/blob/HEAD:/multi-node-job/master/master-lava-android-test-multinode.json

Available parameters
--------------------

* ``boot``: Android ``boot.img`` or ``boot.bz2``. Typically this is
  a kernel image and ramdisk. The parameter accepts http, local and
  scp urls::

   http://myserver.com/boot.img
   file:///home/user/boot.img
   scp://username@myserver.com:/home/user/boot.img

* ``system``: Android ``system.img`` or ``system.bz2``. Typically
  this is the system partition. The parameter accepts http, local and
  scp urls::

   http://myserver.com/system.img
   file:///home/user/system.img
   scp://username@myserver.com:/home/user/system.img

* ``data``: Android ``userdata.img`` or ``userdata.bz2``. Typically
  this is the data partition. The parameter accepts http, local and
  scp urls::

   http://myserver.com/userdata.img
   file:///home/user/userdata.img
   scp://username@myserver.com:/home/user/userdata.img

* :term:`rootfstype`: This is the filesystem type for the :term:`rootfs`.
  (i.e. ext2, ext3, ext4...). The parameter accepts any string and is
  optional. The default is ``ext4``.
* :term:`role`: Determines which devices in a MultiNode group will
  use this action. The parameter accepts any string, the string must
  exactly match one of the roles specified in the :term:`device group`.

.. _boot_linaro_android_image:

Booting a Linaro Android image
==============================

Use ``boot_linaro_android_image`` to boot an Android test image
that was deployed using the ``deploy_linaro_android_image`` action::

 {
    "actions": [
        {
            "command": "deploy_linaro_android_image",
            "parameters": {
                "boot": "http: //<server>/boot.bz2",
                "data": "http: //http: //<server>/userdata.bz2",
                "system": "http: //http: //<server>/system.bz2"
            }
        },
        {
            "command": "boot_linaro_android_image"
        }
    ]
 }

Example functional test: **master-job-defined-boot-cmds-android**:

http://git.linaro.org/lava-team/lava-functional-tests.git/blob/HEAD:/single-node-job/master/master-job-defined-boot-cmds-android.json

.. _lava_android_test_install:

Installing Android tests in a deployed Android image
====================================================

Use ``lava_android_test_install`` to invoke the installation of a
lava-android-test test::

 {
    "command": "lava_android_test_install",
    "parameters": {
        "tests": [
            "monkey"
        ]
    }
 }

Example functional test: **master-lava-android-test-multinode**:

http://git.linaro.org/lava-team/lava-functional-tests.git/blob/HEAD:/multi-node-job/master/master-lava-android-test-multinode.json

Running Android tests in a deployed Android image
==================================================

.. _lava_android_test_run:

Use ``lava_android_test_run`` to invoke the execution of a
lava-android-test test::

 {
    "command": "lava_android_test_run",
    "parameters": {
        "test_name": "monkey"
    }
 }

Example functional test: **master-lava-android-test-multinode**:

http://git.linaro.org/lava-team/lava-functional-tests.git/blob/HEAD:/multi-node-job/master/master-lava-android-test-multinode.json

Available parameters
--------------------

* ``test_name``: The name of the test you want to invoke from
  lava-android-test. Any string is accepted. If an unknown test is
  specified it will cause an error.
* ``option``: Allows you to add additional command line parameters to
  lava-android-test install. Any string is accepted. If an unknown
  option is specified it will cause an error.
* ``timeout``: Allows you set a timeout for the action. Any integer
  value, optional.
* :term:`role`: Determines which devices in a MultiNode group will
  use this action. The parameter accepts any string, the string must
  exactly match one of the roles specified in the :term:`device group`.

Example functional test: **master-lava-android-test-multinode**:

http://git.linaro.org/lava-team/lava-functional-tests.git/blob/HEAD:/multi-node-job/master/master-lava-android-test-multinode.json

.. _lava_android_test_shell:

Invoking a LAVA Android test shell
==================================

Use ``lava_android_test_shell`` to invoke the execution of a
lava-test-shell test(s)::

 {
    "command": "lava_test_shell",
    "parameters": {
        "testdef_urls": [
            "http://myserver.com/my_test.yaml"
        ],
        "timeout": 180
    }
 }

Example functional test: **master-boot-options-boot-cmds-lava-test-shell-android**:

http://git.linaro.org/lava-team/lava-functional-tests.git/blob/HEAD:/single-node-job/master/master-boot-options-lava-test-shell-android.json:
