Administrator use cases
#######################

.. index:: pipeline device requirements

.. _pipeline_device_requirements:

Requirements for a pipeline device
**********************************

The new design makes less assumptions about the software support on the
device - principally only a *working* bootloader is required. The detail
of *working* includes but is not restricted to:

Hardware Requirements
=====================

* **Serial** - the principle method for connecting to any device during
  an automated test is serial. If a specific baud rate or particular
  UART connections are required, these must be declared clearly.
* **Network** - tests will need a method for delivering files to the
  device using the bootloader. Unless the bootloader has full support
  for wireless connections, physical ethernet is required.
* **Power** - automation requires that the board can be reliably reset
  by removing and then reapplying power. The board must support this in
  an automatic manner, without needing human intervention to press a
  reset button or similar. If such a button is present, each device will
  need to be modified to remove that barrier.

Software Requirements
=====================

* **Interruptable** - for example, ``uBoot`` must be configured to emit
  a recognisable message and wait for a sufficient number of seconds for
  a keyboard interrupt to get to a prompt.
* **Network aware** - most common deployments will need to pull files
  over a network using TFTP.
* **Stable** - the bootloader is the rescue system for the device and
  needs to be reliable - if the test causes a kernel panic or hardware
  lockup, resetting the board (by withdrawing and re-applying power)
  **must always** put the board back to the same bootloader operation
  as a standard power-on from cold. Note that USB serial connections
  can be a particular problem by allowing the device to continue to
  receive some power when the power supply itself is disconnected.
* **Configurable** - the bootloader needs to be configured over the
  serial connection during a test. Such configuration support needs to
  be robust and not lock up the device in case of invalid user input.
* **Accessible** - the bootloader will need to be updated by lab admins
  from time to time and this should be as trivial as possible, e.g. by
  simply copying a binary to a known location using an established
  protocol, not some board-specific routine requiring special software.
* **Flexible** - the bootloader should support as wide a range of
  deployments as possible, without needing changes to the bootloader
  itself. e.g. only having support for uncompressed kernel images would
  be a problem.

With such a bootloader installed on the device, the test writer has a
wide range of possible deployments and boot methods.

.. index:: pipeline support for devices of known type

.. _adding_known_device:

Adding support for a device of a known type
*******************************************

.. note:: Not all devices supported by the old dispatcher are currently
   supported in the pipeline. The configuration for the old dispatcher
   is very different to pipeline support - the intrinsic data of load
   addresses and ports remains but the layout has changed.

A known device type for the pipeline means that a template file exists in
:file:`/etc/lava-server/dispatcher-config/device-types/`.

This is a `Jinja2`_ template which is turned into a complete YAML file
when a job needs to run on the device using settings in the
:term:`device dictionary`. Initially, you can work with a
static YAML file and deal with how to use the template and the
dictionary later.

If this is the first device you are adding to this instance or the
first device using a new remote worker, this will need to be configured
first. The :term:`device type` and a Device entry using that type will
need to be created in the database. Once the device dictionary is
working, the device can be marked as a pipeline device in the admin
interface. See :ref:`create_entry_known_type`.

.. _Jinja2: http://jinja.pocoo.org/docs/dev/

.. _obtain_known_device_config:

Obtaining configuration of a known device
=========================================

The simplest way to start is to download the working configuration of
a device of the same known device type using
`XMLRPC <https://staging.validation.linaro.org/api/help/#scheduler.get_pipeline_device_config>`_
or the :command:`lava-tool get-pipeline-device-config` command,
see :manpage:`lava-tool (1)`. This will (by default) write a new file
in the current working directory containing the configuration.

This YAML file will then need some tweaks for your local setup. e.g.
these values will differ for every local LAVA instance.

.. code-block:: yaml

 commands:
    connect: telnet playgroundmaster 7018
    hard_reset: /usr/bin/pduclient --daemon services --hostname pdu09 --command reboot --port 04
    power_off: /usr/bin/pduclient --daemon services --hostname pdu09 --command off --port 04
    power_on: /usr/bin/pduclient --daemon services --hostname pdu09 --command on --port 04

These values are similar to the existing dispatcher configuration and
those values can be transferred directly into the new structure.

With this local YAML file, you can now run pipeline jobs on that device
**but only from the lava-dispatch command line**::

 $ sudo lava-dispatch --target ./bbb01.yaml bbb-ramdisk.yaml --output-dir=/tmp/test/

.. note:: unlike the current dispatcher, the pipeline dispatcher takes
   a complete YAML file, with path, as the target. There is no default
   location for this file - in routine usage, the dispatcher has no
   permanent configuration for any pipeline device - the YAML is delivered
   to the dispatcher at the start of each job, generated from the
   :term:`device dictionary` and the template.

A sample pipeline testjob definition can be downloaded from the same
instance as you obtained the device configuration.

:command:`lava-tool` can also compare the device configuration YAML
files using the ``compare_device_conf`` option (see also
:ref:`create_device_dictionary`.) The output is a unified diff of
the two YAML files::

 $ lava-tool compare-device-conf ./black02.yaml ./pipeline/devices/black01.yaml
 --- /home/neil/black02.yaml
 +++ /home/neil/pipeline/devices/black01.yaml

 @@ -1,5 +1,5 @@

  commands:
 -    connect: telnet localhost 6001
 +    connect: telnet localhost 6000

  device_type: beaglebone-black


The unified diff can also be piped to :command:`wdiff -d` to show
as a word diff::

 lava-tool compare-device-conf ./black02.yaml ./pipeline/devices/black01.yaml|wdiff -d

 [--- /home/neil/black02.yaml-]
 {+++ /home/neil/pipeline/devices/black01.yaml+}

 @@ -1,5 +1,5 @@

 commands:
     connect: telnet localhost [-6001-] {+6000+}

 device_type: beaglebone-black

.. note:: Unlike the current dispatcher, the pipeline does **not** care
   about the ``hostname`` of the device, the name of the file is unrelated
   and nothing about the job needs to know anything about the hostname
   (the :ref:`multinode_api` has support for making this information
   available to the test cases via the scheduler).

.. _create_entry_known_type:

Creating a new device entry for a known device type
===================================================

If this device does not already exist in the database of the instance,
it will need to be created by the admins. This step is similar to
how devices were added to the database with the current dispatcher:

* Login to the Adminstration interface for the instance
* Click on Lava_Scheduler_App

If there are no devices of this device type in the instance, check that
the device type exists and create it if not. Don't worry about a health
check at this stage. (pipeline device health checks will follow in time.)

Create the device using the device type and ensure that the device has
the :command:`Pipeline device?` field checked. Pipeline devices need the
worker hostname to be set manually in the database, ensure this is
correct, then save the changes.

(A helper for this step will be prepared, in time.)

.. _create_device_dictionary:

Creating a device dictionary for the device
===========================================

The local YAML file downloaded using :command:`get-pipeline-device-config`,
whether XMLRPC or :file:`lava-tool` is the result of combining a device
dictionary and the Jinja2 template. To be able to submit and schedule jobs
on the device, the values from your modified file need to be entered into
the database of the instance you want to use to schedule the jobs. These
values are stored as a :term:`device dictionary`.

Compare with the existing device dictionary for the device. (If you do
not have access, ask the admins for an export of the dictionary - a helper
for this step will be available in time.)::

 $ lava-server manage device-dictionary --hostname black01 --export
 {% extends 'beaglebone-black.yaml' %}
 {% set ssh_host = '172.16.200.165' %}
 {% set connection_command = 'telnet localhost 6000' %}

.. note:: the device dictionary can have a variety of values, according
   to the support available in the template specified in the **extends**
   setting. There is no mention of the hostname within the exported
   dictionary.

Now modify the dictionary (jinja2 format) to set the values required::

 {% extends 'beaglebone-black.yaml' %}
 {% set power_off_command = '/usr/bin/pduclient --daemon services --hostname pdu09 --command off --port 04' %}
 {% set hard_reset_command = '/usr/bin/pduclient --daemon services --hostname pdu09 --command reboot --port 04' %}
 {% set connection_command = 'telnet playgroundmaster 7018' %}
 {% set power_on_command = '/usr/bin/pduclient --daemon services --hostname pdu09 --command on --port 04' %}

.. warning:: the device dictionary parameters are **replaced** when the
   dictionary is updated, which is why the ``extends`` field is required.
   Be sure to merge any existing dictionary with the settings you need to
   change or the existing settings will be lost. LAVA does not preserve history
   of a device dictionary, it is recommended that the files used to create the
   dictionaries are kept under version control.

.. _viewing_device_dictionary_content:

Viewing current device dictionary content
-----------------------------------------

The admin interface displays the current device dictionary contents
in the Advanced Properties drop-down section of the Device detail view.
e.g. for a device called ``kvm01``, the URL in the admin interface would be
``/admin/lava_scheduler_app/device/kvm01/``, click Show on the Advanced
Properties section.

The Advanced Properties includes the device description and the device tags
as well as showing both the YAML formatting as it will be sent
to the dispatcher and the Jinja2 formatting used to update the device
dictionary.

.. note:: The device dictionary is **not** editable in the Django admin
   interface due to constraints of the key value store and the django
   admin forms. This means that the device configuration for pipeline
   devices is managed using external files updating the details in the
   database using hooks. However, this does provide a simple mechanism
   to have version control over the device configuration with a simple
   mechanism to update the database and verify the database content.

Updating a device dictionary using XMLRPC
-----------------------------------------

The populated dictionary now needs to be updated in the database
of the instance. Superusers can update the device dictionary over
XMLPRC or developers can use :ref:`developer_access_to_django_shell`
to update the dictionary on the command line.

.. note:: Newer version of :ref:`lava_tool <lava_tool>` (>= 0.14) support
   the ``import-device-dictionary`` and ``export-device-dictionary``
   functions.

Superusers can use ``import_device_dictionary`` to update a Jinja2 string
for a specified Device hostname (the Device must already exist in the
database - see :ref:`adding_known_devices`).

If the dictionary did not exist for this hostname, it will be created.
You should see output::

 Adding new device dictionary for black01

The dictionary is then updated. If the file is valid, you should see output::

 Device dictionary updated for black01

Superusers can also export the existing jinja2 device information using
``export_device_dictionary`` for a known device hostname. This output
can then be edited and imported to update the device dictionary
information.

Updating a device dictionary on the command line
-------------------------------------------------

::

 $ lava-server manage device-dictionary --hostname black01 --import black01.txt

If the dictionary did not exist for this hostname, you should see output::

 Adding new device dictionary for black01

If the dictionary does exist and the file is valid, you should see output::

 Device dictionary updated for black01

.. note:: The file itself has no particular need for an extension,
   :file:`.txt`, :file:`.jinja2`, :file:`.conf` and :file:`.yaml` are
   common, depending on your preferred editor / syntax / highlighting
   configuration.
