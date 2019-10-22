.. index:: device integration - u-boot

.. _integrating_uboot:

U-Boot
######

.. important:: Make sure you have read :ref:`adding_new_device_types`
   first.

U-Boot is a very common sight on embedded devices. It is a very capable piece
of Open Source software that supports a diverse range of devices out of the
box, and it is easily configurable and modifiable to add support for new
devices too. Comprehensive documentation is available on the `U-Boot website
<https://www.denx.de/wiki/U-Boot>`_.

If your new device includes U-Boot then this can be a useful beginning.
However, the build of U-Boot on the device may potentially hinder integration
due to the wide range of configuration options and behavioral changes
available inside a patched U-Boot build.

.. seealso:: :ref:`uboot_vendor_builds`

Generally, the more components of U-Boot that are disabled or removed from a
vendor build, the harder it will be to integrate. If you are able to fully
script a U-Boot process from interrupting the bootloader to booting a kernel of
your own choice, this will greatly assist in integrating the device into LAVA.

To start the device integration of a device using U-Boot, you must at
least have a complete list of all the commands which are necessary to
interrupt U-Boot and manually boot the device.

.. _uboot_essentials:

Common U-Boot support
*********************

The following elements are common to all U-Boot integration projects. Some
information may need to be obtained from the default vendor configuration as
shipped on the device. interrupt U-Boot and take a copy of all the settings
before you start integration work. Some elements need to be considered during
the development or updating of the build of U-Boot on the device itself.
Sometimes there might be limitations in the hardware itself. Most devices which
can use mainline U-Boot can be integrated into LAVA. Where mainline support is
available, it is recommended to replace the vendor-supplied version of U-Boot
with a mainline build.

* Make sure that the U-Boot environment can be modified and that changes are
  persistent across reboots.

* Read and understand how ``base-uboot.jinja2`` operates to follow how the
  various values will be used to create the U-Boot boot commands. Not all of
  the logic in the ``base-uboot.jinja2`` template is covered in this section.

* Create a unit test and ensure that the final rendered device configuration
  matches the needs of the device.

.. seealso:: :ref:`developing_device_type_templates`,
   :ref:`developer_jinja2_support` and :ref:`testing_new_devicetype_templates`

.. _uboot_configuration:

Configuration
=============

Ensure that the U-Boot build supports a string which can be used to interrupt
U-Boot and that once interrupted, the prompt is set to a usable string like
``=>`` or ``uboot#`` etc. Make sure that the configuration supports TFTP using
commands sent over the serial port. The timeout for interrupting the boot
process **must** be configurable. Typically, the timeout should be at least 5
seconds in the default configuration. There is no need to configure a working
automatic boot once the timeout expires. Whilst having a default boot is useful
during development, it can be simpler in automation to simply drop to the
bootloader prompt if the bootloader could not be interrupted successfully
within the timeout. This avoids wasting time watching the device boot into a
system which is not the system intended by the test writer. (The default boot
would likely fail to support the correct ``auto-login`` or, worse, could allow
login and then fail to run any tests as the overlay will not have been deployed
to that system. Either option is confusing when trying to debug why the test
job failed as the actual error is close to the top of the LAVA test logs, not
at the end after all of the boot messages have been sent.)

.. _uboot_prompts:

Prompts
=======

Two prompts are **required** in the device configuration:

.. code-block:: jinja

  interrupt_prompt: {{ interrupt_prompt|default('Hit any key to stop autoboot') }}
  bootloader_prompt: {{ bootloader_prompt|default('=>') }}

The ``interrupt_prompt`` is seen first as the device boots and then waits for
the timeout before attempting to boot automatically.

The ``bootloader_prompt`` is seen after the bootloader has been interrupted and
after each command is sent to the bootloader.

Many U-Boot configurations use the same prompt strings as the defaults
in ``base-uboot.jinja2``, as shown above.

.. _uboot_interrupting:

Interrupting U-Boot
===================

The default behavior when interrupting U-Boot is to send a single newline
character. This behavior is controlled with the following variables:

.. code-block:: jinja

  interrupt_char: "{{ interrupt_char | default('') }}"
  interrupt-newline: {{ uboot_interrupt_newline | default(True) }}

If U-Boot requires a special character, set ``interrupt_char`` accordingly. For
example, set to SPACE by setting the following in the device template.

.. code-block:: jinja

  {% set uboot_interrupt_character = ' ' %}

If ``interrupt_char`` is used, LAVA will still send it followed by a newline.
To prevent the newline from being sent, disable ``uboot_interrupt_newline``.

.. code-block:: jinja

  {% set uboot_interrupt_newline = False %}

.. _uboot_interrupting_troubleshooting:

Troubleshooting Interrupting U-Boot
-----------------------------------

An extra newline during U-Boot interruption can cause LAVA to send U-Boot
commands before the previous command completes. The error message ``*** ERROR:
`serverip' not set`` may be seen, due to the delay of the ``dhcp`` command,
which preceded the ``setenv serverip`` command, causing the latter to be sent
too soon. If U-Boot interrupt does not need a newline to be sent, set
uboot_interrupt_newline to False in the device template.

.. _uboot_load_addresses:

Load addresses
==============

U-Boot typically requires the load addresses to be specified in the commands
used to load and execute the downloaded kernel, ramdisk and :term:`DTB`. The
initial load addresses can be obtained from the device in ``uEnv.txt`` or in
the saved environment of the default U-Boot configuration (via ``printenv``).
The load addresses may need changes later to support larger ramdisks or
kernels. Some U-Boot devices use different load addresses according to the
kernel to be booted, so each address can be specified separately or mapped to
an existing value.

.. code-block:: jinja

    {% set bootm_kernel_addr = '0x40007000' %}
    {% set bootm_ramdisk_addr = '0x45000000' %}
    {% set bootm_dtb_addr = '0x41f00000' %}
    {% set bootz_kernel_addr = bootm_kernel_addr %}
    {% set bootz_ramdisk_addr = bootm_ramdisk_addr %}
    {% set bootz_dtb_addr = bootm_dtb_addr %}

.. _uboot_requirements:

Required configuration
======================

At a minimum, any new U-Boot device requires the following pieces of
configuration:

* **console device** - There seems to be no standard or default here, so
  **every** request needs to specify the argument to pass to ``console=``
  on the kernel command line, including baud rate.

* **load addresses** - Kernel, ramdisk and DTB load addresses.

* **mkimage arch** - the architecture value to pass to mkimage when preparing
  modified uImage or uboot headers.

* **MAC address** - if the MAC address is not pre-configured as a guaranteed
  unique address, a way of setting a fixed and unique MAC address must be
  provided.

* **boot methods** - ``booti``, ``bootz`` and ``bootm`` - which ones are
  supported on this device?

* **prompts** - What is the configured U-Boot prompt on the required build of
  U-Boot for the device. Has the autoboot prompt been modified and if so, what
  is the autoboot prompt?

.. _uboot_magic:

Booting the kernel
==================

When this goes wrong, the infamous ``Bad Linux magic`` error can be seen.
Retrieve the available boot methods from the existing U-Boot configuration,
typically one or more of ``bootz``, ``booti`` or ``bootm``.

If ``booti_kernel_addr`` is set, ``image`` parameters will be set for the
ramdisk and the DTB.

If ``bootm_kernel_addr`` is set, ``uimage`` parameters will be set for the
ramdisk and the DTB.

If ``bootz_kernel_addr`` is set, ``zimage`` parameters will be set for the
ramdisk and the DTB.

.. _uboot_bootargs:

U-Boot bootargs
===============

U-Boot uses the ``bootargs`` ("boot arguments") variable to specify the command
line when booting a Linux kernel. This can be critical in determining whether a
device boots at all or whether particular hardware is available in the booted
system. Equally, some bootargs settings can be entirely cosmetic and simply add
(or silence) messages during the boot process. Experiment with your board to
work out which bootargs are mandatory for all boots, which are useful as
defaults but which can be omitted for some test jobs and which are entirely
optional.

Mandatory bootargs need to be put into the template as hard-coded
strings. Useful bootargs can be set as the default value of
``{{base_kernel_args}}``. Optional bootargs can be left as comments
for test writers to supply via the :term:`job context` and then added
to the bootargs using ``{{extra_kernel_args}}``.

.. seealso:: :ref:`appending_kernel_command_line`

.. _uboot_mkimage:

Using mkimage
=============

U-Boot typically requires use of the ``mkimage`` binary in various ways. Most
commonly, a test job which only boots a ramdisk needs to have the LAVA overlay
added to the ramdisk.
Many devices require a U-Boot header on the ramdisk. The device configuration
controls how to add a new U-Boot header when LAVA needs to modify the
downloaded ramdisk (to add modules or a test shell overlay). The device
configuration deploy parameters use the default ``add-header: u-boot`` setting
from `base-uboot.jinja2`.

``mkimage`` creates a different header for ``arm`` than for ``arm64``. The
``uboot_mkimage_arch`` value will need to be set according to the requirements
of the device.

.. note:: Most ARMv7 devices will use ``arm`` as the architecture and most
   ARMv8 devices will use ``arm64``, but this is not always the case. For
   example, the APM Mustang is an arm64 device but the U-Boot build on the
   Mustang pre-dates arm64 support in mainline U-Boot. It uses ``{% set
   uboot_mkimage_arch = 'arm' %}``

.. _uboot_vendor_builds:

Vendor builds
=============

Not all devices have mainline U-Boot support and the configurability of the
U-Boot source code means that some vendor-supplied builds of U-Boot may behave
very differently to those found on other U-Boot devices. Do not assume that
options and commands in existing U-Boot devices will always have any equivalent
in a vendor build of U-Boot.

.. _uboot_network:

Network support
===============

Network support in U-Boot is **essential** for any useful automation.
Specifically, ``TFTP`` support in U-Boot needs to work to use any of the
existing U-Boot support in LAVA V2.

Additional U-Boot support
*************************

Some developers integrating new U-Boot devices may need to consider more
elements of U-Boot behavior and configuration.

.. _uboot_filesystems:

Filesystem support
==================

Filesystem support in U-Boot is optional, but will be required for
:ref:`secondary media <secondary_media>`. Check if U-Boot on the device
supports the filesystems you want to use, fat or ext2|3|4. Check if your U-Boot
has limits on the sizes of the filesystems it supports. In some cases, it may
be necessary to use a separate small ``/boot`` partition to make things work.

.. _uboot_interfaces:

Interface names
===============

Some configurations of U-Boot may change how interfaces like SATA are accessed
by U-Boot. For secondary media support or to read files from an attached
storage device, you will need to find out how the U-Boot describes that storage
interface (e.g. ``sata``, ``scsi``, ``usb``, ``mmc``).

.. _uboot_subsystems:

Initializing subsystems
=======================

Some U-Boot devices will not enable some of the onboard storage or peripheral
devices without explicitly initializing them first. Some may need other
subsystems to be initialized first - for example the Panda needs ``usb start``
before networking will work, as the onboard network interface is attached via
USB.

.. _uboot_append_dtb:

Appending the DTB
=================

Some U-Boot configurations support loading a DTB for the device separately, but
not all. If your U-Boot does not support this, you will need to append the DTB
to the kernel instead. This will obviously affect the commands used to boot
your device (e.g. ``tftp``, ``loadm`` or ``bootm``), but also remember that you
will need to generate this combined image file ready for use on the device.

.. add an integration story for the cubietruck and the mustang U-Boot.
