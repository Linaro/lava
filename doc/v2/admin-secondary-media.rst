.. index:: secondary media - admin

.. _admin_secondary_media:

Enabling Secondary Media
########################

.. caution:: Admins should already have read about :ref:`secondary_media`.

Device configuration
********************

* Not all test devices can support secondary media deployments in
  LAVA.

* Additional hardware is typically required and configuration details of this
  specific hardware need to be added to the :term:`device dictionary` to be
  available to test writers.

* The use of operating system installers and/or the deployment of full
  system images to a :term:`DUT` can substantially increase the administrative
  burden of that device. Administrators can choose to not enable this support.

* Secondary media configuration can be complex and hard to deploy as admins
  need to understand how one specific device fits into the range of options
  which are available to cover other devices. Some level of familiarity with
  :ref:`developing_device_type_templates` **will** be required to be able to
  follow the logic.

.. _identifying_secondary_media:

Identifying secondary media
===========================

A deployment to secondary media must be done by a running operating system, not
by the bootloader. To allow this, the device configuration may need extra
restrictions.

To work reliably, media devices must be consistently, uniquely identifiable.
Some test devices may have multiple SATA disks; on others, different types of
media device (USB storage, SATA, SD) may even show up using the same style of
device name (e.g. ``sda``). Ordering of these devices is not guaranteed on each
boot of the system, particularly when using different configurations and
different kernels. To make such a setup work in all cases, the device_type
needs to declare the flag ``UUID-required: True`` for each relevant interface.
Using cubietruck as an example::

  media:  # two USB slots, one SATA connector
    usb:
      UUID-required: True
    sata:
      UUID-required: False

.. _secondary_media_configuration:

Secondary media configuration
=============================

When configuring and using secondary media, there are **six** sets of
parameters used. In each case, this section only deals with the generic or root
parameter and each deployment method uses a specific variant to cope with the
requirements of the possible bootloaders. Admins need to obtain the various
pieces of information required for the parameters from a running device before
starting to write the configuration for secondary media on the same device. To
obtain the correct values, it may be necessary to take the device offline,
connect to it over serial and interact with the bootloader directly. Once this
data has been obtained, the specific configuration for a deployment method can
involve setting other values beyond the core six.

.. note:: Should a device fail or the secondary media on a device need to be
   replaced, the secondary media identifiers will need to be updated before
   the new hardware can work with the device.

The presence of the ``uuid`` for the particular deployment will enable all the
other options used by secondary media using the same deployment method. Each
deployment method has a dedicated ``uuid`` so that the template can provide the
correct information to the dispatcher. Typically, one device will have one
``uuid`` for one deployment method, so the other deployment methods will be
disabled.

Three deployment methods are currently supported. ``sata``, ``sd`` and ``usb``.
The examples in this section are not intended to provide a complete overview of
all deployment methods but to provide context for why particular values need to
be obtained from the device before secondary media configuration can begin.

Admins will typically also need to use :term:`device tag` if more than one
device of this device-type exists in the instance.

The first two parameters must be configured by admins in the :term:`device
dictionary`. They define the storage device that will be used for the secondary
media deployment, and for safety test writers should not be able to override
these settings.

The last three parameters, ``boot_part``, ``root_uuid`` and ``root_part`` can
be used by the test writer in their job submission, depending on how the
deployed image has been built:

#. The ``uuid`` parameter in the device configuration

   This is the ID of the storage device as it appears to the kernel
   running the ``deploy`` action. This can be found by looking in
   ``/dev/disk/by-id/`` on a booted system.

   For example, a SATA drive which appears as
   ``/dev/disk/by-id/ata-ST500DM002-1BD142_S2AKYFSN`` would define
   ``sata_uuid`` and have an entry in the device dictionary of:

   .. code-block:: jinja

      {% set sata_uuid = 'ata-ST500DM002-1BD142_S2AKYFSN' %}

   .. note:: Currently, **only one** UUID (and hence **only one** storage
      device) is supported for each of the available interfaces (SATA, USB and
      SD) for each :term:`DUT`.

#. The ``device_id`` parameter in the device configuration

   This is the ID of the device as it appears to the bootloader when reading
   deployed files into memory. This can be found by interrupting the bootloader
   and listing the filesystem contents on the specified interface. The
   ``device_id`` is closely related to the ``interface`` name used in the
   bootloader to specify the name of the interface which the bootloader will
   use to access the ``device_id``. With some bootloaders, only the
   ``interface`` value is required.

   For example, when using GRUB, the first detected SATA drive would
   be ``(hd0)``, so the device dictionary only needs:

   .. code-block:: jinja

      {% set sata_interface = 'hd0' %}

   .. note:: The parentheses are omitted here, as GRUB also needs to know the
      partition number - ``boot_part`` within the syntax ``(hd0,1)``. The final
      string is a combination of device and test job configuration because it
      is the submitted image which determines where the kernel image has been
      installed.

#. The ``label`` by which test writers can select the secondary media. Admins
   need to consider how best to create the label. The string should relate to
   the kind of media which is supported - USB stick or SATA drive etc. However,
   the label itself should not be entirely specific to the hardware on one
   specific machine. Often, DUTs will be deployed with similar hardware of the
   same overall brand or model and this provides a good label. For example, if
   all devices of the same device-type have Seagate Barracuda 500GB SATA drives
   as secondary media, then the ``sata_label`` could be usefully set as:

   .. code-block:: jinja

    {% set sata_label = 'ST500DM002' %}

   If all devices of another device-type have SanDisk Cruzer Blade USB sticks
   as secondary media, the ``usb_label`` could be usefully set as:

   .. code-block:: jinja

     {% set usb_label = 'SanDiskCruzerBlade' %}

   Remember that unless the ``uuid`` is set, this label has no effect. If
   there are some devices of the same device-type without SATA drives, the
   device dictionary for those devices simply omits the ``sata_uuid``. Use
   a :term:`device tag` on the devices with secondary media to allow test
   writers to submit to one of the supported devices.

#. The ``boot_part`` can be specified in the job submission if the default in
   the device type template is not correct for the deployed image. This is the
   number of the partition within the deployed image which will contain files
   for the bootloader to use too boot (kernel, initramfs, etc.). Files in this
   partition will be accessed directly through the bootloader, not via any
   mount point specified inside the image.

#. The ``root_uuid`` can be specified in the job submission if the default in
   the device type template is not correct for the deployed image. This is the
   ID of the partition to specify as ``root`` on the kernel command line of the
   deployed kernel when booting the kernel inside the image. This must be
   specified if the device has ``UUID-required`` set to True.

#. The ``root_part`` can be specified in the job submission if the default in
   the device type template is not correct for the deployed image. This is the
   partition number inside the deployed image where the rootfs lives.
   ``root_part`` cannot be used with ``root_uuid`` - to do so causes a
   JobError.

Media settings are configured per test device, based on the capability
of the device type. An individual test device of a specified type
*may* have exactly one of the available slots populated on any one
interface. These individual devices would need ``UUID-required:
False`` for that interface. e.g. A panda has two USB host slots. For
each panda, if both slots are occupied, specify ``UUID-required:
True`` in the device configuration. If only one is occupied, specify
``UUID-required: False``.

If none are occupied, avoid enabling ``usb_uuid`` in the device dictionary to
disable the ``usb`` interface section in the configuration for that one device.

List each specific storage device attached to that interface
using a human-usable string, e.g. a SanDisk Ultra usb stick with a
UUID of ``usb-SanDisk_Ultra_20060775320F43006019-0:0`` could simply be
called ``SanDisk_Ultra``. Jobs will specify this label in order to
look up the actual UUID, allowing physical media to be replaced with
an equivalent device without needing to change the job submission
data.

The device configuration should always include the UUID for all media
on each supported interface, even if ``UUID-required`` is False. The
UUID is the recommended way to specify the media, even when not
strictly required. Record the symlink name (without the path) for the
top level device in ``/dev/disk/by-id/`` for the media concerned,
i.e. the symlink pointing at ``../sda`` not the symlink(s) pointing at
individual partitions. The UUID should be **quoted** to ensure that
the YAML can be parsed correctly. Also include the ``device_id`` which
is the bootloader view of the same device on this interface.

.. code-block:: yaml

 commands:
  connect: telnet localhost 6000
 media:
   usb:  # bootloader interface name
     UUID-required: True  # cubie1 is pretending to have two usb media attached
     SanDisk_Ultra:
       uuid: "usb-SanDisk_Ultra_20060775320F43006019-0:0"  # /dev/disk/by-id/
       device_id: 0  # the bootloader device id for this media on the 'usb' interface

There is **no** reasonable way for the device configuration to specify
the device node directly, as this may change from job to job depending
on the configuration of the deployed system.

.. _secondary_media_grub_sata:

Using Grub with SATA secondary media
************************************

Device dictionary
=================

.. code-block:: jinja

 {% set sata_uuid = 'ata-ST500DM002-1BD142_S2AKYFSN' %}
 {% set sata_label = 'ST500DM002' %}

* ``sata_uuid`` enables secondary media on a SATA interface for this device and
  is used to locate the device node as it appears to the kernel of the first
  deployment stage to allow LAVA to write the secondary image.

* ``sata_label`` will need to be specified in the test job to identify the
  SATA device to use for secondary media.

In this case, ``boot_part``, ``device_id``, ``grub_interface`` and
``uboot_interface`` are left as default values from the device-type template.

A more complete device dictionary would look like:

.. code-block:: jinja

 {% set sata_label = 'ST500DM002' %}
 {% set sata_uuid = 'ata-ST500DM002-1BD142_S2AKYFSN' %}
 {% set device_id = 0 %}
 {% set sata_interface = 'hd0' %}
 {% set boot_part = 1 %}

Device template example
=======================

https://git.lavasoftware.org/lava/lava/blob/master/lava_scheduler_app/tests/device-types/base.jinja2

.. note:: The duplication of ``uboot_interface`` and ``grub_interface`` is yet
   to be fixed in the dispatcher code. Currently, the same interface gets set
   for each for this specific item and one entry is simply unused at runtime.

.. code-block:: jinja

 {% if sata_uuid or sd_uuid or usb_uuid %}
  media:
 {% if sata_uuid %}
    sata:
      UUID-required: {{ uuid_required|default(True) }}
      {{ sata_label|default('ST160LM003') }}:
        uuid: {{ sata_uuid }}
        device_id: {{ sata_id|default(0) }}
        uboot_interface: {{ sata_interface|default('scsi') }}
        grub_interface: {{ sata_interface|default('hd0') }}
        boot_part: {{ boot_part|default(1) }}
 {% endif %} #  sata_uuid
 {% if sd_uuid %}
    sd:
      {{ sd_label }}:
        uuid: {{ sd_uuid }}
        device_id: {{ sd_device_id }}  # the bootloader device id for this media on the 'sd' interface
 {% endif %} #  sd_uuid
 {% if usb_uuid %}
    usb:
      {{ usb_label|default('SanDisk_Ultra') }}:
        uuid: {{ usb_uuid }}  # /dev/disk/by-id/
        device_id: {{ usb_device_id }}  # the bootloader device id for this media on the 'usb' interface
 {% endif %} # usb_uuid
 {% else %}
  pass:
 {%- endif %} # sata_uuid_sd_uuid_usb_uuid


Dispatcher configuration
========================

The device dictionary is combined with the template to create the actual
configuration sent to the worker:

.. code-block:: python

            'parameters': {
                'media': {
                    'sata': {
                        'ST500DM002': {
                            'boot_part': 1,
                            'device_id': 0,
                            'grub_interface': 'hd0',
                            'uboot_interface': 'scsi',
                            'uuid': 'ata-ST500DM002-1BD142_S2AKYFSN'
                        },
                        'UUID-required': True
                    }
                }
            }


Grub SATA Test Job submission
=============================

A test writer constructs a deployment action, after booting their chosen
primary deployment, selecting the relevant ``device_id`` and deployment
method (``to: sata``).

.. code-block:: yaml

 - deploy:
    namespace: satadeploy
    # secondary media - use the first deploy to get to a system which can deploy the next
    timeout:
      minutes: 30
    to: sata
    device: ST500DM002 # needs to be exposed in the device-specific UI


Using UBoot with USB secondary media
************************************

Device dictionary
=================

.. code-block:: jinja

 {% set usb_label = 'SanDiskCruzerBlade' %}
 {% set usb_uuid = 'usb-SanDisk_Cruzer_Blade_20060266531DA442AD42-0:0' %}
 {% set usb_device_id = 0 %}

Device template example
=======================

https://git.lavasoftware.org/lava/lava/blob/master/lava_scheduler_app/tests/device-types/base.jinja2

The template is the same as with :ref:`secondary_media_grub_sata` above.

Dispatcher configuration
========================

.. code-block:: python

    'parameters': {
      "media": {
        "usb": {
          "SanDiskCruzerBlade": {
            "uuid": "usb-SanDisk_Cruzer_Blade_20060266531DA442AD42-0:0",
            "device_id": 0
          },
          "UUID-required": true
        }
      },
    }

USB UBoot Test Job submission
=============================
A test writer constructs a deployment action, after booting their chosen
primary deployment, selecting the relevant ``device_id`` and deployment
method (``to: sata``).

.. code-block:: yaml

  - deploy:
     namespace: android
     timeout:
       minutes: 40
     to: usb
     os: android
     image:
         url: http://releases.linaro.org/members/arm/android/juno/16.09/juno.img.bz2
         compression: bz2
     device: SanDiskCruzerBlade
