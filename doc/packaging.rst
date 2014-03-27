Packaging lava-server for distributions
***************************************

The default install provides an Apache2 config suitable for
a LAVA server at ``http://localhost/`` once enabled.

Current versions of LAVA depend on django 1.4 and do not
operate with django 1.5. Patches exist to migrate to 1.6
and these have been applied to the current packages. If
building packages directly from LAVA upstream git, a
snapshot version of python-django **must** be used.

Debian-based distributions
##########################

To install all of LAVA on a single machine, use::

 $ sudo apt-get install postgresql postgresql-9.1
 $ wget http://snapshot.debian.org/archive/debian/20130224T223605Z/pool/main/p/python-django/python-django_1.4.5-1_all.deb
 $ sudo dpkg -i python-django_1.4.5-1_all.deb
 $ sudo apt-get install lava
 $ sudo a2dissite 000-default
 $ sudo a2ensite lava-server.conf
 $ sudo service apache2 restart

To install just the lava-server from the current packages
patched to support django1.6, use::

 $ sudo apt-get install lava-server
 $ sudo a2dissite 000-default
 $ sudo a2ensite lava-server.conf
 $ sudo service apache2 restart

This will install lava-dispatcher and lava-server but not
linaro-media-create and other optional packages.

Superuser
*********

A default lavaserver superuser is setup during package installation with
a random password. The default superuser is not the same as the lavaserver
system user nor the postgres user (despite the name)::

 $ sudo lava-server manage createsuperuser --username default --email=$EMAIL

This will prompt for name, email address and password.

You can always delete this user later, but at least it gets
you a default [sic] admin user with a password you know.

To change the password of the dummy superuser, login as this new superuser
at ``http://localhost/admin`` and select Users in the administrator interface.
Selecting lavaserver brings up the details of the installation superuser
and below the password field is a link to change the password without
needing to know the random password.

To delete the dummy superuser, login as this new superuser at 
``http://localhost/admin`` and select Users in the administrator interface.
Select lavaserver and click the `Delete` link at the bottom of the page.

Apache distribution support
***************************

::

 /etc/apache2/sites-available/lava-server.conf

Aimed at apache2.4 with comments for apache2.2 usage. Edit where necessary
and then enable and restart apache to use.

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
is desired, add the -b option to the helper command.

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

Adding initial data manually
############################

The three stages for a new device are:

#. Create a configuration file for this type of device on the dispatcher
#. Create a configuration for the this instance of the new type on the dispatcher
#. Populate the database so that the scheduler can submit jobs.

The current packaging for LAVA does not support separate dispatchers and
schedulers, so all three steps need to happen on the same machine. If you
want to use the initial data so that this install gets a KVM device, use::

 $ sudo apt-get install qemu-system-x86
 $ sudo cp /usr/share/lava-server/starterkvm.conf /etc/lava-dispatcher/devices/
 $ sudo lava-server manage loaddata /usr/share/lava-server/starterkvm.json

The example starterkvm.conf only supports NAT networking, so will not be
visible over TCP/IP to other devices when running tests.

An example KVM health check is packaged::

 /usr/share/doc/lava-server/examples/kvm-health.json

The contents of this JSON file should be added to the kvm device type
entry in the admin interface, with some adaptations:

#. Set a usable location in deploy_linaro_image
#. Ensure a suitable bundle stream exists, matching the stream variable

** TODO **

* The example KVM device needs an image to be tested.
* Document use of vmdebootstrap to create one and
  location to download one
* Provide a health check JSON and a first job JSON and where to look
  for JSON on other sites.
* Add JSON to create suitable lava-health bundle stream
  lava-dispatcher configuration - set the LAVA_SERVER_IP sensibly.

Instance name
*************
#. Only one instance can be running at any one time.
#. Instance templates share a common folder: /usr/share/lava-server/templates

Debian-based distributions
##########################

The Debian packaging currently configures LAVA to use the instance
name of default, with an option to upgrade an existing instance to
the packaged code by entering the name of the current instance when
asked by debconf.

Further information
===================

See also http://wiki.debian.org/LAVA

LAVA Components
***************

=============== =========================================
lava            meta-package for single instance setup
lava-server     apache and WSGI settings and HTML content
lava-dispatcher dispatches jobs to devices
=============== =========================================

Daemon renaming
###############

The main scheduler daemon is now explicitly named and only restarts
the scheduler daemon::

 $ sudo service lava-server restart

The web application itself is handled within apache, so to refresh
the code running behind the front end, use::

 $ sudo apache2ctl restart

WSGI debugging help
###################

https://code.google.com/p/modwsgi/wiki/DebuggingTechniques

If you get a 502 bad gateway, the uwsgi is probably not setup.

Developing LAVA on Debian
*************************

When using the packages to develop LAVA, there is a change to
the workflow compared to lava-deployment-tool buildouts.

.. _dev_builds:

Developer package build
#######################

The ``lava-dev`` package includes a helper script which is also present
in the source code in ``lava-server/share/``. The script requires a normal
Debian package build environment (i.e. ``dpkg-dev``) as well as the
build-dependencies of the package itself. The helper checks for package
dependencies using ``dpkg-checkbuilddeps`` which halts upon failure with
a message showing which packages need to be installed.

The helper is likely to improve in time but currently needs to know the
name of the package to build::

 $ /usr/share/lava-server/debian-dev-build.sh lava-server

The packages will be built in a temporary directory using a version string
based on the current git tag and the latest git commit hash. You can use
lightweight git tags to make incremental builds. The helper outputs the
location of all the built packages at the end of a successful build,
ready for use with ``$ sudo dpkg -i``.

.. note:: the helper does **not** install the packages for you, neither
          do the packages restart apache, although the ``lava-server``
          service will be restarted each time ``lava-server`` is
          installed or updated. Also note that ``lava-server`` builds
          packages which may conflict with each other - select the
          packages you already have installed.

Helpers for other distributions may be added in due course. Patches
welcome.

Quick fixes and testing
#######################

The paths to execute LAVA python scripts have changed and developing
LAVA based on packages has a different workflow.

Modified files can be copied to the equivalent path beneath ``/usr/share/pyshared/``
with sudo::

 $ sudo cp <git-path> /usr/share/pyshared/<git-path>

New files will need to be copied directly into the python path for the
module - or added by doing a local :ref:`dev_builds`. e.g. for python2.7
the path would be: ``/usr/lib/python2.7/dist-packages/<git-path>``. When
the package is built to include the new files, the old files will be
replaced with symlinks to the packaged files in ``/usr/share/pyshared``.

Viewing changes
===============

Different actions are needed for local changes to take effect,
depending on the type of file(s) updated:

==================== ==============================================
templates/\*/\*.html     next browser refresh (F5/Ctrl-R)
\*_app/\*.py             ``$ sudo apache2ctl restart``
\*_daemon/\*.py          ``$ sudo service lava-server restart``
==================== ==============================================
