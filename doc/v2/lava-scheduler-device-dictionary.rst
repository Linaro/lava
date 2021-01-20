.. index:: device dictionary - help

.. _device_dictionary_help:

Detailed device dictionary information in LAVA Scheduler
########################################################

Each :term:`device type` in LAVA defines a template to describe the features of
that device type, and how LAVA can use it. A :term:`device dictionary`
customizes that template to include the data for one specific instance of that
device. This includes details like the commands to connect specific serial
ports for this device, commands to operate remote power control, device serial
numbers and elements of the network topology for :term:`VLANd` support.

Other fields can also be used in the templates. The only field which is
compulsory is **extends** which links this device dictionary to a specific
device type template.

.. _device_dictionary_commands:

Commands
********

* **connection_command** - **deprecated** command to access the serial port of
  the device.

  .. seealso: :ref:`device_dictionary_connections` and
    :ref:`configuring_serial_ports`

* **power_on_command** - command to supply power to the device remotely. (The
  device **must** start the boot sequence on application of power.)

* **power_off_command** - command to terminate power to the device remotely.

* **soft_reboot_command** - command to issue at a prompt of a running system to
  request a reboot.

* **hard_reset_command** - command to abruptly terminate power and then supply
  power to the device remotely. May include a delay using ``sleep``.

* **pre_power_command** - ancillary command used for special cases, dependent
  on deployment method and device type template support.

* **pre_os_command**  - ancillary command used for special cases, dependent
  on deployment method and device type template support.

* **device_info** - a list of dictionaries, where each dictionary value can
  contain keys such as 'board_id', 'usb_vendor_id', 'usb_product_id',
  'wait_device_board_id', which can be added to the LXC for device specific
  tasks dynamically, whenever the device is reset, using a ``udev`` rule.

* **static_info** - a list of dictionaries, where each dictionary value can
  contain keys such as 'board_id', 'usb_vendor_id', 'usb_product_id', which
  will be added to the LXC for device specific tasks when the LXC is started.
  Used for static devices which are always visible to the dispatcher, for
  example the ARM Energy Probe which has a USB connection to the dispatcher
  and probe connections to the device.

* **adb_serial_number** - value to pass to ADB to connect to this device.

* **fastboot_serial_number** - value to pass to ``fastboot`` to connect to this
  device.

* **fastboot_options** - a list of strings, used for specifying additional
  options to the ``fastboot`` command.

.. _device_dictionary_connections:

Connections
***********

* **connection_list** - the list of hardware ports which are configured for
  serial connections to the device.

* **connection_commands** - a dictionary of the commands to start each
  connection.

* **connection_tags** -  Each connection can include ``tags`` - extra pieces of
  metadata to describe the connection.

  There must always be one (and only one) connection with the ``primary`` tag,
  denoting the connection that will be used for firmware, bootloader and kernel
  interaction.

  Other tags may describe the *type* of connection, as extra information that
  LAVA can use to determine how to close the connection cleanly when a job
  finishes (e.g ``telnet`` and ``ssh``).

.. seealso:: :ref:`create_device_dictionary`, :ref:`configuring_serial_ports`
   and :ref:`viewing_device_dictionary_content`.

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

The "download" button present in the :term:`device dictionary` page is used to
download a YAML file of the :term:`device dictionary`, which is the equivalent
of contents returned by `lavacli devices dict get`. This file
is not intended for admin support and cannot be used to modify the
:term:`device dictionary` itself.

.. index:: storage_info, device_ip, device_mac

.. _device_dictionary_exported_parameters:

Exported parameters
*******************

Some elements of the device configuration can be exposed to the test shell,
where it is safe to do so. Each parameter must be explicitly set in each device
dictionary. The information will then be populated into the
:ref:`lava_test_helpers`.

* **device_ip** - A single fixed IPv4 address of this device. The value will be
  exported into the test shell using ``lava-target-ip``.

  .. code-block:: jinja

   {% set device_ip = "10.66.16.24" %}

* **device_mac** - similar to ``device_ip`` but for a single MAC address.

  .. code-block:: jinja

   {% set device_mac = '00:02:F7:00:58:53' %}

* **storage_info** - a list of dictionaries, where each dictionary value can
  contain keys describing the storage method (e.g. USB or SATA) and a value
  stating the device node of the top level block device which is available to
  the test writer.

  .. code-block:: jinja

   {% set storage_info = [{'SATA': '/dev/disk/by-id/ata-ST500DM002-1BD142_W3T79GCW'}] %}

* **environment** - a dictionary containing device-specific shell
  variables, which will be available in the LAVA test shell. These can
  be used, for example, to describe physical hardware connections
  between the :term:`DUT` and interfaces on the worker or other
  addressable hardware.

  .. code-block:: jinja

   {% set environment = {
       'RELAY_ADDRESS': '10.66.16.103',
       'REMOTE_SERIAL_PORT': '/dev/ttyUSB2',
   } %}

For ease of use, LAVA will directly export the content of the
**device_info**, **environment**, **static_info** and **storage_info**
dictionaries into the test shell environment. The dictionaries and
lists will be unrolled, for example:

.. code-block:: jinja

   {% set static_info = [{"board_id": "S_NO81730000"}, {"board_id": "S_NO81730001"}] %}
   {% set storage_info = [{'SATA': '/dev/disk/by-id/ata-ST500DM002-1BD142_W3T79GCW'}] %}

will become:

.. code-block:: shell

   export LAVA_STATIC_INFO_0_board_id='S_NO81730000'
   export LAVA_STATIC_INFO_1_board_id='S_NO81730001'
   export LAVA_STORAGE_INFO_0_SATA='/dev/disk/by-id/ata-ST500DM002-1BD142_W3T79GCW'

The environment can be **overridden in the job definition**. See
:ref:`job_environment_support`.

.. seealso:: :ref:`test_device_info` and :ref:`extra_device_configuration`.

.. _device_dictionary_other_parameters:

Other parameters
****************

* **flash_cmds_order** - a list of strings, used for specifying the order in
  which the images should be flashed to the :term:`DUT` using the ``fastboot``
  command.
