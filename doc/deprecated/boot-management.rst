.. _boot_management:

Boot Management
###############

LAVA offers many facilities to control the boot process of a :term:`DUT`.
This enables users to configure the boot process to support custom software
images.

Boot Commands Stanzas
*********************

Boot command stanzas are *predefined* :ref:`boot_commands` which are
included in the device configuration or in the :term:`device type` configuration.

.. _boot_commands:

Boot Commands
=============

The following example demonstrates how to define a boot command stanza.

Example::

 boot_cmds =
     setenv initrd_high "'0xffffffff'",
     setenv fdt_high "'0xffffffff'",
     setenv bootcmd "'fatload mmc 0:3 0x80200000 uImage; fatload mmc 0:3 0x81600000 uInitrd; fatload mmc 0:3 0x815f0000 board.dtb; bootm 0x80200000 0x81600000 0x815f0000'",
     setenv bootargs "'console=ttyO0,115200n8 root=LABEL=testrootfs rootwait ro'",
     boot

In the above example "boot_cmds" is the name of the stanza.

Boot Options
************

Boot options are *predefined* :ref:`boot_commands` which are included
in the device configuration or in the :term:`device type` configuration.

Configuration
=============

The following example demonstrates how to enable, define, and set the
default ``boot_options`` in either the device configuration or
in the :term:`device type` configuration.

Example::

 boot_options =
     boot_cmds

 [boot_cmds]
 default = boot_cmds

The "boot_cmds" stanza defines
