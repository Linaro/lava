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
recognize is passed through unchanged. The output of rendering the template
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

.. index:: device dictionary - admin

.. _admin_device_dictionary:

Device dictionary
*****************

The device dictionary is a file. In the early stages, it can be very simple:

.. code-block:: jinja

 {% extends 'mytemplate.jinja2' %}

Comments may be used in device dictionary files, using the jinja syntax:

.. code-block:: jinja

 {# comment goes here #}

To remove a variable from a device dictionary, simply remove or comment out the
variable in the file.

It is recommended to keep device dictionary files in version control of some
kind to make it easier to track changes. The :ref:`administrative interface
<django_admin_interface>` tracks when and who changed the device dictionary but
not the detail of what was changed within it.

.. seealso::
   * :ref:`updating_device_dictionary_using_xmlrpc` and
     :ref:`updating_device_dictionary_on_command_line` for information on how to
     use the new file to update the device dictionary. (Needs superuser
     permissions on that instance.)
   * :ref:`device_dictionary_help`
   * :ref:`create_device_dictionary`
   * :ref:`configuring_serial_ports` and
   * :ref:`viewing_device_dictionary_content`.

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

 $ python3 -m unittest -vcf tests.lava_scheduler_app.test_base_templates.TestBaseTemplates.test_all_templates

.. seealso:: :ref:`integration_unit_test`

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

The functional tests repository
===============================

This git repository holds working examples of a range of different jobs for a
range of different devices. These jobs are routinely submitted as functional
tests of upcoming releases of the LAVA software.

https://git.lavasoftware.org/lava/functional-tests

Not every combination of deployment method or boot method can be expressed for
all supported devices but we aim to have at least one example of each
deployment method and each boot method on at least one supported device.

Check the ``standard`` directory for tests which use
:ref:`gold standard images <providing_gold_standard_files>`.

The lava-server unit test support
=================================

The `Jinja2`_ device-type templates here are used for the unit tests and also
become the default :term:`device type` templates when the packages are built.
The ``devices`` directory contains working device dictionary examples for these
device types.

https://git.lavasoftware.org/lava/lava/tree/master/lava_scheduler_app/tests

.. _extra_device_configuration:

Extra device configuration
**************************

There are a variety of optional elements of device configuration which need to
be considered at an administrator level.

.. seealso:: :ref:`device_dictionary_exported_parameters` and
   :ref:`test_device_info`

Providing permanent IPv4 addresses
==================================

Not all devices of one device-type will necessarily need fixed IPv4 addresses
to be configured in the device dictionary. Admins should consider the use of
:term`device tags`.

.. index:: storage, filesystem storage

.. _temporary_filesystem_storage:

Providing temporary filesystem storage
======================================

``lava-target-storage`` - Where devices have alternative storage media
fitted, the id of the block device can be exported. For example, this can help
provide temporary storage on the device when the test shell is running a
ramdisk or NFS. Some devices may provide a USB mass storage device which could
also be exported in this way.

Test writers need to be able to rely on getting a known block device, without
complications from enumeration at boot. If a second block device is desired,
the ``method`` label could simply append a unique ID, ``SATA-1``, ``SATA-2``
etc.

Only a **single** block device is supported per method. The ``method`` itself
is simply a label specified by the admin. Often it will relate to the interface
used by the block device, e.g. ``SATA`` or ``USB`` but it could be any string.
In the example below, ``UMS`` is the label used by the device (as an
abbreviation for USB Mass Storage).

.. caution:: Do **not** specify the ID for a partition as this **will change**
   if a test changes the partition table. There must be **no** files on the
   exported block device which are necessary for the device to reboot and
   execute another test job successfully. Not all devices can support such
   temporary storage.

.. seealso:: :ref:`device_dictionary_exported_parameters`

.. _dispatcher_configuration:

Extra dispatcher configuration
******************************

It is possible to supply dispatcher-specific configuration along with each test
job, by adding a configuration file on the master at
``/etc/lava-server/dispatcher.d/<hostname>.yaml``.

An example file exists in ``/usr/share/lava-dispatcher/dispatcher.yaml`` on
each worker.

Current support includes:

* Sets the dispatcher_ip, if the dispatcher has many IPs

.. code-block:: yaml

 # Only set this key, if this dispatcher has many IPs
 #dispatcher_ip: <this-dispatcher-ip>

* Sets the dispatcher_http_ip

.. code-block:: yaml

# Only set this key, if this dispatcher is running separately from slave httpd
# server or listening on a custom port.
#dispatcher_http_ip: <dispatcher-http-ip>:<port>

* Sets the dispatcher_nfs_ip

.. code-block:: yaml

# Only set this key, if this dispatcher is running separately from nfs server
# or listening on a custom port.
#dispatcher_nfs_ip: <dispatcher-nfs-ip>:<port>

* Sets the dispatcher_tftp_ip

.. code-block:: yaml

# Only set this key, if this dispatcher is running separately from tftpd server
# or listening on a custom port.
#dispatcher_tftp_ip: <dispatcher-tftp-ip>:<port>

* Sets the container creation path.

.. code-block:: yaml

 # Set this key, if you want to change the default lxc creation path
 # No trailing /
 # The default path is /var/lib/lxc
 #lxc_path: <custom-path>

.. seealso:: :ref:`keep_dispatcher_dumb`

* Add a prefix to tmp directories on a worker. This can be useful if
  a worker runs more than one ``lava-worker``, e.g. using docker.

.. code-block:: yaml

 # Prefix for all temporary directories
 # If this variable is set, the temporary files will be created in
 # /var/lib/lava/dispatcher/tmp/<prefix><job_id> instead of
 # /var/lib/lava/dispatcher/tmp/<job_id>
 #prefix: <prefix>

.. _dispatcher_environment:

Per dispatcher environment settings
===================================

Sometimes individual dispatchers can need different environment
settings, for example when a remote dispatcher is added then any
settings for ``HTTP_PROXY`` for other internal dispatchers cannot
apply to the remote dispatcher.

To support this, LAVA will check for dispatcher-specific environment
files. If the files exist, the content will be used instead of applying
any environment files for the entire instance.

In a similar manner to :ref:`dispatcher_configuration` above, the
configuration files are:

* ``/etc/lava-server/dispatcher.d/<hostname>/env.yaml``

* ``/etc/lava-server/dispatcher.d/<hostname>/env-dut.yaml``

If the dispatcher specific configuration files are not present,
lava-master will fallback to the environment files for the entire
instance:

* ``/etc/lava-server/env.yaml``

* ``/etc/lava-server/env-dut.yaml``

.. note:: when using dispatcher specific environment, it can be useful
    (but not mandatory) to move the dispatcher configuration from
    ``/etc/lava-server/dispatcher.d/<hostname>.yaml`` to
    ``/etc/lava-server/dispatcher.d/<hostname>/dispatcher.yaml``.

.. index:: pipeline device requirements

.. _pipeline_device_requirements:

Requirements for a LAVA device
******************************

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

* **Interruptible** - for example, ``uBoot`` must be configured to emit a
  recognizable message and wait for a sufficient number of seconds for a
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

.. seealso:: :ref:`Device requirements for integration <device_requirements>`

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

.. seealso:: :ref:`naming_conventions`

.. _Jinja2: http://jinja.pocoo.org/docs/dev/

.. _obtain_known_device_config:

Obtaining configuration of a known device
*****************************************

The simplest way to start is to download the working configuration of a device
of the same known device type from a configured LAVA instance. Browse to the
device and select "Device Dictionary". There is a download link for the
full rendered YAML or the original Jinja can be copied.

The original Jinja2 file will then need some tweaks for your local setup.
e.g. values like these will differ for every local LAVA instance.

.. code-block:: yaml

 commands:
    connect: telnet playgroundmaster 7018
    hard_reset: /usr/bin/pduclient --daemon services --hostname pdu09 --command reboot --port 04
    power_off: /usr/bin/pduclient --daemon services --hostname pdu09 --command off --port 04
    power_on: /usr/bin/pduclient --daemon services --hostname pdu09 --command on --port 04

.. seealso:: :ref:`power_commands`

Alternatively, the fully rendered YAML file, can be used to test jobs
on that device **but only from the command line on the worker**::

 $ sudo lava-run --device ./bbb01.yaml bbb-ramdisk.yaml --output-dir=/tmp/test/

A sample testjob definition can be downloaded from the same instance
as you obtained the device configuration.

.. _create_entry_known_type:

Creating a new device entry for a known device type
***************************************************

If this device does not already exist in the database of the instance, it will
need to be created by the admins using the :ref:`django_admin_interface`

If there are no devices of this device type in the instance, check that the
device type exists and create it if not. Don't worry about a health check at
this stage.

Create the device using the device type then set the worker hostname
for this device and save the changes.

.. _create_device_dictionary:

Creating a device dictionary for the device
*******************************************

.. seealso:: :ref:`updating_device_dictionary` to add a device dictionary to
   a new device.

Based upon an existing device
=============================

Download the device dictionary of an existing device in the original
``jinja2`` syntax, ready for modification. Compare with the existing
device dictionary for the device and modify the dictionary (`Jinja2
child template`_ format) to set the values required::

 {% extends 'beaglebone-black.jinja2' %}
 {% set power_off_command = '/usr/bin/pduclient --daemon services --hostname pdu09 --command off --port 04' %}
 {% set hard_reset_command = '/usr/bin/pduclient --daemon services --hostname pdu09 --command reboot --port 04' %}
 {% set connection_list = [‘uart0’] %}
 {% set connection_commands = {‘uart0’: ‘telnet playgroundmaster 7018’} %}
 {% set connection_tags = {‘uart0’: [‘primary’, 'telnet']} %}
 {% set power_on_command = '/usr/bin/pduclient --daemon services --hostname pdu09 --command on --port 04' %}

.. warning:: LAVA does not preserve history of a device dictionary, it is
   recommended that the files used to create the dictionaries are kept under
   version control.

.. _Jinja2 child template: http://jinja.pocoo.org/docs/dev/templates/#child-template

.. seealso:: :ref:`updating_device_dictionary`

.. _viewing_device_dictionary_content:

Viewing current device dictionary content
=========================================

View the device in the UI and click the link to the device dictionary.
The dictionary is displayed as Jinja2 by default. Click on "Rendered YAML" to
see the full device configuration as it would be sent to the worker.

.. index:: device dictionary - update

.. _updating_device_dictionary:

Updating a device dictionary
****************************

The populated dictionary now needs to be updated on the filesystem of the
instance.

All operations to update a device dictionary need to be done by a
superuser. The specified device must already exist in the database
**and** be assigned to an active worker to run test jobs -

.. seealso:: :ref:`create_entry_known_type`

* :ref:`updating_device_dictionary_using_xmlrpc`
* :ref:`updating_device_dictionary_on_command_line`

.. _updating_device_dictionary_on_command_line:

Using the command line
======================

Most commonly, a device dictionary is updated by placing a new file
onto the master, typically using configuration management tools like
salt_, puppet_ or ansible_.

.. _salt: https://www.saltstack.com/
.. _puppet: https://puppet.com/
.. _ansible: https://www.ansible.com/

The device dictionary exists as a ``jinja2`` file in
``/etc/lava-server/dispatcher-config/devices`` and can be updated by admins
with the necessary access.

.. _updating_device_dict_with_lavacli:

Using lavacli
=============

::

 $ lavacli -i <identity> devices dict get <hostname>

Other options when using ``get`` include:

*  ``field`` to only show the given sub-fields

* ``--context CONTEXT`` to pass a job context for template rendering

* ``--render`` to render the dictionary into a configuration (YAML).

Make changes within the `Jinja2 child template`_ syntax and then ``lavacli``
can be used to update a new device dictionary (replacing the previous device
dictionary).

The filename and extension of the ``<device_dict_file>`` are completely
arbitrary but you may find that your preferred editor has highlighting
support for jinja2::

 $ lavacli -i <identity> devices dict set <hostname> <device_dict_file>

.. seealso::
  * :ref:`device_dictionary_help`,
  * :ref:`create_device_dictionary`,
  * :ref:`configuring_serial_ports`,
  * :ref:`viewing_device_dictionary_content`

.. _updating_device_dictionary_using_xmlrpc:

Using XML-RPC
=============

Superusers can use ``import_device_dictionary`` to update a Jinja2 string for a
specified Device hostname:

.. code-block:: python

  # Python3
  import xmlrpc.client
  username = "USERNAME"
  token = "TOKEN_STRING"
  hostname = "HOSTNAME"
  protocol = "PROTOCOL"  # http or preferably https
  server = xmlrpc.client.ServerProxy("%s://%s:%s@%s/RPC2" % (protocol, username, token, hostname))
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
