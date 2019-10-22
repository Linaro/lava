.. index:: device integration - uefi, UEFI

.. _integrating_uefi:

UEFI
****

.. important:: Make sure you have read :ref:`adding_new_device_types` first.

:abbr:`UEFI (Unified Extensible Firmware Interface)` is a specification that
defines a software interface between an operating system and platform firmware.
Devices which support UEFI typically need to download or execute a UEFI
application which can act as a bootloader.

Overall, the simplest way to integrate a device using UEFI is not to interact
with UEFI in the integration.

* Configure UEFI to have the required support available as a default boot
  method using a locally installed UEFI application to act as a bootloader.

* Configure UEFI to have suitable drivers to access the network and use that
  support as the default boot method to download a suitable UEFI application to
  act as a bootloader.

.. _integrating_uefi_intro:

Introduction
============

The emphasis when integrating devices using UEFI is to use the firmware to
support and execute a bootloader. Integration has involved using UEFI with:

* PXE which then downloads Grub (mustang, D02 and D03)

  * relies on UEFI exposing a network interface.

* fastboot (HiKey 620)

  * involves the use of :term:`LXC` to run ``fastboot flash`` commands to
    deploy complete images, including ``boot``, ``system`` and ``userdata``
    amongst others.

* onboard grub (Hikey 960)

  * A UEFI application is installed by the test writer using ``fastboot``.

* onboard flash storage (Juno)

  * device-specific support for running commands in a UEFI shell application.

.. _device_integration_uefi_menu:

UEFI menus
==========

Some UEFI implementations use a menu which can be processed over serial but
these menus have proved to be unreliable for full automation as that involves
creating dynamic menu items through a Device Manager. Admins need to create
static menu items where all LAVA will do is select a known menu item. e.g.:

.. code-block:: none

 [1] PXE boot
 [2] Reboot

This can then be automated using these defaults from ``base.jinja2``:

.. code-block:: jinja

 {% set base_menu_interrupt_prompt = 'The default boot selection will start in' -%}
 {% set base_menu_interrupt_string = ' ' -%}
 {% set base_item_markup_list = (
 '            - "["
             - "]"'
 ) -%}
 {% set base_item_class = '0-9' -%}
 {% set base_item_separator = ' ' -%}
 {% set base_label_class = 'a-zA-Z0-9\s\:' -%}
 {% set base_menu_bootloader_prompt = 'Start:' -%}

These defaults describe how to match the line containing the ``label`` (PXE
boot) and then match the integer which can be passed to UEFI to execute that
menu item (1 in this case). Only a single integer is supported by the default
``base_item_class`` and the integer must be enclosed in the characters
specified in the ``base_item_markup_list``. In practice, only a limited number
of devices use this method of presenting a menu in UEFI, so the defaults do not
need to be modified.

.. _device_integration_uefi_graphical:

UEFI graphical interfaces
=========================

Other UEFI implementations (like the D02 and D03 below) use a system which is
closer to `BIOS`_. **These are not possible to drive through serial at all** as
changes are indicated by changing the color highlight and other similar
mechanisms. Admins would need to configure the system to use a boot order or
other supported mechanism so that LAVA does not interact with the UEFI at all.

Not all UEFI instances include a shell or CLI. Not all shells are capable of
downloading test artifacts to the device, e.g. no TFTP support.

.. _BIOS: https://en.wikipedia.org/wiki/BIOS

.. seealso:: https://en.wikipedia.org/wiki/Unified_Extensible_Firmware_Interface

.. _integrating_d02_uefi:

D02/D03
=======

Serial and power control were available over the network due to the onboard
:term:`BMC`. This made integration much simpler, in theory.

Cons
----

The early firmware was incredibly unreliable, it could not see local disks and
grub did not have support for the network device as the EFI networking was
broken. We had to create our own pxe grub and all modules as grub is only
usually installed by a distro, I couldn't find a prepackaged arm64 grub. Then
had to get the admins to match this grub config and make sure the boards were
running the same firmware, which was changing frequently.

The firmware has a bios-like ascii graphical menu system over serial which
would have been impossible to automate, so had to make the board autoboot into
grub. We found that running an installer would overwrite the default boot
option, so had to force the board into a network boot each time. However, the
``ipmi`` calls to do this didn't work, so had to wait for another firmware
update.

.. _integrating_mustang_uefi:

Mustang UEFI
============

Serial and power control work reliably, UEFI is configured by the admin to use
PXE to download a build of Grub with which LAVA V2 can interact. UEFI itself is
capable of executing Grub locally. Working SATA support, physical NIC and a
stable device.

The mustang UEFI uses the ARM BDS (boot device selector) which provides a UEFI
menu which can be supported in LAVA over serial:

.. code-block:: none

 [1] Boot from eMMC
 [2] Device Manager

The UEFI menu support in the template then generates a configuration block for
each device (where ``LAVA PXE Grub`` is the menu entry created by the admins):

.. code-block:: yaml

      uefi-menu:
        menu_options: pxe-grub
        parameters:
          interrupt_prompt: The default boot selection will start in
          interrupt_string: ' '
          item_markup:
            - "["
            - "]"
          item_class: '0-9'
          separator: ' '
          bootloader_prompt: 'Start:'
        pxe-grub:
        - select:
            items:
            - 'LAVA PXE Grub'


.. add a note that Mustang UEFI will not accept a devicetree over TFTP unless
   that has been modified to replace the support already within UEFI.
   the boot firmware has an internal device tree with some elements which are
   defined at runtime.

Cons
----

There were a lot of problems getting a build of UEFI for this platform due to
lack of engagement from hardware suppliers. Issues around getting the network
card supported in UEFI and a very complex upgrade procedure involving an
interim build which was no longer available from usual sources. Upgrading the
local build of Grub inside UEFI is awkward and of little use compared to being
able to deploy over PXE.

Hardware no longer commercially available.

Not possible to switch from UBoot to UEFI on the same device between test jobs
which has delayed availability of V2 UEFI support on mustang until the lab team
can declare a suitable maintenance window for all mustangs.

UEFI was initially scope to work through the menus but this proved to be
unworkable in automation due to complexity of the sequences and the changes in
error handling between levels of the same menus.

.. _integrating_hikey_620_uefi:

HiKey 620
=========

This section only deals with the integration of the HiKey as it relates to the
**UEFI support**.

The HiKey UEFI uses a similar menu approach as the :ref:`mustang
<integrating_mustang_uefi>`. The HiKey 620 firmware is configured to provide a
menu option to boot from the eMMC.

.. code-block:: yaml

      grub-efi:
        reset_device: False
        line_separator: unix
        menu_options: fastboot
        parameters:
          bootloader_prompt: grub>
        installed:
          parameters:
            interrupt_prompt: "Android Fastboot mode"
            interrupt_string: ' '
          commands:
            - search.fs_label rootfs root
            - linux ($root)/boot/ console=tty0 console=ttyAMA3,115200 root=/dev/mmcblk0p9 rootwait rw
            - devicetree ($root)/boot/
            - boot
      uefi-menu:
        menu_options: fastboot
        parameters:
          interrupt_prompt: Android Fastboot mode
          interrupt_string: ' '
          item_markup:
            - "["
            - "]"
          item_class: '0-9'
          separator: ' '
          bootloader_prompt: "Start:"
          boot_message: Booting Linux Kernel...
        fastboot:
        - select:
            items:
             - boot from eMMC


.. _integrating_hikey_960_uefi:

HiKey 960
=========

This section only deals with the integration of the HiKey as it relates to the
**UEFI support**.

The HiKey UEFI uses a similar menu approach as the :ref:`mustang
<integrating_mustang_uefi>`. The HiKey 960 is configured using DIP switches to
always go into fastboot which can then be interrupted after flashing the
relevant files to boot the system. This means that the 960 device configuration
does not describe UEFI at all, simply fastboot and then grub:

.. code-block:: yaml

      fastboot: ['boot', 'wait-usb-add', 'lxc-add-device']
      grub:
        reset_device: False
        sequence:
        - wait-fastboot-interrupt
        installed:
          commands:
            - boot

.. note:: As there is no interaction with UEFI, the boot method is ``grub``
   instead of ``grub-efi`` as used with the HiKey 620. The device configuration
   is therefore much shorter as there is no need to describe how to interact
   with UEFI.
