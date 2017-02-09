.. index:: device dictionary help

.. _device_dictionary_help:

Detailed device dictionary information in LAVA Scheduler
########################################################

Each :term:`device type` in LAVA defines a template to describe the features of
that device type, and how LAVA can use it. A :term:`device dictionary`
customises that template to include the data for one specific instance of that
device. This includes details like the specific serial port connection for this
device, commands to operate remote power control, device serial numbers and
elements of the network topology for :term:`vland` support.

Other fields can also be used in the templates. The only field which is
compulsory is **extends** which links this device dictionary to a specific
device type template.

Dictionary elements are shown in three blocks; commands, vland and others.

Commands
********

* **exclusive** - if set to ``'True'``, the device will not accept V1
  submissions.

* **connection_command** - command to access the serial port of the device.

* **power_on_command** - command to supply power to the device remotely. (The
  device **must** start the boot sequence on application of power.)

* **power_off_command** - command to terminate power to the device remotely.

* **soft_reset_command** - command to issue at a prompt of a running system to
  request a reboot.

* **hard_reset_command** - command to abruptly terminate power and then supply
  power to the device remotely. May include a delay using ``sleep``.

* **pre_power_command** - ancillary command used for special cases, dependent
  on deployment method and device type template support.

* **pre_os_command**  - ancillary command used for special cases, dependent
  on deployment method and device type template support.

* **device_info** - a list of dictionaries, where each dictionary value can
  contain keys such as 'board_id', 'usb_vendor_id', 'usb_product_id', which can
  be added to the LXC for device specific tasks.

* **adb_command** - command to access the device using ADB.

* **adb_serial_number** - value to pass to ADB to connect to this device.

* **fastboot_command** - command to access the device using fastboot.

* **fastboot_serial_number** - value to pass to fastboot to connect to this
  device.

VLANd support
*************

.. seealso:: :ref:`vlan_support`

* **interfaces** - the list of interface labels supported by the device.

* **tags** - a dictionary of interface labels containing a list of the
  :term:`interface tags <interface tag>` for each label.

* **map** - the :ref:`network map <vland_network_map>` as it relates to this
  device. A dictionary of interface labels containing a dictionary of the
  switch name and port number relating to the physical cable connection to the
  interface associated with the interface label on that device.

* **mac_addr** - a dictionary of interface labels containing the MAC address
  of the interface associated with the interface label on that device.

* **sysfs** - a dictionary of interface labels containing the ``sysfs`` path of
  the interface associated with the interface label on that device.
