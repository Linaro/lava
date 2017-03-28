.. index:: administrator guide

.. _admin_introduction:

Understanding the Pipeline - an administrator guide
###################################################

Introduction
************

Administrators who are familiar with the terminology of the pipeline and
templates can skip this section. If so, move on to
:ref:`pipeline_device_requirements`.

.. index:: templates

.. _device_type_templates:

Device type templates
*********************

Device type templates exist on the master in the
``/etc/lava-server/dispatcher-config/device-types/`` directory.

Although the example templates include jinja markup, the template itself is
YAML. The files use the ``.jinja2`` filename extension to make it easier for
editors to pick up the correct syntax highlighting, but whatever jinja does not
recognise is passed through unchanged. The output of rendering the template
**must always** be valid YAML.

If you are starting with just a single device of the relevant device type on a
particular instance, you don't need to include jinja markup in the device type
template - it can stay as YAML. Once you have more than one device or you are
considering contributing the template upstream, then you will need to support
the jinja markup. Jinja is used to:

* **avoid code duplication** - e.g. if a U-Boot command stanza is common to a
  number of device types (it does not have to be all devices capable of
  supporting U-Boot), then the common code needs to move into the base template
  and be inserted using jinja.

* **support multiple devices** - e.g. if the configuration needs serial numbers
  (for adb) or references to unique IDs (like UUID of storage devices) or IP
  addresses (for primary ssh connections) then these can be set as defaults in
  the template but need a variable name which is then overridden by the device
  dictionary.

* **support job-level overrides** - if a variable exists in the device type
  template and that variable is not set in the device dictionary, it becomes
  available for the job submission to set that variable.

Device dictionary
*****************

The device dictionary is a file. In the early stages, it can be very simple:

.. code-block:: jinja

 {% extends 'mytemplate.jinja2' %}

Comments may be used in device dictionary files but will not be stored in the
form of the dictionary created in the database. To use comments, use the jinja
syntax:

.. code-block:: jinja

 {# comment goes here #}

To remove a variable from a device dictionary, simply remove or comment out the
variable in the file. When the file is uploaded, the complete device dictionary
for that device is replaced with the content of the file.

It is recommended to keep device dictionary files in version control of some
kind to make it easier to track changes. The :ref:`administrative interface
<django_admin_interface>` tracks when and who changed the device dictionary but
not the detail of what was changed within it.

.. seealso:: :ref:`updating_device_dictionary_using_xmlrpc` and
   :ref:`updating_device_dictionary_on_command_line` for information on how to
   use the new file to update the device dictionary. (Needs superuser
   permissions on that instance.)

The `Jinja template documentation
<http://jinja.pocoo.org/docs/dev/templates/>`_ gives more information on jinja
syntax, although the examples are for HTML. Not all features of the jinja
template API can be supported in a device dictionary or device type template.
All of the logic within the template support, such as conditionals and the use
of blocks, is **only** to be done in the device type template.

.. _checking_templates:

Checking your templates
=======================

Whenever you modify a device type template, take care to respect the
indentation within the file. You can (temporarily) copy your template into
``lava_scheduler_app/tests/device-types`` and run the unit tests to verify that
the template can be parsed and rendered as valid YAML::

 $ ./lava_server/manage.py test lava_scheduler_app.tests.test_device.DeviceTypeTest

(As with all unit tests in ``lava-server``, this requires that ``lava-server``
is installed and configured on the machine running the test **and** that the
version of ``lava-server`` is recent enough such that its database schema is
compatible with the source code in the git checkout you are using. It does not
need to be `latest`, as long as it is `consistent` with the version installed.
If you are using production releases or jessie-backports, this is likely to
mean using ``git pull; git checkout release``.)

All contributions are **required** to pass this test (amongst others) and you
will not be able to successfully run jobs through your instance if it fails.

Finally, although the final configuration sent to the dispatcher will be
stripped of comments, it is **strongly recommended** to use **comments**
liberally in all your YAML files, including device type templates.

.. seealso:: :ref:`developer_jinja2_support` and
   :ref:`testing_templates_dictionaries`

Finding your way around the files
=================================

* Start with a device-type YAML file from the dispatcher which is similar to
  the one you want to support. Modify the YAML and verify using the `Online
  YAML parser <http://yaml-online-parser.appspot.com/?yaml=&type=json>`_ to
  make sure you **always** have valid YAML. This is the basis of your device
  type template. Use **comments** liberally, this is YAML remember.

* Compare that with the device-specific YAML which is what the dispatcher will
  actually see. Again, modify the YAML and verify using the `Online YAML parser
  <http://yaml-online-parser.appspot.com/?yaml=&type=json>`_ and make sure you
  **always** have valid YAML. This is what your device type template will need
  to produce.

* Identify variables which are device-specific and add **comments** about what
  will need to be handled when the device type template is used.

* Create a minimal device dictionary file which simply extends your initial
  device type template.

Information sources
*******************

The pipeline tests repository
=============================

This git repository holds working examples of a range of different jobs for a
range of different devices. These jobs are routinely submitted as functional
tests of upcoming releases of the LAVA software.

https://git.linaro.org/lava-team/refactoring.git

Not every combination of deployment method or boot method can be expressed for
all supported devices but we aim to have at least one example of each
deployment method and each boot method on at least one supported device.

Check the ``standard`` directory for tests which use
:ref:`gold standard images <providing_gold_standard_files>`.

The lava-dispatcher pipeline source code
========================================

As well as the source code, the ``devices`` and ``device_types`` directories in
this git repository contain YAML examples of device and device type
configuration. These are the raw forms which are used on the ``lava-dispatch``
command line and are useful for debugging and starting to create support for
your own devices.

https://git.linaro.org/lava/lava-dispatcher.git/tree/HEAD:/lava_dispatcher/pipeline

The lava-server unit test support
=================================

The `Jinja2`_ device-type templates here are used for the unit tests and also
become the default :term:`device type` templates when the packages are built.
The ``devices`` directory contains working device dictionary examples for these
device types.

https://git.linaro.org/lava/lava-server.git/tree/HEAD:/lava_scheduler_app/tests

.. _dispatcher_configuration:

Extra dispatcher configuration
******************************

It is possible to supply dispatcher-specific configuration along with each test
job, using the support in ``/etc/lava-server/dispatcher.d/``. The master will
read files in this directory which match the ``hostname`` of a known worker and
send the configuration to that worker.

An example file exists in ``/usr/share/lava-dispatcher/dispatcher.yaml`` on
each worker.

Current support includes:

* Sets the dispatcher_ip, if the dispatcher has many IPs

.. code-block:: yaml

 # Only set this key, if this dispatcher has many IPs
 #dispatcher_ip: <this-dispatcher-ip>

* Sets the container creation path.

.. code-block:: yaml

 # Set this key, if you want to change the default lxc creation path
 # No trailing /
 # The default path is /var/lib/lxc
 #lxc_path: <custom-path>

.. seealso:: :ref:`keep_dispatcher_dumb`

.. index:: pipeline device requirements

.. _pipeline_device_requirements:

Requirements for a pipeline device
**********************************

The new design makes less assumptions about the software support on the device
- principally only a *working* bootloader is required. The detail of *working*
includes but is not restricted to:

Hardware Requirements
=====================

* **Serial** - the principle method for connecting to any device during an
  automated test is serial. If a specific baud rate or particular UART
  connections are required, these must be declared clearly.

* **Network** - tests will need a method for delivering files to the device
  using the bootloader. Unless the bootloader has full support for wireless
  connections, physical ethernet is required.

* **Power** - automation requires that the board can be reliably reset by
  removing and then reapplying power. The board must support this in an
  automatic manner, without needing human intervention to press a reset button
  or similar. If such a button is present, each device will need to be modified
  to remove that barrier.

Software Requirements
=====================

* **Interruptable** - for example, ``uBoot`` must be configured to emit a
  recognisable message and wait for a sufficient number of seconds for a
  keyboard interrupt to get to a prompt.

* **Network aware** - most common deployments will need to pull files
  over a network using TFTP.

* **Stable** - the bootloader is the rescue system for the device and needs to
  be reliable - if the test causes a kernel panic or hardware lockup, resetting
  the board (by withdrawing and re-applying power) **must always** put the
  board back to the same bootloader operation as a standard power-on from cold.
  Note that USB serial connections can be a particular problem by allowing the
  device to continue to receive some power when the power supply itself is
  disconnected.

* **Configurable** - the bootloader needs to be configured over the serial
  connection during a test. Such configuration support needs to be robust and
  not lock up the device in case of invalid user input.

* **Accessible** - the bootloader will need to be updated by lab admins from
  time to time and this should be as trivial as possible, e.g. by simply
  copying a binary to a known location using an established protocol, not some
  board-specific routine requiring special software.

* **Flexible** - the bootloader should support as wide a range of deployments
  as possible, without needing changes to the bootloader itself. e.g. only
  having support for uncompressed kernel images would be a problem.

With such a bootloader installed on the device, the test writer has a wide
range of possible deployments and boot methods.

.. index:: pipeline support for devices of known type

.. _adding_known_device:

Adding support for a device of a known type
*******************************************

.. note:: Not all devices supported by the old dispatcher are currently
   supported in the pipeline. The configuration for the old dispatcher is very
   different to pipeline support - the intrinsic data of load addresses and
   ports remains but the layout has changed.

.. seealso:: :ref:`migrating_known_device_example`

A known device type for the pipeline means that a template file exists in
:file:`/etc/lava-server/dispatcher-config/device-types/`.

This is a `Jinja2`_ template which is turned into a complete YAML file when a
job needs to run on the device using settings in the :term:`device dictionary`.
Initially, you can work with a static YAML file and deal with how to use the
template and the dictionary later.

If this is the first device you are adding to this instance or the first device
using a new remote worker, this will need to be configured first. The
:term:`device type` and a Device entry using that type will need to be created
in the database. Once the device dictionary is working, the device can be
marked as a pipeline device in the admin interface. See
:ref:`create_entry_known_type`.

.. _Jinja2: http://jinja.pocoo.org/docs/dev/

.. _obtain_known_device_config:

Obtaining configuration of a known device
*****************************************

The simplest way to start is to download the working configuration of a device
of the same known device type using `XML-RPC
<https://staging.validation.linaro.org/api/help/#scheduler.get_pipeline_device_config>`_
or the :command:`lava-tool get-pipeline-device-config` command, see
:manpage:`lava-tool (1)`. This will (by default) write a new file in the
current working directory containing the configuration.

This YAML file will then need some tweaks for your local setup. e.g. these
values will differ for every local LAVA instance.

.. code-block:: yaml

 commands:
    connect: telnet playgroundmaster 7018
    hard_reset: /usr/bin/pduclient --daemon services --hostname pdu09 --command reboot --port 04
    power_off: /usr/bin/pduclient --daemon services --hostname pdu09 --command off --port 04
    power_on: /usr/bin/pduclient --daemon services --hostname pdu09 --command on --port 04

.. seealso:: :ref:`power_commands`

These values are similar to the existing dispatcher configuration and those
values can be transferred directly into the new structure.

With this local YAML file, you can now run pipeline jobs on that device **but
only from the lava-dispatch command line**::

 $ sudo lava-dispatch --target ./bbb01.yaml bbb-ramdisk.yaml --output-dir=/tmp/test/

.. note:: unlike the current dispatcher, the pipeline dispatcher takes a
   complete YAML file, with path, as the target. There is no default location
   for this file - in routine usage, the dispatcher has no permanent
   configuration for any pipeline device - the YAML is delivered to the
   dispatcher at the start of each job, generated from the :term:`device
   dictionary` and the template.

A sample pipeline testjob definition can be downloaded from the same instance
as you obtained the device configuration.

:command:`lava-tool` can also compare the device configuration YAML files using
the ``compare_device_conf`` option (see also :ref:`create_device_dictionary`.)
The output is a unified diff of the two YAML files::

 $ lava-tool compare-device-conf ./black02.yaml ./pipeline/devices/black01.yaml
 --- /home/neil/black02.yaml
 +++ /home/neil/pipeline/devices/black01.yaml

 @@ -1,5 +1,5 @@

  commands:
 -    connect: telnet localhost 6001
 +    connect: telnet localhost 6000

  device_type: beaglebone-black


The unified diff can also be piped to :command:`wdiff -d` to show as a word
diff::

 lava-tool compare-device-conf ./black02.yaml ./pipeline/devices/black01.yaml|wdiff -d

 [--- /home/neil/black02.yaml-]
 {+++ /home/neil/pipeline/devices/black01.yaml+}

 @@ -1,5 +1,5 @@

 commands:
     connect: telnet localhost [-6001-] {+6000+}

 device_type: beaglebone-black

.. note:: Unlike the current dispatcher, the pipeline does **not** care about
   the ``hostname`` of the device, the name of the file is unrelated and
   nothing about the job needs to know anything about the hostname (the
   :ref:`multinode_api` has support for making this information available to
   the test cases via the scheduler).

.. _create_entry_known_type:

Creating a new device entry for a known device type
***************************************************

If this device does not already exist in the database of the instance, it will
need to be created by the admins. This step is similar to how devices were
added to the database with the current dispatcher:

* Login to the Adminstration interface for the instance
* Click on Lava_Scheduler_App

If there are no devices of this device type in the instance, check that the
device type exists and create it if not. Don't worry about a health check at
this stage. (pipeline device health checks will follow in time.)

Create the device using the device type and ensure that the device has the
:command:`Pipeline device?` field checked. Pipeline devices need the worker
hostname to be set manually in the database, ensure this is correct, then save
the changes.

(A helper for this step will be prepared, in time.)

.. _create_device_dictionary:

Creating a device dictionary for the device
*******************************************

.. seealso:: :ref:`updating_device_dictionary` to add a device dictionary to
   a new pipeline device.

Existing devices
================

Admins are able to export the device dictionary of existing devices in the
original ``jinja2`` syntax, ready for modification.

The local YAML file downloaded using :command:`get-pipeline-device-config`,
whether XML-RPC or :file:`lava-tool` is the result of combining a device
dictionary and the Jinja2 template. To be able to submit and schedule jobs on
the device, the values from your modified file need to be entered into the
database of the instance you want to use to schedule the jobs. These values are
stored as a :term:`device dictionary`.

Compare with the existing device dictionary for the device. (If you do not have
access, ask the admins for an export of the dictionary - a helper for this step
will be available in time.)::

 $ lava-server manage device-dictionary --hostname black01 --export
 {% extends 'beaglebone-black.jinja2' %}
 {% set ssh_host = '172.16.200.165' %}
 {% set connection_command = 'telnet localhost 6000' %}

.. note:: the device dictionary can have a variety of values, according to the
   support available in the template specified in the **extends** setting.
   There is no mention of the hostname within the exported dictionary.

Now modify the dictionary (`Jinja2 child template`_ format) to set the values required::

 {% extends 'beaglebone-black.jinja2' %}
 {% set power_off_command = '/usr/bin/pduclient --daemon services --hostname pdu09 --command off --port 04' %}
 {% set hard_reset_command = '/usr/bin/pduclient --daemon services --hostname pdu09 --command reboot --port 04' %}
 {% set connection_command = 'telnet playgroundmaster 7018' %}
 {% set power_on_command = '/usr/bin/pduclient --daemon services --hostname pdu09 --command on --port 04' %}

.. warning:: the device dictionary parameters are **replaced** when the
   dictionary is updated, which is why the ``extends`` field is required. Be
   sure to merge any existing dictionary with the settings you need to change
   or the existing settings will be lost. LAVA does not preserve history of a
   device dictionary, it is recommended that the files used to create the
   dictionaries are kept under version control.

.. _Jinja2 child template: http://jinja.pocoo.org/docs/dev/templates/#child-template

.. seealso:: :ref:`updating_device_dictionary`

.. _viewing_device_dictionary_content:

Viewing current device dictionary content
=========================================

The admin interface displays the current device dictionary contents in the
Advanced Properties drop-down section of the Device detail view. e.g. for a
device called ``kvm01``, the URL in the admin interface would be
``/admin/lava_scheduler_app/device/kvm01/``, click Show on the Advanced
Properties section.

The Advanced Properties includes the device description and the device tags as
well as showing both the YAML formatting as it will be sent to the dispatcher
and the Jinja2 formatting used to update the device dictionary.

.. note:: The device dictionary is **not** editable in the Django admin
   interface due to constraints of the key value store and the django admin
   forms. This means that the device configuration for pipeline devices is
   managed using external files updating the details in the database using
   hooks. However, this does provide a simple mechanism to have version control
   over the device configuration with a simple mechanism to update the database
   and verify the database content.

.. index:: device dictionary update

.. _updating_device_dictionary:

Updating a device dictionary
****************************

The populated dictionary now needs to be updated in the database of the
instance.

All operations to update a device dictionary need to be done by a superuser.
The specified device must already exist in the database **and** be marked as a
pipeline device -

.. seealso:: :ref:`create_entry_known_type`

* :ref:`updating_device_dictionary_with_lava_tool`
* :ref:`updating_device_dictionary_using_xmlrpc`
* :ref:`updating_device_dictionary_on_command_line`

Developers can use :ref:`developer_access_to_django_shell` to update the
dictionary on the command line.

.. _updating_device_dictionary_with_lava_tool:

Using lava-tool
===============

.. note:: Ensure you update to the latest version of
   :ref:`lava_tool <lava_tool>` (>= 0.14) support to use
   the ``device-dictionary`` ``--update`` and ``--export``
   functions as superuser.

::

 $ lava-tool device-dictionary SERVER HOSTNAME --export > file.jinja2
 Please enter password for encrypted keyring:

The filename and extension are completely arbitrary but you may find that your
preferred editor has highlighting support for jinja2. The contents of the file
can be something like:

.. code-block:: jinja

 {% extends 'beaglebone-black.jinja2' %}
 {% set power_off_command = '/usr/bin/pduclient --daemon localhost --hostname pdu01 --command off --port 12' %}
 {% set hard_reset_command = '/usr/bin/pduclient --daemon localhost --hostname pdu01 --command reboot --port 12' %}
 {% set connection_command = 'telnet dispatcher01 7001' %}
 {% set power_on_command = '/usr/bin/pduclient --daemon localhost --hostname pdu01 --command on --port 12' %}

Make changes within the `Jinja2 child template`_ syntax and then ``lava-tool``
can be used to update a new device dictionary (replacing the previous device
dictionary)::

 $ lava-tool device-dictionary SERVER HOSTNAME --update file.jinja2
 Please enter password for encrypted keyring:
 Device dictionary updated for black01

Any line not included in the updated device dictionary will be removed from the
database for that device.

.. _updating_device_dictionary_using_xmlrpc:

Using XML-RPC
=============

Superusers can use ``import_device_dictionary`` to update a Jinja2 string for a
specified Device hostname:

.. code-block:: python

  import xmlrpclib
  username = "USERNAME"
  token = "TOKEN_STRING"
  hostname = "HOSTNAME"
  protocol = "PROTOCOL"  # http or preferably https
  server = xmlrpclib.ServerProxy("%s://%s:%s@%s/RPC2" % (protocol, username, token, hostname))
  server.scheduler.import_device_dictionary(device_hostname, jinja_string)

If the dictionary did not exist for this hostname, it will be created. The
XML-RPC call will return::

 Adding new device dictionary for black01

The dictionary is then updated. If the file is valid, the XML-RPC call will
return::

 Device dictionary updated for black01

Superusers can also export the existing jinja2 device information using
``export_device_dictionary`` for a known device hostname. This output can then
be edited and used to update the device dictionary information.

.. _updating_device_dictionary_on_command_line:

Using the command line
======================

::

 $ lava-server manage device-dictionary --hostname black01 --import black01.txt

If the dictionary did not exist for this hostname, you should see output::

 Adding new device dictionary for black01

If the dictionary does exist and the file is valid, you should see output::

 Device dictionary updated for black01

.. note:: The file itself has no particular need for an extension,
   :file:`.txt`, :file:`.jinja2`, :file:`.conf` and :file:`.yaml` are common,
   depending on your preferred editor / syntax / highlighting configuration.

Updating the device dictionary replaces any previous device dictionary
for the specified device.
