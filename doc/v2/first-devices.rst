.. index:: first devices

.. _first_devices:

Adding your first devices
#########################

Requirements
************

You need to be familiar with these sections:

#. :ref:`installation`
#. :ref:`creating a pipeline worker <setting_up_pipeline_instance>`.
#. :ref:`adding_pipeline_devices_to_worker`
#. :ref:`create_superuser`
#. :ref:`logging_in` (as superuser)
#. :ref:`device_types` and :ref:`device_type_elements`

.. seealso:: `Django documentation on the Django Admin
   Interface <http://www.djangobook.com/en/2.0/chapter06.html>`_

.. _django_admin_interface:

Django administration interface
*******************************

The django admin interface is a core component of the django framework.
Elements can be added for particular implementations but, fundamentally,
the operation of the interface is the same as other django sites. The
appearance of the menu is determined by the version of django installed
on your system. The style changed substantially in django 1.9, so images
of the interface itself are not included here.

Changes within the administration interface and changes made as a superuser
through the UI are tracked through the **History** elements of objects in the
database. When viewing a specific element (for example a single Test Job or a
single Device), click on the **History** link to view all changes relating to
that element. There is also a link back to the UI view of the same element.

.. note:: the organisation, layout and content of the django administration
   interface is subject to change with upgrades to django itself and these
   changes are outside the control of LAVA.

.. _django_admin_interface_sites:

Administative interface site links
==================================

The django administrative interface offers links back to your LAVA
instance *if* the ``Sites`` element is modified. (The default django
value is ``example.com``.) Navigate to the ``Sites`` element in the
administrative interface and modify the domain name and display name.
Once complete, links like ``View site`` and the ``View on site``
button on certain pages of the interface will link to the correct
location in your LAVA instance.

Start with a known device type
******************************

It is tempting to jump straight in with your one-off special device
which nobody else has managed to automate yet but a fresh install
**needs** to be tested with a known working configuration. Setting up
known working devices and learning how to modify the
:ref:`first job <first_job_definition>` is essential to deciding how
to best configure a new device. It is also **recommended** to setup
another known device type which is similar to the device you want to
add as there are different steps required for certain types of device.

This first QEMU device can be configured on the existing worker which
is always available on the master. Subsequent devices can be added to
other workers and devices can be shuffled between workers, subject to
limitations of physical connections.

QEMU
====

QEMU is always recommended as the first device to be set up on any
LAVA instance for a few reasons:

#. QEMU requires no external hardware or software configuration
   (until a network bridge becomes desirable)
#. QEMU requires only a minimal :term:`device dictionary`.
#. Test images for use with QEMU are readily available and relatively
   easy to modify.

.. seealso:: :ref:`creating_gold_standard_files` and
   :ref:`adding_qemu_v2_device`.

.. index:: add-device-type, adding a device type

.. _create_device_type_database:

Create a Device Type
--------------------

Prior to adding any devices, admins should add suitable :term:`device types
<device type>` to the database.
The device type name should match a jinja2 template file in::

 /etc/lava-server/dispatcher-config/device-types/

If an existing template does not exist, a new template will need to be created.

.. seealso:: :ref:`device_types`

You can then either use the :ref:`web admin interface <django_admin_interface>`
or the ``lava-server`` command line to add device types.

**Using the admin interface**

In order to use the web admin interface, log in to the LAVA instance and click
on your username to see the Profile menu.

.. image:: images/profile-menu.png

The django administrative interface is accessed from the ``Administration``
link in the profile menu.

#. Scroll down to the group labelled ``LAVA_SCHEDULER_APP``.
#. Click on ``Device types``

Just before you add the device type, take a look at the available
:ref:`elements of a device type <device_type_elements>`:

* Name
* Has health check
* Display
* Owners only
* Health check frequency
* Architecture name
* Processor name
* CPU model name
* List of cores
* Bit count

The only value needed for the QEMU device type is the **Name**, just
check that **Display** is the default: enabled. Now Save.

**Using the command line**

On the command line, you can add device types (for instance QEMU and panda)
using::

  lava-server manage add-device-type qemu panda

It's also possible to add all known device types at the same time with:

.. code-block:: none

  lava-server manage add-device-type '*'

Descriptive fields like ``Architecture name``, ``Processor name``, ``CPU model
name``, ``List of cores`` and ``Bit count`` cannot be set on the command line.

Using the command line interface it's also possible to list all known device
types:

.. code-block:: none

  lava-server manage add-device-type --list

.. index:: add-device, adding a device, create a device in the database

.. _adding_qemu_v2_device:

Create a device in the database
-------------------------------

**Using the admin interface**

* Navigate back to ``LAVA_SCHEDULER_APP`` and select ``Devices`` and
  ``Add Device``.
* Select the QEMU device type from the list.
* Give your device a name
* Select the worker from the list.
* Set the Device owner (typically one of the superusers).
* Your first device should be public.
* Ensure that the device is enabled as a ``Pipeline device``.

**Using the command line**

Using the command line interface it's also possible to list all known device
types:

.. code-block:: none

  lava-server manage add-device --list

On the command line, you can add device types (for instance a QEMU type device
with a hostname ``qemu01``) using::

  lava-server manage add-device --device-type qemu qemu01

See ``lava-server manage help add-device`` for more options, including initial
states of the device in the database.

Adding a dictionary to the first QEMU device
--------------------------------------------

For the first device, a simple :term:`device dictionary` can be used
to provide the device-specific details on top of the template:

.. code-block:: jinja

  {% extends 'qemu.jinja2' %}
  {% set mac_addr = '52:54:00:12:34:59' %}
  {% set memory = '1024' %}

* The device dictionary **must** ``extend`` an existing template.

* The architecture (``arch`` value) is not set in this device dictionary. This
  allows this device to run test jobs using files for any architecture
  supported by QEMU.

  .. seealso:: :ref:`overriding_device_configuration`

* The MAC address needs to differ for each device of this type across all
  instances on the same subnet.

* The available memory for the virtual machine is set in megabytes. This can be
  changed later to balance the requirements of test jobs with performance on
  the worker.

* Line ordering within the device dictionary is irrelevant, although
  it is common to put the ``extends`` line first when storing the
  dictionary as a file.

The template itself lives in::

 /etc/lava-server/dispatcher-config/device-types/qemu.jinja2

This dictionary does not include a setting to use a ``tap`` device which
means that this device would not support a hacking session inside the
virtual machine. Setting up a bridge is out of scope for this documentation.

.. seealso:: :ref:`create_device_dictionary` to export and modify a device
   dictionary, :ref:`updating_device_dictionary` to import a device dictionary
   into the database for use with a new or existing device,
   :ref:`checking_templates` for help with types of devices other than QEMU and
   :ref:`device_type_templates` for help with how the device dictionary works
   with the device-type templates.

Once updated, the device dictionary is added to the Device view in the
administrative interface under the Advanced Properties section at the
base of the page.

.. index:: adding devices of known types

.. _adding_known_devices:

Adding other devices of known device-types
******************************************

The core principles remain the same as for QEMU, the main differences
are in the way that the device dictionary is needed to provide a wider
range of settings covering power control, serial connections, network
details and other values.

.. seealso:: :ref:`health_checks` - each time a new device type is added to an
   instance, a health check test job needs to be defined.

Check existing instances
========================

Templates usually exist for known device types because an existing
instance is using the template. Often, that instance will be Linaro's
central validation lab in Cambridge which is accessible via
https://validation.linaro.org/ .

The contents of the device dictionary for particular devices are visible
to anyone with access to that device type, using the device detail page.
Details of the jinja2 files used to update the device dictionary on
Linaro instances is also held in git::

 https://git.linaro.org/lava/lava-lab.git

The structure of the device dictionary files will be similar for each
device of the same type but the values will change. An example for a
beaglebone-black device looks like:

.. code-block:: jinja

 {% extends 'beaglebone-black.jinja2' %}
 {% set connection_command = 'telnet localhost 7101' %}
 {% set hard_reset_command = '/usr/local/lab-scripts/snmp_pdu_control --hostname pdu15 --command reboot --port 11' %}
 {% set power_off_command = '/usr/local/lab-scripts/snmp_pdu_control --hostname pdu15 --command off --port 11' %}
 {% set power_on_command = '/usr/local/lab-scripts/snmp_pdu_control --hostname pdu15 --command on --port 11' %}

https://git.linaro.org/lava/lava-lab.git/blob/HEAD:/staging.validation.linaro.org/lava/pipeline/devices/staging-black01.jinja2

.. note:: It is recommended to keep the device dictionary jinja files
   under version control. The templates are configuration files, so if
   you modify the default templates, those need to be under version
   control as well.

Migrating V1 devices to V2 devices
**********************************

If you have a working V1 configuration, this can be migrated to the
V2 requirements. Devices can support both models during the migration,
admins can choose to make some devices :term:`exclusive` to V2 at any
time before the V1 code support is removed.

.. seealso:: :ref:`migrating_known_device_example` and
   :ref:`migrating_to_pipeline`.

.. index:: device integration, adding new device-types

.. _adding_new_device_types:

Adding new device types
***********************

.. warning:: This is the most complex part and it can be a lot of work
  (sometimes several months) to integrate a completely new device into
  LAVA. V2 offers a different and wider range of support to V1 but some
  devices will need new support to be written within ``lava-dispatcher``.
  **It is not always possible to automate a new device**, depending on
  how the device connects to LAVA, how the device is powered and whether
  the software on the device allows the device to be controlled remotely.

The integration process is different for every new device. Therefore,
this documentation can only provide hints about such devices, based on
experience within the LAVA software and lab teams. **Please** talk to
us **before** starting on the integration of a new device using the
:ref:`mailing_lists`. Include full details of the type of device, the
bootloader specifications, hardware support and anything you have done
so far to automate the device. Sometimes, the supplied bootloader
**must** be modified to allow automation. Some devices need electrical
modifications or specialised hardware to be automated.

Hints
=====

* **UBoot** - if the device supports UBoot then this is a useful
  beginning. However, the build of UBoot on the device can hinder
  integration due to the wide range of configuration options and
  behavioural changes available inside a patched UBoot build. Generally,
  the more components of UBoot that are disabled or removed from a
  vendor build, the harder it will be to integrate. If you are able to
  fully script a UBoot process from interrupting the bootloader to
  booting a kernel of your own choice, this will greatly assist in
  integrating the device into LAVA.

* **Android** - LAVA relies on :abbr:`ADB (Android Debug Bridge)` and
  ``fastboot`` to control an Android device. Support for ADB **must**
  be enabled in **every** image running on the device or LAVA will lose
  the ability to access, reboot or deploy to the device.

* **Battery Power** - devices which have internal batteries become
  difficult to reliably automate for a few issues, unless the battery
  can be permanently removed:

  #. **forced reboots** become impossible without electrical modification
     of the device to temporarily take the battery out of circuit. This
     means that it is much easier to cause the device to go offline
     because of a broken kernel build or broken image.
  #. **recharging** can be an issue - devices may not behave normally
     when held in ``fastboot`` mode or with a broken kernel build or
     image deployed to the system. This can cause the device to fail
     to keep charge in the battery or fail to recharge the battery,
     despite having power available.

* **Serial power leaks** - some devices are capable of drawing power
  over the serial line used to control the device, despite the actual
  power supply being disconnected. Sometimes this requires a period of
  time to discharge capacitors on the board (fixable by adding a ``sleep``
  in the ``power_off_command``). Sometimes this power leak can cause the
  device to ``latch`` into a particular bootloader mode or other state
  which prevents the automation from proceeding.

