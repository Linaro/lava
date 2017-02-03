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

.. index:: prompt list, prompts, boot prompt list, boot prompts

.. _boot_prompts:

prompts
*******

After login (or directly from boot if no login is required), LAVA needs to
match the first prompt offered by the booted system. The full list of possible
prompts **must** be specified by the test writer in the test job submission.

Each prompt needs to be unique across the entire boot sequence, so typically
includes ``:`` and needs to be quoted. If the hostname of the device is
included in the prompt, this can be included in the ``prompt``:

.. code-block:: yaml

     - boot:
         prompts:
           - 'root@debian:~#'

When using the :term:`lxc` :term:`protocol`, the hostname element of the
prompt will vary::

.. code-block:: yaml

     - boot:
         prompts:
           - 'root@(.*):/#'

.. index:: boot connection

.. _boot_connection:

connection
**********

.. index:: boot method

.. _boot_method:

method
******

The boot ``method`` determines how the device is booted and which commands and
prompts are used to determine a successful boot.

.. index:: boot method fastboot

.. _boot_method_fastboot:

fastboot
========

The ``fastboot`` boot method takes no arguments or parameters.

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
    namespace: tlxc
    prompts:
    - 'root@(.*):/#'
    timeout:
      minutes: 5
    method: lxc

LXC Boot example
----------------

.. code-block:: yaml

 - boot:
    namespace: droid
    prompts:
    - 'root@(.*):/#'
    timeout:
      minutes: 5
    method: fastboot
    failure_retry: 2
    connection: lxc

  - boot:
      method: grub
      commands: ramdisk
      timeout:
          minutes: 50
      prompts:
       - 'root@genericarmv8:~#'
       - '/ #'

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
dispatcher, e.g. ``jessie``. Information on the available versions of ``qemu``
in Debian is available at http://tracker.debian.org/qemu

.. seealso:: :ref:`essential_components` and :ref:`qemu-iso boot method
   <boot_method_qemu_iso>`

.. index:: boot method qemu media

.. _boot_method_qemu_media:

media
-----

When booting a QEMU image file directly, the ``media`` needs to be specified as
``tmpfs``

.. code-block:: yaml

 - boot:
     method: qemu
     media: tmpfs

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
dispatcher, e.g. ``jessie``. Information on the available versions of ``qemu``
in Debian is available at http://tracker.debian.org/qemu

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

.. index:: boot method u-boot type

.. _boot_method_u_boot_type:

type
----

The type of boot, dependent on the U-Boot configuration. This needs to match
the supported boot types in the device configuration, e.g. it may change the
load addresses passed to U-Boot.

.. code-block:: yaml

 - boot:
   method: u-boot
   commands: nfs
   type: bootz
   prompts:
     - 'root@debian:~#'
