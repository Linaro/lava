.. _boot_action:

Boot Action Reference
#####################

The ``boot`` action is used to cause the device to boot using the deployed
files. Depending on the parameters in the job definition, this could be by
executing a command on the dispatcher (for example
``/usr/bin/qemu-system-x86_64``) or by connecting to the device over serial or
ssh. Depending on the power state of the device and the device configuration,
the device may be powered up or reset to provoke the boot.

Every ``boot`` action **must** specify a method which is used to determine how
to boot the deployed files on the device. Depending on the method, other
parameters will be required.

Boot actions which result in a POSIX type login or shell must specify a list of
expected prompts which will be matched against the output to determine the
endpoint of the boot process. There are no default prompts, the test writer is
responsible for providing a list of all possible prompts.

.. seealso:: :ref:`boot_prompts`

Boot is a top level action that is part of the ``actions`` list. Here is an
example of full boot action from the test job definition:

.. code-block:: yaml

  - boot:
    namespace: target
    timeout:
      minutes: 15
    method: u-boot
    auto_login:
      login_prompt: 'am57xx-evm login:'
      username: root
      password_prompt: "Password:"
      password: "P@ssword-1"
      login_commands:
      - P@ssword-1
      - azertAZERT12345
      - azertAZERT12345
      - azertAZERT12345
    prompts:
    - 'Current password: '
    - 'New password: '
    - 'Retype new password: '
    - 'root@am57xx-evm:'
    transfer_overlay:
      download_command: unset http_proxy ; dhclient eth1 ; cd /tmp ; wget
      unpack_command: tar -C / -xzf
    commands:
    - setenv fdtfile am57xx-beagle-x15.dtb
    - setenv console ttyS2,115200n8
    - setenv mmcdev 1
    - setenv bootpart 1:9
    - run mmcboot
    ignore_kernel_messages: false

.. contents::
   :backlinks: top

.. index:: auto login, boot auto login

.. _boot_auto_login:

auto_login
**********

Some systems require the test job to specify a username and optionally a
password to login. These values must be specified in the test job submission.
If the system boots directly to a prompt without needing a login, the
``auto_login`` details can be omitted from the test job submission.

.. note:: The test job submission uses ``auto_login`` with underscore.

.. index:: auto login prompt, boot auto login prompt

.. _boot_auto_login_login_prompt:

login_prompt
============

The prompt to match when the system requires a login. This prompt needs to be
unique across the entire boot sequence, so typically includes ``:`` and should
be quoted. If the hostname of the device is included in the prompt, this can be
included in the ``login_prompt``:

.. code-block:: yaml

  - boot:
    auto_login:
      login_prompt: 'login:'
      username: root

.. note:: If login_prompt is not matched during boot LAVA will send control
   characters to the shell "thinking" that the kernel alert happened
   which may result in incorrect login but after it recognizes the
   ``Login incorrect`` message it will automatically try to log in
   using provided credentials.

.. index:: auto login username, boot auto login username

.. _boot_auto_login_username:

username
========

Whenever a ``login_prompt`` is specified, a ``username`` will also be required.
The username should either be ``root`` or a user with ``sudo`` access without
needing a password.

.. index:: auto login password prompt, boot auto login password prompt

.. _boot_auto_login_password_prompt:

password_prompt
===============

If the login requires a password as well as a username, the ``password_prompt``
must be specified:

.. code-block:: yaml

  - boot:
      auto_login:
        login_prompt: 'login:'
        username: root
        password_prompt: 'Password:'
        password: rootme

.. note:: If password_prompt is not matched during login or password is
   required but not provided LAVA will recognize the ``Login timed out``
   message, stop the execution of the job and log the error.

.. index:: auto login password, boot auto login password

.. _boot_auto_login_password:

password
========

Whenever a ``password_prompt`` is specified, a ``password`` will also be
required.

.. index:: auto login login commands, boot auto login login commands

.. _boot_auto_login_login_commands:

login_commands
==============

A list of arbitrary ``login_commands`` can be run after the initial login and
before setting the shell prompt. This is typically used to make a regular user
become root with su. For example:

.. code-block:: yaml

  - boot:
      auto_login:
        login_prompt: 'login:'
        username: user
        password_prompt: 'Password:'
        password: pass
        login_commands:
        - sudo su

.. note:: No interactive input such as a password can be provided with the list
   of ``login_commands``.

.. index:: prompt list, prompts - test jobs, boot prompt list, boot prompts

.. _boot_prompts:

prompts
*******

After login (or directly from boot if no login is required), LAVA needs to
match the first prompt offered by the booted system. The full list of possible
prompts **must** be specified by the test writer in the test job submission.

Each prompt needs to be unique across the entire boot sequence, so typically
includes ``:`` and needs to be quoted. If the hostname of the device is
included in the prompt, this can be included in the ``prompt``:

.. caution:: Take care with the specified prompts. Prompt strings which do not
   include enough characters can match early, resulting in a failed login.
   Prompt strings which include extraneous characters may fail to match for all
   test jobs. Avoid prompt elements which are user-specific, e.g. ``$``
   indicates an unprivileged user in some shells and ``#`` indicates the
   superuser. ``~`` indicates the home directory in some shells. In general,
   the prompt string should **include and usually end with** a colon ``:`` or a
   colon and space.

.. code-block:: yaml

  - boot:
      prompts:
      - 'root@debian:'

When using the :term:`LXC` :term:`protocol`, the hostname element of the
prompt will vary:

.. code-block:: yaml

  - boot:
      prompts:
      - 'root@(.*):'

When using a ramdisk, the prompt is likely to need to contain brackets which
will need to be escaped:

.. code-block:: yaml

  - boot:
      prompts:
      # escape the brackets to ensure that the prompt does not match
      # kernel debug lines which may mention initramfs
      - '\(initramfs\)'

.. index:: boot connection

.. _boot_connection:

connection
**********


.. index:: boot connection namespace

.. _boot_connection_namespace:

connection-namespace
********************

When using :term:`namespaces <namespace>` in job definition, you can reuse the
existing serial connection from another namespace via ``connection-namespace``
parameter. This applies only to *boot* action Example:

.. code-block:: yaml

   actions:
   - deploy:
       namespace: boot1
   # ...
   - boot:
       namespace: boot1
   # ...
   - test:
       namespace: boot1
   # ...
   - boot:
       namespace: boot2
       connection-namespace: boot1
   # ...
   - test:
       namespace: boot2
   # ...

.. index:: boot commands

.. _boot_commands:

commands
********

One of the key definitions in the :term:`device type` template for
each device is the list(s) of boot ``commands`` that the device
needs. These are sets of specific commands that will be run to boot
the device to start a test. The definitions will typically include
placeholders which LAVA will substitute with dynamic data as
necessary. For example, the full path to a tftp kernel image will be
expanded to include a job-specific temporary directory when a job is
started.

As a simple example from a U-Boot template:

.. code-block:: yaml

  - boot
      commands:
      - setenv autoload no
      - setenv initrd_high '0xffffffff'
      - setenv fdt_high '0xffffffff'
      - setenv loadkernel 'tftp {KERNEL_ADDR} {KERNEL}'
      - setenv loadinitrd 'tftp {RAMDISK_ADDR} {RAMDISK}; setenv initrd_size ${filesize}'
      - setenv loadfdt 'tftp {DTB_ADDR} {DTB}'
      - setenv bootcmd 'run loadkernel; run loadinitrd; run loadfdt; {BOOTX}'
      - boot

.. note:: In some cases, the boot commands list in the template may
   not provide **all** of the commands used; lines will also be
   generated from other data in the template. For example: the command
   ``setenv kernel_addr_r '0x82000000'`` might be generated from the
   load addresses which match the type of kernel being deployed.

When a test is started, the appropriate list of commands will be
selected. LAVA then substitutes the placeholders in the list to
generate a complete command list. The final parsed and expanded boot
commands used for a test are reported in the logs for that test job,
e.g.:

.. code-block:: none

 Parsed boot commands: setenv autoload no; setenv initrd_high '0xffffffff';
 setenv fdt_high '0xffffffff'; setenv kernel_addr_r '0x82000000'; setenv
 initrd_addr_r '0x83000000'; setenv fdt_addr_r '0x88000000'; setenv loadkernel
 'tftp ${kernel_addr_r} 158349/tftp-deploy-Fo78o6/vmlinuz'; setenv loadinitrd
 'tftp ${initrd_addr_r} 158349/tftp-deploy-Fo78o6/ramdisk.cpio.gz.uboot; setenv
 initrd_size ${filesize}'; setenv loadfdt 'tftp ${fdt_addr_r}
 158349/tftp-deploy-Fo78o6/am335x-boneblack.dtb'; setenv bootargs
 'console=ttyO0,115200n8 root=/dev/ram0  ip=dhcp'; setenv bootcmd 'dhcp; setenv
 serverip 10.3.1.1; run loadkernel; run loadinitrd; run loadfdt; bootz
 0x82000000 0x83000000 0x88000000'; boot

.. index:: boot commands - full

.. _full_boot_commands:

Specifying commands in full
===========================

During testing and development, it can sometimes be useful to use
a different set of boot commands instead of what is listed in the
jinja2 template for the device-type. This allows test writers to
change boot commands beyond the scope of existing overrides. To work
sensibly in the LAVA environment, these commands will still need to
**include the placeholders** such that temporary paths etc. can be
substituted in when the test job is started.

In this example (for an x86 test machine using iPXE), the commands
change the ``root`` argument to the kernel to boot from a SATA drive
which has been configured separately. (For example, by the admins or
by test writers from a hacking session.)

.. literalinclude:: examples/test-jobs/x86-sata-commands.yaml
   :language: yaml
   :start-after: # BOOT_ACTION
   :end-before: - boot

.. caution:: This support is recommended for use for corner cases that can't
   be fixed on the level of device type. Accordingly, LAVA will
   raise a warning each time this support is used. Abuse of this
   support can potentially stop devices from working in subsequent
   tests, or maybe even damage them permanently - be careful!

   If the commands are to be used regularly, `ask on the lava-users mailing
   list <https://lists.lavasoftware.org/mailman3/lists/lava-users.lists.lavasoftware.org/>`_ requesting
   that a label is created in the templates for this set of commands.
   Alternatively, you can request a new override to make the existing labels
   more flexible. You can also propose a patch yourself.

.. index:: kernel command line, extra kernel arguments, boot commands - kernel

.. _appending_kernel_command_line:

Appending to the kernel command line
====================================

A test job may require extra kernel command line options to enable or disable
particular functionality. The :term:`job context` can be used to append
strings to the kernel command line:

.. code-block:: jinja

  context:
    extra_kernel_args: vsyscall=native

:term:`job context` is a top level element of LAVA job definition. It is not
a part of `boot` section.

Values need to be separated by whitespace and will be added to the command
line with a prefix of a single space and a suffix of a single space.

The possible values which can be used are determined solely by the support
available within the kernel provided to the :term:`DUT`.

Depending on the boot method, it may also be possible to add specific options,
for example to append values to the NFS options using ``extra_nfsroot_args``:

.. code-block:: jinja

  context:
    extra_nfsroot_args: ,rsize=4096 nfsrootdebug

.. note:: ``extra_nfsroot_args`` are appended directly to the existing NFS
   flags ``nfsroot={NFS_SERVER_IP}:{NFSROOTFS},tcp,hard,intr`` so if the
   appended string contains an extra flag, this must be put first and the
   string must start with a comma. Other options can then be separated by a
   space or can use ``extra_kernel_args``. The example above would result in
   the string ``nfsroot={NFS_SERVER_IP}:{NFSROOTFS},tcp,hard,intr,rsize=4096
   nfsrootdebug``.

.. seealso:: `Kernel documentation for NFSROOT
   <https://www.kernel.org/doc/Documentation/filesystems/nfs/nfsroot.txt>`_ ,
   :ref:`override_variables_context` and :ref:`override_support`

.. index:: boot failure_message

.. _boot_failure_message:

failure_message
***************

Some devices deploy the boot commands inside the boot image which is
then deployed using ``fastboot``. To boot the device after deployment,
LAVA does not interrupt the bootloader (e.g. U-Boot or Grub) and lets
the configured boot arguments control the boot.

In some situations, a test kernel can fail and cause the device to
reset to the bootloader. The presence of configured boot commands leads
to the device booting into an environment which is not necessarily the
one required by the test writer and the failure of the test kernel can
then be hidden. To handle this issue, a ``failure_message`` can be
specified to match a string output by the bootloader after the device
has reset. The test job will then fail after the reset and tracking the
kernel errors.

.. seealso:: :ref:`boot_method_fastboot`

.. index:: boot method

.. _boot_method:


ignore_kernel_messages
**********************

Some test scenarios assume deliberately forcing kernel panic. This might
interfere with LAVA failure detection. To prevent LAVA from stopping the
job in such circumstance ``ignore_kernel_messages`` should be set to ``true``.
LAVA won't be able to detect any other "legitimate" kernel crashes in such
situation. Default value is false.

.. index:: boot method

.. _boot_ignore_kernel_messages:

method
******

The boot ``method`` determines how the device is booted and which commands and
prompts are used to determine a successful boot.

.. index:: boot method bootloader

.. _boot_method_bootloader:

bootloader
==========

The ``bootloader`` method is used to power-on the :term:`DUT`, interrupt the
bootloader, and wait for the bootloader prompt.

In order to interrupt the bootloader, the bootloader type should be specified
in the ``bootloader`` parameter:

.. code-block:: yaml

  - boot
      method: bootloader
      bootloader: u-boot
      commands: []
      prompts: ['=>']

.. note:: the bootloader method type should match a boot method supported by
          the give device-type.
          For example ``fastboot``, ``minimal``, ``pyocd``, ``u-boot``, ...

The ``commands`` parameter is required but can be kept empty.
If some commands should be sent to the bootloader before the end of the action,
give the list in the ``commands`` parameter.

.. index:: boot method cmsis-dap

.. _boot_method_cmsis_dap:

cmsis-dap
=========

The ``cmsis-dap`` boot method takes no arguments or parameters.

.. code-block:: yaml

  - boot
      method: cmsis-dap
      timeout:
        minutes: 10

.. index:: boot method depthcharge

.. _boot_method_depthcharge:

depthcharge
===========

The ``depthcharge`` boot method takes no arguments or parameters.  It is used
to boot the downloaded kernel image, and optionally a device tree and a
ramdisk.  The files are converted into an FIT (U-Boot Flattened Image Tree
format) image suitable to be booted by Coreboot using the Depthcharge payload,
typically used by Chrome OS devices.  It also creates a separate text file with
the kernel command line which is made available to the :term:`DUT` over TFTP
alongside the FIT image.

.. code-block:: yaml

  - boot:
      method: depthcharge
      commands: nfs

.. note:: Unlike some other boot methods such as ``u-boot``, the
          ``depthcharge`` boot method always expects the kernel image to be in
          the same standard format (zImage for arm, Image for arm64...).  So
          there should not be any ``type`` attribute for the kernel image in
          the ``deploy`` section as shown in the example below:

.. code-block:: yaml

  - deploy:
      kernel:
        url: http://storage.kernelci.org/mainline/master/v4.18-1283-g10f3e23f07cb/arm/multi_v7_defconfig/zImage
      ramdisk:
        url: http://storage.kernelci.org/images/rootfs/debian/stretchtests/20180627.0/armhf/rootfs.cpio.gz
        compression: gz

.. index:: boot method docker

.. _boot_method_docker:

docker
======

Boot a docker image already deployed by a :ref:`deploy to docker action <deploy_to_docker>`.

.. code-block:: yaml

  - boot:
     method: docker
     command: bash
     prompts:
     - 'root@lava:'
     timeout:
       minutes: 2

command
-------

The command to run when starting the docker container.

.. index:: boot method fastboot

.. _boot_method_fastboot:

fastboot
========

The ``fastboot`` boot method takes no arguments or parameters.

.. code-block:: yaml

  - boot:
      method: fastboot
      namespace: droid
      prompts:
        - 'root@(.*):/#'
        - 'hikey:/'
      timeout:
        minutes: 15

.. note:: Since all fastboot :term:`DUT` depend on LXC to run jobs, it is
          mandatory to have the namespace specified.

.. index:: boot method fastboot commands

.. _boot_method_fastboot_commands:

fastboot boot commands
----------------------

Some test jobs may need to add a ``fastboot`` command prior to boot, for
example to specify whether the ``_a`` or ``_b`` partitions are to be
active.

If the test job specifies the ``images`` labels as ``boot_a`` instead
of ``boot``, then a fastboot boot command will be required to make sure
that the device boots from ``boot_a`` instead of ``boot_b`` (which may
contain an old deployment from a previous test job or may contain nothing
at all).

.. code-block:: yaml

  - boot:
      method: fastboot
      commands:
      - --set-active=a

.. index:: boot method fastboot-nfs

.. _boot_method_fastboot_nfs:

fastboot-nfs
============

The ``fastboot-nfs`` boot is a method that allow you specify a ``nfs`` rootfs in
a Android boot image via LXC image build and boot using ``fastboot`` boot method.

The job needs a require set of 3 primary actions:

- Deploy rootfs over NFS
- Download Kernel and DTB to LXC
- Create Android boot image with NFS details provided by NFS_{ROOTFS,SERVER_IP}
  environment variables

.. literalinclude:: examples/test-jobs/fastboot-nfs.yaml
    :language: yaml

.. seealso:: :ref:`boot method fastboot <boot_method_fastboot>`.

.. index:: boot method fvp

.. _boot_method_fvp:

fvp
===

The ``fvp`` boot method allows you to run Fixed Virtual Platforms.

.. code-block:: yaml

  - boot:
      method: fvp
      prompts:
        - 'root@(.*):/#'
      image: /path/to/FVP_Binary
      licence_variable: ARMLMD_LICENSE_FILE=foo
      arguments:
        - "-C board.virtioblockdevice.image_path={DISK}"
        ...
      docker:
        name: "fvp_foundation:11.8"
        local: true
      timeout:
        minutes: 5

This boot method will launch the ``image`` file
(already present in the docker image provided)
with the ``arguments`` as parameters,
and the ``licence_variable`` set as an environment variable.

You can use ``{IMAGE_NAME}`` which will be replaced with the path to the
image with the same key under ``images`` in the previous ``fvp`` deploy stage.
``{ARTIFACT_DIR}`` can also be used for the directory where all images are deployed.

.. note:: Previous to running an ``fvp`` boot, you should run an ``fvp`` deploy.

.. note:: The docker image must have the fastmodel in it and must have the required tools, such as ``telnet``.

.. index:: boot method grub

.. _boot_method_grub:

grub
====

The ``grub`` boot method takes no arguments or parameters.

.. code-block:: yaml

  - boot:
      method: grub
      commands: ramdisk

.. index:: boot method grub-efi

.. _boot_method_grub_efi:

grub-efi
========

The ``grub-efi`` boot method takes no arguments or parameters. **However**, in
most cases, starting Grub from UEFI requires using the
:ref:`boot_method_uefi_menu` as well.

.. literalinclude:: examples/test-jobs/mustang-grub-efi.yaml
   :language: yaml
   :start-after: # BOOT_ACTION
   :end-before: # TEST_ACTION

Download or view the complete example:
`examples/test-jobs/mustang-grub-efi.yaml
<examples/test-jobs/mustang-grub-efi.yaml>`_

.. note:: Admins can refer to the ``mustang-grub-efi.jinja2`` template for an
   example of how to make selections from a UEFI menu to load Grub. See
   :ref:`device_type_templates`.

.. index:: boot method ipxe

.. _boot_method_ipxe:

ipxe
====

The ``ipxe`` boot method takes no arguments or parameters.

.. code-block:: yaml

  - boot:
      method: ipxe
      commands: ramdisk
      prompts:
      - 'root@debian:~#'
      - '/ #'

.. index:: boot method lxc

.. _boot_method_lxc:

lxc
===

.. seealso:: :ref:`lxc_protocol_reference`

.. code-block:: yaml

  - boot:
      method: lxc
      prompts:
      - 'root@(.*):/#'
      timeout:
        minutes: 5

.. index:: boot method openocd

.. _boot_method_openocd:

openocd
=======

The ``openocd`` boot method takes no arguments or parameters.

The method works by passing through the command line options for the
openocd command. It downloads and runs the executable specified by ``binary``
in the job definition. It also allows an openocd script file to be downloaded
from the location specified by ``openocd_script`` in the job definition, if
a custom script file should be used instead of the one specified by the
device type.

``board_selection_cmd`` can be used in the device-type to specify a command to
pass the board id/serial number to OpenOCD. See OpenOCD documentation for
details on the command to set the serial number for the interface your
device type is using.

.. code-block:: yaml

  - boot:
      method: openocd
      timeout:
        minutes: 3

.. index:: boot method pyocd

.. _boot_method_pyocd:


.. index:: boot method minimal

.. _boot_method_minimal:

minimal
=======

The ``minimal`` method is used to power-on the :term:`DUT` and to let the
:term:`DUT` boot without any interaction.

.. code-block:: yaml

  - boot
      method: minimal
      prompts:
      - 'root@debian:~#'
      - '/ #'

.. note:: auto-login and transfer_overlay are both supported for this method.

By default LAVA will reset the board power when executing this action. Users
can skip this step by adding ``reset: false``. This can be useful when testing
bootloader in interactive tests and then booting to the OS.

.. code-block:: yaml

  - boot
      method: minimal
      reset: false

Pre power/os command defined in device dictionary can be executed by adding
``pre_power_command: true`` or ``pre_os_command: true``. These commands can be
useful to activate or deactivate external hardware before applying power.

.. code-block:: yaml

  - boot
      method: minimal
      pre_power_command: true

.. index:: boot method musca

.. _boot_method_musca:

musca
=====

The ``musca`` method is used to boot musca devices. Currently supported are the `musca a
<https://developer.arm.com/products/system-design/development-boards/iot-test-chips-and-boards/musca-a-test-chip-board>`__,
`musca b
<https://developer.arm.com/tools-and-software/development-boards/iot-test-chips-and-boards/musca-b-test-chip-board>`__,
and `musca s1
<https://developer.arm.com/tools-and-software/development-boards/iot-test-chips-and-boards/musca-s1-test-chip-board>`__.
Unlike the ``minimal`` boot, the board has to be powered on before the serial will be available
as the board is powered by the USB that provides the serial connection also.
Therefore, the board is powered on then connection to the serial is made.
Optionally, ``prompts`` can be used to check for serial output before continuing.

.. code-block:: yaml

  - boot:
      method: musca

.. note:: No shell is expected and no boot string is checked. All checking should be done with test monitors.

.. note:: Some initial setup steps are required to ensure that the Musca device boots when it is powered on.
          Check `here <https://github.com/ARMmbed/DAPLink/blob/master/docs/MSD_COMMANDS.md>`__ for details
          on how to setup the board to auto-boot when it is programmed or turned on.
          Ensure ``DETAILS.TXT`` on the MSD shows "Auto Reset" and "Auto Power" are activated.

pyocd
=====

The ``pyocd`` boot method takes no arguments or parameters.

.. code-block:: yaml

  - boot:
      method: pyocd
      timeout:
        minutes: 10

The ``pyocd`` boot method requires configuration on the device type level.
Following configuration options are supported:

* ``command`` - executable command to invoke
* ``options`` - list of options to pass to the executable
* ``connect_before_flash`` - if ``true``, connect to device before running
  pyocd flash command, otherwise after the command (default is ``false``)

.. index:: boot method jlink

.. _boot_method_jlink:

jlink
=====

The ``jlink`` boot method takes no arguments or parameters.

.. code-block:: yaml

  - boot:
      method: jlink
      timeout:
        minutes: 10

.. index:: boot method console

.. _boot_method_console:

new_connection
==============

The ``new_connection`` boot method takes no arguments or
parameters. This method can be used to switch to a new connection,
allowing a test to isolate test and kernel messages (if the kernel and
the device are both appropriately configured).

.. include:: examples/test-jobs/hikey-new-connection.yaml
     :code: yaml
     :start-after: # boot uart0 block
     :end-before: # boot hikey block

.. note:: The ``new_connection`` boot method **must** use a different
   :term:`namespace` to all other actions in the test job. The test
   shell(s) must pass this namespace label as the
   ``connection-namespace``.

.. seealso:: :ref:`boot_connection_namespace`

.. include:: examples/test-jobs/hikey-new-connection.yaml
     :code: yaml
     :start-after: # test isolation block
     :end-before: # test lxc block

.. index:: boot method qemu

.. _boot_method_qemu:

qemu
====

The ``qemu`` method is used to boot the downloaded ``image`` from the
deployment action using QEMU. This runs the QEMU command line on the
dispatcher. Only certain elements of the command line are available for
modification using the :term:`job context`. The available values can vary
depending on local admin configuration. For example, many admins restrict the
available memory of each QEMU device, so the ``memory`` option in the job
context may be ignored.

.. code-block:: yaml

    context:
      arch: aarch64
      memory: 2048
      # comment out or change to user if the dispatcher does not support bridging.
      # netdevice: tap
      extra_options:
      - -smp
      - 1
      - -global
      - virtio-blk-device.scsi=off
      - -device virtio-scsi-device,id=scsi
      - --append "console=ttyAMA0 root=/dev/vda rw"

The version of ``qemu`` installed on the dispatcher is a choice made by the
admin. Generally, this will be the same as the version of ``qemu`` available
from Debian in the same suite as the rest of the packages installed on the
dispatcher, e.g. ``buster``. Information on the available versions of ``qemu``
in Debian is available at https://tracker.debian.org/pkg/qemu

.. seealso:: :ref:`essential_components` and :ref:`qemu-iso boot method
   <boot_method_qemu_iso>`

.. index:: boot method qemu media tmpfs

.. _boot_method_qemu_media_tmpfs:

media
-----

When booting a QEMU image file directly, the ``media`` needs to be specified as
``tmpfs``.

.. code-block:: yaml

  - boot:
      method: qemu
      media: tmpfs

.. index:: boot method qemu-nfs

.. _boot_method_qemu_nfs:

qemu-nfs
========

The ``qemu-nfs`` method is used to boot a downloaded ``kernel`` with a root
filesystem deployed on the worker. Only certain elements of the command line
are available for modification using the :term:`job context`. The available
values can vary depending on local admin configuration. For example, many
admins restrict the available memory of each QEMU device, so the ``memory``
option in the job context may be ignored.

The version of ``qemu`` installed on the dispatcher is a choice made by the
admin. Generally, this will be the same as the version of ``qemu`` available
from Debian in the same suite as the rest of the packages installed on the
dispatcher, e.g. ``buster``. Information on the available versions of ``qemu``
in Debian is available at https://tracker.debian.org/pkg/qemu

QEMU can be used with an NFS using the ``qemu-nfs`` method and the ``nfs``
media:

.. literalinclude:: examples/test-jobs/qemu-nfs.yaml
    :language: yaml
    :start-after: # BOOT_BLOCK
    :end-before: # TEST_BLOCK

.. seealso:: :ref:`boot method qemu <boot_method_qemu>`.

When using ``qemu-nfs``, the hostname element of the prompt will vary according
to the worker running QEMU:

.. literalinclude:: examples/test-jobs/qemu-nfs.yaml
    :language: yaml
    :start-after: # BOOT_BLOCK
    :end-before: # TEST_BLOCK

.. index:: boot method qemu media nfs

.. _boot_method_qemu_media_nfs:

media
-----

When booting a QEMU image using NFS, the ``media`` needs to be specified as
``nfs``.

.. literalinclude:: examples/test-jobs/qemu-nfs.yaml
    :language: yaml
    :start-after: # BOOT_BLOCK
    :end-before: # TEST_BLOCK

.. index:: boot method qemu-iso

.. _boot_method_qemu_iso:

qemu-iso
========

The ``qemu-iso`` method is used to boot the downloaded installer from the
deployment action using QEMU. This runs the QEMU command line on the
dispatcher. Only certain elements of the command line are available for
modification using the :term:`job context`.

The version of ``qemu`` installed on the dispatcher is a choice made by the
admin. Generally, this will be the same as the version of ``qemu`` available
from Debian in the same suite as the rest of the packages installed on the
dispatcher, e.g. ``buster``. Information on the available versions of ``qemu``
in Debian is available at https://tracker.debian.org/pkg/qemu

.. seealso:: :ref:`essential_components` and :ref:`boot method qemu
   <boot_method_qemu>`

.. code-block:: yaml

  - boot:
      method: qemu-iso
      media: img
      timeout:
        minutes: 20
      connection: serial
      auto_login:
        login_prompt: 'login:'
        username: root
        password_prompt: 'Password:'
        password: root
      prompts:
      - 'root@debian:~#'

.. index:: boot method qemu-iso media

.. _boot_method_qemu_iso_media:

media
-----

When booting an installer using QEMU, the ``media`` needs to be specified as
``img``

.. code-block:: yaml

  - boot:
      method: qemu-iso
      media: img

.. index:: transfer overlay

.. _boot_transfer_overlay:

transfer_overlay
================

An overlay is a tarball of scripts which run the LAVA Test Shell for
the test job. The tarball also includes the git clones of the
repositories specified in the test job submission and the LAVA helper
scripts. Normally, this overlay is integrated into the test job
automatically. In some situations, for example when using a command
list to specify an alternative rootfs, it is necessary to transfer the
overlay from the worker to the device using commands within the booted
system prior to starting to run the test shell.

Some overlay tarballs can be quite large. The LAVA TestShell helpers are tiny
shell scripts but the git repositories cloned for your test shell definitions
can become large over time. Additionally, if your test shell definition clones
the git repo of source code, those clones will also appear in the overlay
tarball.

.. note:: The situations where ``transfer_overlay`` is useful tend to
   also require restricting the test job to specific devices of a
   particular device type. This needs to be arranged with the lab
   admins who can create suitable :term:`device tags <device tag>`
   which will need to be specified in all test job definitions.

.. seealso:: :ref:`secondary_media` which is more flexible but slower.

The overlay is transferred before any test shell operations can occur,
so the method of transferring and then unpacking the overlay **must**
work without any further setup of the rootfs. All dependencies must be
pre-installed and all configuration must be in place (possibly using a
hacking session). This includes the **network** configuration - the
worker offers several network services to download the overlay and LAVA
can populate the URL but the device **must** automatically configure the
networking immediately upon boot and the network **must** work
straight away.

The job could specify ``transfer_method`` to choose how to transfer overlay:

* ``transfer_method: http``

  This will transfer overlay through apache host service.

  .. code-block:: yaml

    - boot:
        transfer_overlay:
          transfer_method: http
          download_command: wget -S --progress=dot:giga
          unpack_command: tar -C / -xzf

  .. note:: The ``-C /`` command to tar is **essential** or the test shell will
     not be able to start. The overlay will use ``gzip`` compression, so pass
     the ``z`` option to ``tar``.

* ``transfer_method: nfs``

  This will transfer overlay through nfs server service:

  .. code-block:: yaml

    - boot:
        transfer_overlay:
          transfer_method: nfs
          download_command: mount -t nfs -o nolock
          unpack_command: cp -rf

.. note:: ``http`` will be used if ``transfer_method`` omitted.

Deployment differences
----------------------

The ``-S --progress=dot:giga`` options to wget in the example above optimize
the output for serial console logging to avoid wasting line upon line of
progress percentage dots. If the system uses ``busybox``, these options may not
be supported by the version of ``wget`` on the device.

Some systems do not store the current time between boots. The ``--warning
no-timestamp`` option is a useful addition for ``tar`` for those systems but
note that ``busybox tar`` does not support this option.

The ``download_command`` and the ``unpack_command`` can include one or more
shell commands. However, as with the test shell definitions, avoid using
redirects (``>`` or ``>>``) or other complex shell syntax. This example changes
to ``/tmp`` to ensure there is enough writeable space for the download.

.. code-block:: yaml

  - boot:
      transfer_overlay:
        download_command: cd /tmp ; wget
        unpack_command: tar -C / -xzf

.. index:: boot method u-boot

.. _boot_method_u_boot:

u-boot
======

The ``u-boot`` method boots the downloaded files using U-Boot commands.

.. index:: boot method u-boot commands

.. _boot_method_u_boot_commands:

commands
--------

The predefined set of U-Boot commands into which the location of the downloaded
files can be substituted (along with details like the SERVERIP and NFS
location, where relevant). See the device configuration for the complete set of
commands.

Certain elements of the command line are available for modification using the
:term:`job context`. The available values vary by :term:`device type`.

Example
-------------

NXP Layerscape platforms supports booting from Alternate Bank, keeping Main
Bank safe.
If you want to boot the board from Alternate Bank, you can do it by adding
context variable "uboot_altbank: true".
By default its value is set to "false"

.. code-block:: yaml

 context:
   uboot_altbank: true

.. _boot_method_uefi_menu:

uefi-menu
=========

The ``uefi-menu`` method selects a pre-defined menu in the UEFI configuration
for the device. In most cases, this is used to execute a different bootloader.
For example, a ``fastboot`` device can execute ``fastboot`` from a menu item or
a device could execute an ``PXE`` menu item to download and execute Grub.

.. caution:: Although it *is possible* to create new menu entries in UEFI each
   time a test job starts, this has proven to be unreliable on both of the
   device types tested so far. If the build of UEFI is not able to download a
   bootloader using ``PXE``, then experiment with creating a UEFI menu item
   which is able to execute a local file and have a build of Grub on local
   storage. Build the grub binary using ``grub-mkstandalone`` to ensure that
   all modules are available.

UEFI menus will renumber themselves each time a new item is added or removed,
so LAVA must be able to match the description of the menu item and then
identify the correct selector to be able to send the correct character to
execute that menu option. This means that the admins must create the same menu
structures on each device of the same device type and correlate the text
content of the menu with the :ref:`jinja2 templates
<developing_device_type_templates>`.

To use ``uefi-menu``, the device must offer a menu from which items can be
selected using a standard regular expression: ``'a-zA-Z0-9\s\:'``, for example:

.. code-block:: shell

  [1] bootloader
  [2] boot from eMMC
  [3] Boot Manager
  [4] Reboot

The :term:`device type` template would need to specify the ``separator``
(whitespace in the example) as well as how to identify the **item** matching
the requested selector:

.. code-block:: yaml

  - boot:
      method: uefi-menu
      parameters:
        item_markup:
        - "["
        - "]"
        item_class: '0-9'
        separator: ' '

This allows LAVA to match a menu item matching ``\[[0-9]\] ['a-zA-Z0-9\s\:']``
and select the correct selector when the menu item string matches one (and only
one) line output by the UEFI menu. In this example, the selector must be a
digit.

The template must then also specify which menu item to select, according to
the ``commands`` set in the testjob:

.. code-block:: yaml

  - boot:
      method: uefi-menu
      commands: fastboot

The template would then need:

.. code-block:: yaml

  - boot:
      method: uefi-menu
      parameters:
        fastboot:
        - select:
            items:
            - 'boot from eMMC'

.. _boot_method_uuu_menu:

uuu
===

Integration of NXP ``uuu`` the flashing tool utility for i.mx platform.

See the complete documentation of `uuu / mfgtools` on GitHub https://github.com/NXPmicro/mfgtools/wiki

Installation
------------

``uuu`` is not provided as a dependency within LAVA, you need to install it manually over all Slaves.

You can get the latest release here : https://github.com/NXPmicro/mfgtools/releases/latest

.. code-block:: bash

  # INSTALLATION SCRIPT
  wget https://github.com/NXPmicro/mfgtools/releases/download/<UUU_VERSION>/uuu
  chmod a+x uuu
  mv uuu /bin/uuu

Device configuration
--------------------

To use ``uuu`` the :term:`device` template must specify two variables :

.. code-block:: jinja

  {# One of the variable above #}
  {% set uuu_usb_otg_path = '2:143' %}
  {% set uuu_usb_otg_path_command = ['echo', '2:143'] %}

  {% set uuu_corrupt_boot_media_command = ['mmc dev 1', 'mmc erase 0 0x400'] %}

* ``uuu_corrupt_boot_media_command`` : a list of commands to execute on the platform within u-boot to corrupt the primary boot media.
    On the next reboot, serial download protocol must be available on the platform to flash future images using uuu.

* ``uuu_usb_otg_path`` : can be obtained using the command ``uuu -lsusb``. Multiple paths can be provided by using array declaration in device template.

.. code-block:: jinja

  {# Multiple otg path example #}
  {% set uuu_usb_otg_path = ['1:143', '2:143'] %}
  {% set uuu_usb_otg_path_command = ['echo', '-ne', '1:143\n2:143'] %}

  {% set uuu_corrupt_boot_media_command = ['mmc dev 1', 'mmc erase 0 0x400'] %}


* ``uuu_usb_otg_path_command`` : Allow to customize uuu_otg_path at the worker level, avoiding jinja2 device template modification on the server.
    Your command must print a well formatted usb path accepted by uuu on each line with no new-line at end of output.

.. code-block:: shell

  $ uuu -lsusb
  uuu (Universal Update Utility) for nxp imx chips -- libuuu_1.3.102-1-gddf2649
  Connected Known USB Devices
      Path	 Chip	 Pro	 Vid	 Pid	 BcdVersion
      ==================================================
      2:143	 MX8MQ	 SDP:	 0x1FC9	0x012B	 0x0001

If you want to use ``uuu`` within docker image, you could specify next variable:

.. code-block:: jinja

  {% set uuu_docker_image = 'atline/uuu:1.3.191' %}

* ``uuu_docker_image`` : This is a docker image which installed an uuu binary in it already.

.. note:: A docker image specified in job.yaml could also override this value in device configuration like next:

    .. code-block:: yaml

      - boot:
          docker:
            image: atline/uuu:1.3.191
          method: uuu
          commands:
            - uuu : -b sd {boot}
          timeout:
            minutes: 5

If you also want to enable ``remote uuu`` feature, in which situation your device not directly linked to lava dispatcher, you could specify another variable:

.. code-block:: jinja

  {% set uuu_remote_options = '--tlsverify --tlscacert=/labScripts/remote_cert/ca.pem --tlscert=/labScripts/remote_cert/cert.pem --tlskey=/labScripts/remote_cert/key.pem -H 10.192.244.5:2376' %}

* ``uuu_remote_options`` : This let docker client remotely operate an uuu docker container on a remote machine.

You could follow https://docs.docker.com/engine/install/linux-postinstall/#configure-where-the-docker-daemon-listens-for-connections to configure remote docker support.

You could follow https://docs.docker.com/engine/security/https/ to protect the docker daemon socket if you are also care about security.

.. note:: The minimal docker version to run uuu is 19.03. This is due to a bug in earlier docker versions. See https://github.com/moby/moby/pull/37665.

* ``uuu_power_off_before_corrupt_boot_media`` : This enables a device power off before corrupt boot media.

  There is a situation that uboot continues to restart, it will affect uboot interrupt when corrupt boot media. Next configure could power down the device before uboot interrupt, with which you have option to remove the interference:

.. code-block:: jinja

  {% set uuu_power_off_before_corrupt_boot_media = true %}

Usage
-----

Following the same syntax of ``uuu`` tool, commands are specified using a pair <Protocol, Command>.
``commands`` field is then a list of dictionary with only one pair of <Protocol, Command>.

A special Protocol named ``uuu`` is defined to used build-int scripts.

.. note:: Images passed to uuu commands must be first deployed using the ``uuu`` deploy action if used with overlay.

    Using the following :

    .. code-block:: yaml

      - deploy:
          to: uuu
          images:
            boot:
              url: https://.../imx-boot-sd.bin-flash
            system:
              url: https://../imx-image-multimedia.rootfs.wic
              apply-overlay: true
              root_partition: 1

    Both ``boot`` and ``system`` keyword are stored as images name that you can reference within ``uuu`` boot method commands.

    .. warning::

        ``boot`` image is required by uuu boot method to perform USB serial download availability check.

    The USB serial availability check consist to try to write in memory a valid bootloader image using this command ``uuu {boot}``.
    If the command does not terminate within 10 seconds, primary boot-media will be erased using ``uuu_corrupt_boot_media_command``.

Using built-in scripts
^^^^^^^^^^^^^^^^^^^^^^

Example definition :

.. code-block:: yaml

  - boot:
      method: uuu
      commands:
      - uuu: -b sd_all {boot} {system}

Non-exhaustive list of available built-in scripts :

.. code-block:: yaml

  - uuu: -b emmc {boot}                 # Write bootloader to emmc
  - uuu: -b emmc_all {boot} {system}    # Write bootloader & rootfs to emmc
  - uuu: -b sd {boot}                   # Write bootloader to sd card
  - uuu: -b sd_all {boot} {system}      # Write bootloader & rootfs to sd card


Using commands
^^^^^^^^^^^^^^
Example code :

.. code-block:: yaml

  - boot:
      method: uuu
      commands :
      - SDPS: boot -f {boot}
      - FB: continue
      - FB: done

BCU Integration
^^^^^^^^^^^^^^^
Most recent i.MX boards (imx8dxl, imx8mp, imx8ulp, imx93 as of july-2022) support BCU, a remote control utility.
BCU allows changing the board's boot configuration (mainly SD card, eMMC or USB Serial Download Protocol) through a serial interface.

**bcu**

Integration of NXP ``bcu`` the board remote control utility for the boards/platform that support remote control.

See the project readme of `bcu` on GitHub : https://github.com/NXPmicro/bcu#readme

**Installation**

``bcu`` is not provided as a dependency within LAVA, you need to install it manually over all workers.

You can get the latest release here : https://github.com/NXPmicro/bcu/releases/latest


**Enabling bcu capability on compatible device types**

To use ``bcu`` the :term:`device type` template must specify variable :

.. code-block:: jinja

  {% set bcu_board_name = 'imx8dxlevk' %}

* ``bcu_board_name`` : can be obtained using the command ``bcu lsboard`` :

.. code-block:: shell

   $ bcu lsboard
   version bcu_1.1.45-0-g0b267ba

   list of supported board model:

	imx8dxlevk
	imx8dxlevkc1
	imx8dxl_ddr3_evk
	imx8mpevkpwra0
	imx8mpevkpwra1
	imx8mpevk
	imx8mpddr4
	imx8ulpevk
	imx8ulpevkb2
	imx8ulpevk9
	done

**Device configuration**

To use ``bcu`` the :term:`device` template must specify variable :

.. code-block:: jinja

  {# One of the variable below #}
  {% set bcu_board_id = '2-1.3' %}
  {% set bcu_board_id_command = ['echo', '2-1.3'] %}

* ``bcu_board_id`` : can be obtained using the command ``bcu lsftdi`` :
* ``bcu_board_id_command`` : Allows customization of bcu_board_id at the worker level. It avoids device template modification in server side.
    Your command must print on a single line a well formatted board id accepted by bcu.

.. code-block:: shell

  $ bcu lsftdi
  version bcu_1.1.45-0-g0b267ba
  number of boards connected through FTDI device found: 1
  board[0] location_id=2-1.3
  done

**Usage**

Following the same syntax of ``bcu`` tool, in the boot action the ``method`` should be specified as ``uuu`` and then
commands are specified in the ``commands`` field.

Example definition :

.. code-block:: yaml

  - boot:
      method: uuu
      commands:
           - bcu: reset usb
           - uuu: -b emmc {boot}
           - bcu: set_boot_mode emmc
      timeout:
        minutes: 20

.. note::
    Serial availability check and bootloader corruption actions are skipped when:
        - First item in ``commands`` block is ``bcu: reset usb``
    Or 
        - ``commands`` block contain ``bcu`` commands only

    This behavior is useful to recover bricked devices or to use bcu as a standalone action.

Non-exhaustive list of available bcu commands :

.. code-block:: yaml

  - reset BOOTMODE_NAME                 # Reset the board and then boots from mentioned BOOTMODE_NAME.
                                        # Replace BOOTMODE_NAME with different options like emmc,sd,
                                        # usb which can be obtained from command bcu lsbootmode.
                                        # Replace the BOOTMODE_NAME with anyone of the mentioned.
  - lsftdi                              # List all the boards connected by ftdi device
  - lsboard                             # List all supported board models
  - get_boot_mode                       # Displays the boot mode set by BCU
