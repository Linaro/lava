.. index:: advanced installation topics, laptop, virtual machine

.. _advanced_installation:

Advanced Installation Topics
############################

The basic :ref:`installation` guide should be a good start for most users
installing LAVA. For more advanced users, here is much more information and
recommendations for administrators.

Requirements to Consider Before Installing LAVA
***********************************************

.. _laptop_requirements:

Laptops
=======

Be careful with laptop installs, particularly if you are using health checks.
It is all too easy for a health check to take the device offline just because
the laptop was suspended or without an internet connection at the relevant
moment.

Laptops also have limitations on device availability but are routinely used as
development platforms and can support QEMU devices without problems.

.. _virtual_machine_requirements:

Virtual Machines
================

LAVA installs inside a virtual machine (or container) have particular
constraints. A QEMU device or container may suffer from being executed within
the constraints of the existing virtualisation and other devices may need USB
device nodes to be passed through to the VM. Depending on the VM, it is also
possible that storage space for the logs may become an issue.

.. _workload_requirements:

Workload
========

Consider the expected load of the master and each of the workers:

* The workload on the **master** primarily depends on:

  #. the visibility of the instance,
  #. the number of users,
  #. the average number of jobs in the queue and
  #. the total number of devices attached across all the workers connected to
     this master.

* The workload on the **worker** involves a range of tasks, scaling
  with the number of devices attached to the worker:

  #. doing a lot of synchronous I/O,
  #. decompression of large files
  #. serving large files over TFTP or HTTP and
  #. git clone operations.

ARMv7 devices can serve as a master or worker but SATA support is **strongly**
recommended along with 2GB of RAM.

Localhost
=========

LAVA expects to be the primary host on the master. This has improved with V2
but unless your instance is V2-only, you may experience problems or require
additional configuration to use LAVA as a virtual host.

.. index:: infrastructure requirements

.. _infrastructure_requirements:

Other infrastructure
====================

LAVA will need other services to be available, either using separate tools on
the same machines or as separate hardware. This list is not exhaustive.

.. index:: power control infrastructure, automated power control

.. _power_control_infrastructure:

Remote power control
--------------------

Automated power control using a (:abbr:`PDU (Power Distribution Unit)`) is the
most common issue with new LAVA labs. Hardware can be difficult to obtain and
configuring the remote power control can require custom scripting. There is no
single device for all use cases and a wide variety of possible solutions,
depending on your needs. Take the time to research the issues and ask on the
:ref:`lava_users` mailing list.

.. index:: serial console support, serial console server

.. _serial_console_support:

Serial console support
----------------------

Once more than a handful of devices are attached to a worker it becomes
necessary to have a separate unit to handle the serial connectivity, turning
serial ports into TCP ports. Bespoke serial console servers can be expensive,
alternatives include ARMv7 boards with ``ser2net`` installed but the USB and
ethernet support needs to be reliable.

.. _network_switch_infrastructure:

Network switches
----------------

Simple unmanaged switches will work for small LAVA labs but managed switches
are essential to use :ref:`vland_in_lava` and will also be important for medium
to large LAVA labs.

.. _power_supply_ups:

Power supply
------------

:abbr:`UPS (Uninterruptible Power Supply)` allows the entire lab to cope with
power interruptions. Depending on the budget, this could be a small UPS capable
of supporting the master and the worker for 10 minutes or it could be a
combination of larger UPS units and a generator.

.. _fileserver_infrastructure:

Fileserver
----------

The master is **not** the place to be putting build artefacts, the worker will
download those later to a temporary location when the job starts. The
development builds and the files built to support the LAVA test need to happen
on a suitably powerful machine to match the expectations of the CI loop and the
developers.

Shelving and racks
------------------

Quite quickly, the tangle of power cables, network cables, serial cables,
devices, switches and other infrastructure will swamp a desk etc. For even a
small lab of a handful of devices, a set of shelves or a wall-mounted rack is
going to make things a lot easier to manage.

.. _more_installation_types:

Recommended Installation Types
******************************

Single instance
===============

The basic guide shows how to install ``lava-server`` and ``lava-dispatcher`` on
a single machine. This kind of instance can later be migrated to the same
master with one or more remote workers when more devices become available.
Single instance installs are useful for local development, testing inside
virtual machines and small scale testing.

Limitations
-----------

The main limitation of a single instance is the number of devices which can be
supported and the need to connect some devices directly to that machine. The
solution then is to allocate a new machine as a worker and move some devices
onto the worker.

Master with one or more remote workers
======================================

Any single instance of LAVA V2 can be extended to work with one or more workers
which only need ``lava-dispatcher`` installed.

.. seealso:: :ref:`Installing a worker <installing_pipeline_worker>`

Authentication and encryption
-----------------------------

When the worker is on the same subnet and behind the same firewall as the
master, admins can choose to use workers without authentication. In all other
cases, the ZMQ socket used for passing control messages to the worker and the
socket used to pass logs back to the master need to use authentication which
will then turn on :ref:`encryption <zmq_curve>`.

Once authentication is configured on the master, one or more workers can be
:ref:`prepared <installing_pipeline_worker>` and also configured to use
authentication.

Other installation notes
************************

.. _automated_installation:

Automated installation
======================

Using debconf pre-seeding with Debian packages
----------------------------------------------

Debconf can be easily automated with a text file which contains the answers for
debconf questions - just keep the file up to date if the questions change. For
example, to preseed a worker install::

 # cat preseed.txt
 lava-server   lava-worker/db-port string 5432
 lava-server   lava-worker/db-user string lava-server
 lava-server   lava-server/master boolean false
 lava-server   lava-worker/master-instance-name string default
 lava-server   lava-worker/db-server string snagglepuss.codehelp
 lava-server   lava-worker/db-pass string werewolves
 lava-server   lava-worker/db-name string lava-server

Insert the preseed information into the debconf database::

 debconf-set-selections < preseed.txt

::

 # debconf-show lava-server
 * lava-worker/master-instance-name: default
 * lava-server/master: false
 * lava-worker/db-pass: werewolves
 * lava-worker/db-port: 5432
 * lava-worker/db-name: lava-server
 * lava-worker/db-server: snagglepuss.codehelp
 * lava-worker/db-user: lava-server

The strings available for seeding are in the Debian packaging for the
relevant package, in the ``debian/<PACKAGE>.templates`` file.

* http://www.debian-administration.org/articles/394
* http://www.fifi.org/doc/debconf-doc/tutorial.html

.. _branding:

LAVA server branding support
============================

The icon, link, alt text, bug URL and source code URL of the LAVA link on each
page can be changed in the settings ``/etc/lava-server/settings.conf`` (JSON
syntax)::

   "BRANDING_URL": "http://www.example.org",
   "BRANDING_ALT": "Example site",
   "BRANDING_ICON": "https://www.example.org/logo/logo.png",
   "BRANDING_HEIGHT": 26,
   "BRANDING_WIDTH": 32,
   "BRANDING_BUG_URL": "http://bugs.example.org/lava",
   "BRANDING_SOURCE_URL": "https://github.com/example/lava-server",

Admins can include a sentence describing the purpose of the instance to give more
detail than is available via the instance name. This will be added in a paragraph
on the home page under "About the {{instance_name}} LAVA instance"::

   "BRANDING_MESSAGE": "Example site for local testing",

If the icon is available under the django static files location, this location
can be specified instead of a URL::

   "BRANDING_ICON": "path/to/image.png",

There are limits to the size of the image, approximately 32x32 pixels, to avoid
overlap.

The ``favicon`` is configurable via the Apache configuration::

 Alias /favicon.ico /usr/share/lava-server/static/lava-server/images/logo.png

.. index:: security upgrades, unattended upgrades

.. _unattended_upgrades:

Unattended upgrades
===================

Debian provides a package which can be installed to keep the computer current
with the latest security (and other) updates automatically. If you plan to use
it, you should have some means to monitor your systems, such as installing the
``apt-listchanges`` package and configuring it to send you emails about
updates and a working email configuration on each machine.

This service is recommended for LAVA instances but is not part of LAVA itself.
Please read the Debian wiki instructions carefully. If unattended upgrades are
used, ensure that the master and all workers are similarly configured and this
includes creating a working email configuration on each worker.

.. seealso:: https://wiki.debian.org/UnattendedUpgrades

Example changes
---------------

``/etc/apt/apt.conf.d/50unattended-upgrades``

The default installation of ``unattended-upgrades`` enables automatic upgrades
for all security updates::

   Unattended-Upgrade::Origins-Pattern {

        "origin=Debian,codename=jessie,label=Debian-Security";
   };


Optionally add automatic updates from the :ref:`lava_repositories` if those are
in use::

   Unattended-Upgrade::Origins-Pattern {

        "origin=Debian,codename=jessie,label=Debian-Security";
        "origin=Linaro,label=Lava";
   };

Other repositories can be added to the upgrade by checking the output of
``apt-cache policy``, e.g.::

 release v=8.1,o=Linaro,a=unstable,n=sid,l=Lava,c=main

Relates to an origin (``o``) of ``Linaro`` and a label (``l``) of ``Lava``.

When configuring unattended upgrades for the master or any worker which still
supports LAVA V1, PostgreSQL will need to be added to the
``Package-Blacklist``. Although services like PostgreSQL do get security
updates and these updates **are** important to apply, ``unattended-upgrades``
does not currently restart other services which are dependent on the service
being upgraded. Admins still need to watch for security updates to PostgreSQL
and apply the update manually, restarting services like ``lavapdu-runner``,
``lava-master`` and ``lava-server``::

   Unattended-Upgrade::Package-Blacklist {
        "postgresql-9.4";
   };

Email notifications also need to be configured.

::

   Unattended-Upgrade::Mail "admins@myinstance.org";

   Unattended-Upgrade::MailOnlyOnError "true";

With these changes to ``/etc/apt/apt.conf.d/50unattended-upgrades``, the rest
of the setup is as described on the Debian wiki.

https://wiki.debian.org/UnattendedUpgrades#automatic_call_via_.2Fetc.2Fapt.2Fapt.conf.d.2F20auto-upgrades

.. index:: event notifications - configuration

.. _configuring_event_notifications:

Configuring event notifications
===============================

Event notifications **must** be configured before being enabled.

* All changes need to be configured in ``/etc/lava-server/settings.conf`` (JSON
  syntax).

* Ensure that the ``EVENT_TOPIC`` is **changed** to a string which the
  receivers of the events can use for filtering.

  * Instances in the Cambridge lab use a convention which is similar to DBus -
    the top level URL of the instance is reversed.

* Ensure that the ``EVENT_SOCKET`` is visible to the receivers - change the
  default port of ``5500`` if required.

* Enable event notifications by setting ``EVENT_NOTIFICATION`` to ``true``

When changing the configuration, you should restart the corresponding services:

.. code-block:: shell

  service lava-publisher restart
  service lava-master restart
  service lava-server restart
  service lava-server-gunicorn restart

The default values for the event notification settings are:

.. code-block:: python

 "EVENT_TOPIC": "org.linaro.validation",
 "INTERNAL_EVENT_SOCKET": "ipc:///tmp/lava.events",
 "EVENT_SOCKET": "tcp://*:5500",
 "EVENT_NOTIFICATION": false,
 "EVENT_ADDITIONAL_SOCKETS": []

The ``INTERNAL_EVENT_SOCKET`` does not usually need to be changed.

Services which will receive these events **must** be able to connect to the
``EVENT_SOCKET``. Depending on your local configuration, this may involve
opening the specified port on a firewall.

With this configuration, LAVA will publish events to the ``EVENT_SOCKET`` only,
using a `zmq PUB socket <http://api.zeromq.org/4-2:zmq-socket#toc7>`__.

.. note:: This type of socket is realy powerful to publish messages to a large
   audience. However, In case of a network breakage, the client nor the server
   will notice that the connection was lost and might miss events.

To publish events on an unrelable network (like Internet) and for a small set of
known listeners, you can use the ``EVENT_ADDITIONAL_SOCKETS``. The publisher
will connect to this list of endpoints with a `zmq PUSH socket
<http://api.zeromq.org/4-2:zmq-socket#toc12>`__ for each endpoints.

These sockets are configured to keep a queue of 10000 messages for each
endpoints. No messages will be lost, as long as less than 10000 messages are
waiting in the queue.

.. seealso:: :ref:`publishing_events`
