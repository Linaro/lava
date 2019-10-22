.. index:: device integration - fastboot

.. _integrating_fastboot:

Fastboot
********

.. important:: Make sure you have read :ref:`adding_new_device_types` first.

Fastboot devices can be simple to integrate but fastboot deployment has several
issues which can cause issues in automation.

.. seealso:: :ref:`lxc_deploy` and :ref:`deploy_using_lxc`

#. The fastboot protocol runs from the worker and *pushes* files to the device.
   This causes issues with :ref:`integration_scalability` compared to
   deployment methods which allow the :term:`DUT` to *pull* files over a
   network connection.

   * As a guideline, ensure that each worker has one CPU core for each fastboot
     device plus at least one more core for the rest of the system to avoid
     excessive load on the worker.

#. Different fastboot devices can need different versions of fastboot to be
   installed **on the worker**, so LAVA uses :term:`LXC` to isolate all
   fastboot operations on the worker.

#. Each fastboot process tries to collect all of the fastboot devices which are
   visible in ``dev/bus/usb``. When fastboot is pushing files to one device, a
   second fastboot process would not be able to connect to a different device
   on the same worker. This is the second reason why LAVA uses :term`LXC` with
   fastboot as LAVA can then ensure that the only device node(s) which show up
   in ``/dev`` inside the LXC are the nodes specifically related to a single
   fastboot device.

#. Fastboot relies on every :term:`DUT` having a unique fastboot serial number
   which **must** persist across reboots and test jobs. The fastboot serial
   number can be the same as the :abbr:`ADB (Android Debug Bridge)` serial
   number. The fastboot serial number **must** modifiable by the admin in case
   an existing device is already using that number.

#. For automation to work, all fastboot devices **must** boot into fastboot
   mode **automatically** after every hard reset or soft reboot.

#. The device needs to implement the ``fastboot boot <boot img>`` command, so
   that the test image can be loaded directly into memory and executed.

External constraints
====================

In addition, integrating fastboot devices has some limitations on how the test
images are prepared.

Device changes
--------------

The DUT should be roooted or unlocked wherever applicable (mostly phones,
tabs, etc.) ``fastboot oem unlock`` or ``fastboot flash unlock``

Images
------

No special mangling of supplied images are required, ie., LAVA will not do any
magic on the images, except for decompressing images (based on already
supported decompression methods) if they are in compressed state.

.. seealso:: :ref:`integrate_android`.

.. _integrate_android:

Android
=======

LAVA relies on :abbr:`ADB (Android Debug Bridge)` and ``fastboot`` to control
an Android device. Support for ADB **must** be enabled in **every** image
running on the device or LAVA will lose the ability to access, reboot or deploy
to the device::

    ro.secure=0
    ro.debuggable=1
    ro.adb.secure=0
    persist.service.adb.enable=1

These settings enable USB debugging on the DUT and allow the DUT to trust the
worker by default.

.. index:: device integration - fastboot devices

.. _integrating_fastboot_devices:

Specific support for fastboot devices in LAVA
=============================================

.. seealso:: :ref:`device_dictionary_commands` and
   :ref:`device_dictionary_other_parameters`

fastboot sequence or fastboot boot sequence - This is provided as a list within
the device dictionary and can take the following values, which are actions that
will get added as sub actions to the boot action pipeline:

boot
  ``fastboot boot boot.img`` where boot.img is supplied via the deploy action

reboot
  ``fastboot reboot`` which will reboot the DUT to the operating
  system

auto-login
  auto login action

shell-session
  wait for a shell session

export-env
  export environment as defined for the DUT
