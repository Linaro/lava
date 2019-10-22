Integration Stories
###################

.. index:: nexus, device integration - fastboot nexus

.. _integrating_fastboot_nexus:

Integration Story One - Nexus
*****************************

.. important:: This use case is merely illustrative and **not a detailed
   guide**. The :ref:`device integration guidelines <adding_new_device_types>`
   can only highlight certain aspects of previous device integrations in the
   hope that the experience will be useful. There is no step-by-step guide to
   any device integration into LAVA.

Google Nexus devices are standard devices which once unlocked or rooted will
get into fastboot mode without any requirement for manual intervention. A
suitable AOSP build (See assumption 4 above) flashed to the Nexus can make use
of ``adb reboot bootloader`` in order to get into fastboot mode.

Deploy
======

The only supported operating system on the Nexus would obviously be AOSP and
this reduces the problem space to a greater extent. In case of Nexus devices
the AOSP is supplied as images for the following partitions::

 boot
 cache
 system
 userdata
 vendor

Which are straightforward to flash using fastboot command during the deploy
stage or action. flash_cmds_order parameter from the device dictionary is used
to determine the order in which the above images will be flashed to their
respective partitions.

Boot
====

In case of boot action the ``fastboot boot sequence`` comes into place which is
simple as seen below::

 - reboot
 - wait-usb-add
 - lxc-add-device

When the device is still in fastboot mode after the deployment of images to the
respective partitions ``fastboot reboot`` is issued which will reboot the Nexus
device to the AOSP operating system. We wait for a udev add event and then once
the event happens, we add the device to the LXC container using the device_info
values.

Thus the device is booted and ready for running tests via ADB from an LXC
container.

Issues
======

There is no serial console hence we cannot monitor the kernel boot log or
messages while Nexus device boots. We need a mechanism such as
``reboot-to-fastboot`` set to false in order to not reboot the Nexus device to
fastboot mode, since most of these devices do not charge in fastboot mode,
hence the battery drains if the device is in fastboot mode which calls for
manual intervention to juggle with the volume and power buttons at different
combinations to make the device usable for automation. Nexus devices have
inbuilt battery, hence these are not suitable for controlling them with a Power
Distribution Unit (PDU). So hard reset literally means ``adb reboot
bootloader`` (provided the AOSP build installed on the Nexus device is stable)
or ``fastboot reboot bootloader`` (provided we are in fastboot mode), both of
which are software triggered and not a proper hard reset.

Sample job run - https://staging.validation.linaro.org/scheduler/job/175653
Currently LAVA V2 supports the following Google Nexus devices (provided
suitable builds are available):

* Nexus 4

* Nexus 5x

* Nexus 9

* Nexus 10

.. index:: pixel, device integration - fastboot pixel

.. _integrating_fastboot_pixel:

Integration Story Two - Pixel
*****************************

.. important:: This use case is merely illustrative and **not a detailed
   guide**. The :ref:`device integration guidelines <adding_new_device_types>`
   can only highlight certain aspects of previous device integrations in the
   hope that the experience will be useful. There is no step-by-step guide to
   any device integration into LAVA.

Pixel
=====

Google Pixel is same as the Google Nexus device with very minimal differences.
Everything said above for Nexus devices applies to Google Pixel except for the
following described in the issues below.

Issues
======

Google Pixel requires latest versions of fastboot and adb tools. The version of
fastboot (4.2.2) and adb (4.2.2) found in Debian Jessie does not work correctly
with Google Pixel. It requires a pretty recent version which is now available
in Debian Stretch - fastboot (1:7.0.0) and adb (1:7.0.0).

Google Pixel has two system partitions which is different from old Google Nexus
devices::

 system_a
 system_b

The partitions or images supplied for deployment in case of Google Pixel are as
follows and the order in which they are flashed are of prime importance which
is handled by flash_cmds_order::

 boot
 userdata
 system_a
 system_b
 vendor

Sample job run - https://staging.validation.linaro.org/scheduler/job/177188

.. index:: hikey6220, device integration - fastboot hikey6220

.. _integrating_fastboot_hikey6220:

Integration Story Three - HiKey 6220
************************************

.. important:: This use case is merely illustrative and **not a detailed
   guide**. The :ref:`device integration guidelines <adding_new_device_types>`
   can only highlight certain aspects of previous device integrations in the
   hope that the experience will be useful. There is no step-by-step guide to
   any device integration into LAVA.

HiKey 6220 is the most problematic board due to various reasons. There were too
many workarounds put in place just for supporting HiKey 6220’s automation since
the board was inherently not stable for automation. The key things that hinders
automation on Hikey 6220 are as follows:

Unstable UEFI firmware
======================

* For every new release of the firmware which happens once in two months the
  behavior or the interface changes.

* Text used for interrupting UEFI bootloader has changed many times.

* The timeout in order to hit any key to enter UEFI menu has changed which
  sometimes made automating it harder due to insufficient time to capture the
  interrupt prompt and feed the interrupt string.

* Inconsistent behavior of bringing up the UEFI bootloader after soft resets
  and hard resets.

* Changes with different versions of firmware in the way we get into fastboot
  mode.

Serial numbers
==============

By default HiKey 6220 does not provide a unique serial number, though there is
a way to set unique serial number.

Due to the hardware design decisions made when creating HiKey 6220 the OTG port
and TYPE A ports are not usable at the same time. To automate the image
delivery we use fastboot, which requires the OTG port to be connected during
flashing. However, for automated testing we would prefer to use a USB attached
ethernet adapter as it is more reliable than WiFi. Somewhere between the
delivery of images and booting the kernel, we need to disable the OTG port to
allow the TYPE A ports to function.

Irrespective of the operating system that is getting deployed we need to enable
the USB OTG port which may have been disabled in the previous job run (Why this
is done is explained in point 3 above). This is done using the
``pre_power_command``, called via the lava-lxc protocol for deploy action.

.. seealso:: :ref:`using_protocols_from_actions`

Deploy
======

HiKey 6220 supports different operating systems such as AOSP, GNU/Linux
(Debian, Ubuntu, etc.) and OpenEmbedded (OE), for which different partition
schemes and communication schemes has to be supported. HiKey has a UEFI
firmware as seen above which can get you to a UEFI menu to choose the device or
operating system from where you want to boot or get into fastboot mode. The
primary method of flashing images to HiKey 6220 is by using ``fastboot flash``
commands.

AOSP
----

In case of AOSP a HiKey needs to flash the images mentioned in the deploy
action using the flash commands. The order in which images are getting flashed
is important which is controlled by flash_cmds_order

AOSP for HiKey 6220 is provided using the following images::

 ptable
 boot
 cache
 userdata
 system

HiKey 6220 firmware has some issues when we do not hard-reset after flashing
certain images such as ptable and boot. This is required especially when the
HiKey’s following job requests to run a different operating system from the one
that was run on the last job ie., if a job runs AOSP and the following job
wants to run OE then we need to flash a partition different partition table
which reflects after a reboot of the HiKey. Hence the deploy action in HiKey
accepts a special parameter called ``reboot`` which indicates whether to reboot
the HiKey after flashing the current image. The values accepted for this
parameter are as follows:

hard-reset
  does a power cycle with the help of PDU after flashing

fastboot-reboot
  does a ``fastboot reboot`` after flashing

fastboot-reboot-bootloader
  does a ``fastboot reboot bootloader`` after flashing

For some reason we have identified ``hard-reset`` always works and it is
recommended. It is uncertain why fastboot-rebooot or fastboot-reboot-bootloader
creates problem in identifying the partitions properly after flashing. This is
a significant issue that was discovered after running too many jobs on the
HiKey.

OE
--

In case of OE a HiKey needs to flash the images mentioned in the deploy action
using the flash commands. Similar to AOSP the order in which images gets
flashed is important which is controlled by flash_cmds_order

OE for HiKey 6220 is provided using the following images::

 ptable
 boot
 system

The same issue with rebooting after flashing ptable and boot partitions applies
to OE images as explained above for AOSP.

Debian
------

In case of Debian a HiKey needs to flash the images mentioned in the deploy
action using the flash commands. Similar to AOSP the order in which images gets
flashed is important which is controlled by flash_cmds_order

Debian for HiKey 6220 is provided using the following images::

 ptable
 boot
 system (the rootfs of Debian system)

The same issue with rebooting after flashing ptable and boot partitions applies
to Debian images too.

Boot
====

AOSP
----

The fastboot boot sequence for AOSP on HiKey is defined with the following
steps on the device dictionary::

    - boot
    - wait-usb-add
    - lxc-add-device
    - auto-login
    - shell-session
    - export-env

Since the HiKey has a serial connection we can watch the kernel boot log using
the serial connection.

AOSP provides ADB communication, hence the tests are run using lava-test-shell
from within the LXC container communicating via ADB daemon on the HiKey.

OE / Debian
-----------

Both OpenEmbedded and Debian operating systems are booted using the selection
on the UEFI Menu. We interrupt to get into the UEFI menu and then select the
menu item which says “boot from eMMC” where the images will be flashed in the
previous deploy action. Once this selection is done the OS starts booting, at
which point we need a mechanism to switch off the OTG port so that Type A port
starts working and brings up the connected USB ethernet adapter.

.. seealso:: ``pre_os_command`` usage with :ref:`using_protocols_from_actions`

We won't require the OTG port henceforth since we have a serial connection to
monitor and also ethernet is up for communicating to the internet.

OE or Debian does not provide ADB communication, hence the tests are run using
lava-test-shell directly on the HiKey using the serial connection where LXC is
not used.

Sample Job Runs
AOSP - https://staging.validation.linaro.org/scheduler/job/179225
OE - https://staging.validation.linaro.org/scheduler/job/179207

Other Issues
============

Overview
--------

In LAVA V2 HiKey requires pins 5-6 shorted in order to get into fastboot mode
every time after a reboot or a hard reset. This document discusses the need for
shorting 5-6 pins and how it differs from V1.

V2 Scenario
"""""""""""

In LAVA V2 we assume HiKeys have pins 5-6 shorted so that the HiKey gets into
fastboot mode every time there is a reboot or a hard reset. With this
assumption in place we carry on the following actions:

Deploy the images using fastboot flashing since the device is in fastboot mode
by default.

Once the flashing is done, we “fastboot reboot” the device which will take it
to fastboot mode again. If the test job specifies to boot android, fastboot
does not need to be interrupted a second time. To access the UEFI menu to boot
other systems, fastboot is interrupted, to bring up blitthe uefi_menu on which
we choose the second option ie., “[2] boot from eMMC” and boot the device to
the operating system that was flashed in 1.

The above is the right way of doing things, since we can enter into fastboot
mode every time even when the test flashes the boot partition of the device
with different boot.img, which is not possible in V1.

V1 Scenario
"""""""""""

In LAVA V1 we have pins 3-4 shorted which will not take the device to fastboot
mode by default. In order to get into fastboot, the bootloader prompt should be
interrupted and the corresponding UEFI menu item has to be selected for
fastboot. When pins 3-4 are shorted there is possibility of flashing the
following from a job:

fastboot flash fastboot fip.bin
fastboot flash nvme nvme.img

The above can leave the board inconsistent, which complicates automation since
we need the same kind of interface every time the board is rebooted or
hard-reset.

.. index:: dragonboard-410c, device integration - fastboot db410c

.. _integrating_fastboot_db410c:

Integration Story - Dragonboard 410c
************************************

.. important:: This use case is merely illustrative and is **not a detailed
   guide**. The :ref:`device integration guidelines <adding_new_device_types>`
   can only highlight certain aspects of previous device integrations in the
   hope that the experience will be useful. There is no step-by-step guide to
   any device integration into LAVA.

Similar to :ref:`integrating_fastboot_hikey6220`, the Dragonboard 410c (DB410C)
supports different operating systems such as AOSP, GNU/Linux (Debian, Ubuntu,
etc.) and OpenEmbedded (OE), for which different partition schemes and
communication schemes has to be supported. DB410C uses fastboot for both deploy
and boot actions. The primary method of flashing images to DB410c is by using
``fastboot flash`` commands.

Sample Job Run - https://staging.validation.linaro.org/scheduler/job/179278

Issues
======

DB410C is a pretty stable platform and hasn’t given much pains during
integration except for one issue where the images provided for DB410C (this is
specific to Linaro images) are sparse images. In order to convert the sparse
image to normal image we use a tool called simg2img. Once the sparse image is
converted to a normal image we will apply the overlay and then do a normal
image to sparse image conversion using a tool called img2simg. Both these tools
simg2img and img2simg are available in Debian jessie and stretch. The
conversions and application of overlay are done just before flashing these
images within the LXC container which should have tools such as simg2img and
img2simg installed.


.. index:: hikey960, device integration - fastboot hikey960

.. _integrating_fastboot_hikey960:

Integration Story Five - HiKey 960
**********************************

So far, no advantages discovered. Less usable than the 6220.

Cons
====

Fastboot required to deploy non-fastboot systems due to lack of visibility of
the USB stack in UEFI and the lack of a physical NIC on the device.

Custom hardware which is required to provide serial over low speed connector
does not have mount points and can wobble.

Highly unstable device - continues to reset the serial connection arbitrarily.
Appears to cause issues in the USB stack of the worker, making subsequent test
jobs unreliable.

Hardware is incapable of driving the OTG and the USB Host at the same time,
causing complex problems with needing to use specialist USB hub control systems
to change the mode of the OTG port during every test job to be able to have any
network capability after deployment.

Less reliable than the HiKey 6220.

Unexpected changes in the UEFI compared to the 6220 which make the menus
impossible to automate, necessitating a different code flow for support in V2.

Gaps in the 96boards documentation and completely missing documentation for the
changes made for Linaro CI caused several months of delays and wasted
investigation.

Original firmware changes the fastboot serial number randomly on every reboot.

Apparent habit of dropping the serial connection arbitrarily during fastboot
deployment - 3 out of every 5 test jobs failed this way during development.
