.. _adding_known_devices:

Adding known devices using the LAVA admin helpers
*************************************************

LAVA provides helper scripts to automate the creation of the initial
devices and bundle streams for the new instance. Devices added in this
way need to be already known to LAVA, i.e. a suitable device type
configuration needs to exist in ``/etc/lava-dispatcher/device-types/``

Adding a device to LAVA involves changes to the database and to the
dispatcher. Currently, the helper scripts do not directly support
adding devices to remote workers, although once added, a device can
easily be moved to a remote worker by copying the device configuration
file out of ``/etc/lava-dispatcher/devices/`` to the equivalent directory
of the worker.

To make it easier to automate the creation of a usable LAVA instance,
the helper can also create a default lab-health anonymous bundle stream
which can be used to collect results from the initial test jobs as a
check that the instance is working correctly. If a default bundle stream
is desired, add the ``-b`` option to the helper command.

The syntax for the add device helper is::

 $ sudo /usr/share/lava-server/add_device.py <TYPE> <NAME> [<options>]

For example, to add an iMX.53 device (for which the device_type in LAVA
is called ``mx53loco``) and to label that device as ``foo``, use::

 $ sudo /usr/share/lava-server/add_device.py mx53loco foo

This will create an initial device configuration file and add the device
to the database. In order to use the device for a job, a ``connection_command``
and probably a ``hard_reset_command`` are also needed in the device
configuration file. The helper supports connection commands based on
``ser2net`` and hard reset commands based on ``lavapdu``. ``ser2net`` exposes a serial
connection over a telnet interface at a specified port on the server.
lavapdu exposes a power distribution interface over a custom interface
and supports a number of APC PDU units.

Once all devices have been added, restart the LAVA server daemon::

 sudo service lava-server restart

Options
#######

::

  -h, --help            show this help message and exit
  -p PDUPORT, --pduport=PDUPORT
                        PDU Portnumber (ex: 04)
  -t TELNETPORT, --telnetport=TELNETPORT
                        ser2net port (ex: 4003)
  -b, --bundlestream    add a lab health bundle stream if no streams exist.
  -s, --simulate        output the data files without adding the device.

Defaults
########

``add_device.py`` currently sets the ``ser2net`` server as ``localhost``
and the ``lavapdu`` server as ``localhost``. These may need to be changed
in the device configuration file before the first jobs are submitted.

Examples
########

For example, if device ``foo`` is on ``ser2net`` port 4006, then the helper
can create a connection_command setting of ``telnet localhost 4006``::

 $ sudo /usr/share/lava-server/add_device.py mx53loco foo -t 4006

If the device foo is on PDU port 5, the helper can create a
``hard_reset_command`` setting of::

 /usr/bin/pduclient --daemon localhost --hostname pdu --command reboot --port 05

To combine all these steps into one command, use::

 $ sudo /usr/share/lava-server/add_device.py mx53loco foo -t 4006 -p 5 -b

This command will:

* check that mx53loco is supported on this instance
* check that device foo does not already exist
* check to see if any bundle streams exist
* add device foo as a type mx53loco to the database
* create a device configuration file /etc/lava-dispatcher/devices/foo.conf
* set the hostname and device_type of device foo in the configuration file
* add the connection_command telnet localhost 4006
* add the hard_reset_command for port 05
* create a default bundle stream /anonymous/lab-health/ if no streams exist

Checking the connection
=======================

Use the lava command (part of the ``lava-tool`` package) to test the
connection to the device::

 lava connect foo

If the connection works, use the Escape character (by default ``telnet``
uses Ctrl+]) and then ``quit`` at the ``telnet`` prompt to close the
connection (or other connections will be refused).

Adding initial data manually
****************************

The three stages for a new device are:

#. Create a configuration file for this type of device on the dispatcher
#. Create a configuration for the this instance of the new type on the dispatcher
#. Populate the database so that the scheduler can submit jobs.

The examples directory in the LAVA source contains a number of device
configuration files which you can adapt to your needs.

KVM support on x86 architectures
################################

Installing ``lava-dispatcher`` on ``amd64`` and ``i386`` devices
provides ``qemu-system-x86`` to allow the use of KVM devices on these
architectures. KVM support for ARM devices is an ongoing project within
Linaro.

Example on Debian::

 $ sudo cp examples/devices/kvm.conf /etc/lava-dispatcher/devices/
 $ sudo lava-server manage loaddata examples/models/kvm.json

The example kvm.conf only supports NAT networking, so will not be
visible over TCP/IP to other devices when running tests.

An example KVM health check is in the lava-server source code::

 examples/health-checks/kvm-health.json

The contents of this JSON file should be added to the kvm device type
entry in the admin interface, with some adaptations:

#. Set a usable location in deploy_linaro_image
#. Ensure a suitable bundle stream exists, matching the stream variable

See :ref:`deploy_kvm`

