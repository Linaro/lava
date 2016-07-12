.. _advanced_installation:

Advanced Installation Topics
############################

The basic :ref:`installation` guide should be a good start for most users
installing LAVA. For more advanced users, here is much more
information and recommendations for administrators.

Requirements to Consider Before Installing LAVA
***********************************************

.. _laptop_requirements:

Laptops
=======

Be careful with laptop installs, particularly if you are using
health checks. It is all too easy for a health check to take the
device offline just because the laptop was suspended or without an
internet connection at the relevant moment.

Laptops also have limitations on device availability but are
routinely used as development platforms and can support QEMU devices
without problems.

.. _virtual_machine_requirements:

Virtual Machines
================

LAVA installs inside a virtual machine (or container) have particular
constraints. A QEMU device or container may suffer from being executed
within the constraints of the existing virtualisation and other devices
may need USB device nodes to be passed through to the VM. Depending on
the VM, it is also possible that storage space for the logs may become
an issue.

.. _workload_requirements:

Workload
========

Consider the expected load of the master and each of the slaves:

* The workload on the **master** primarily depends on:

  #. the visibility of the instance,
  #. the number of users,
  #. the average number of jobs in the queue and
  #. the total number of devices attached across all the slaves
     connected to this master.

* The workload on the **worker** involves a range of tasks, scaling
  with the number of devices attached to the worker:

  #. doing a lot of synchronous I/O,
  #. decompression of large files
  #. serving large files over TFTP or HTTP and
  #. git clone operations.

ARMv7 devices can serve as a master or worker but SATA support is
**strongly** recommended along with 2GB of RAM.

Localhost
=========

LAVA expects to be the primary host on the master. This has improved
with V2 but unless your instance is V2-only, you may experience problems
or require additional configuration to use LAVA as a virtual host.

Other infrastructure
====================

LAVA will need other services to be available, either using separate
tools on the same machines or as separate hardware. This list is not
exhaustive.

* **Remote power control** (:abbr:`PDU (Power Distribution Unit)`) -
  the most common issue with new LAVA labs is obtaining and then
  configuring the remote power control. There is no single device for
  all use cases and a wide variety of possible solutions, depending on
  your needs. Take the time to research the issues and ask on the
  :ref:`lava_users` mailing list.
* **Serial console support** - once more than a handful of devices are
  attached to a worker it becomes necessary to have a separate unit
  to handle the serial connectivity, turning serial ports into TCP
  ports. Bespoke serial console servers can be expensive, alternatives
  include ARMv7 boards with ``ser2net`` installed but the USB and ethernet
  support needs to be reliable.
* **Network switches** - simple unmanaged switches will work for small
  LAVA labs but managed switches are essential to use :ref:`vland_in_lava`
  and will also be important for medium to large LAVA labs.
* **Power supply** (:abbr:`UPS (Uninterruptible Power Supply)`) - the entire
  lab needs to be able to cope with power interruptions. Depending on the
  budget, this could be a small UPS capable of supporting the master and
  the worker for 10 minutes or it could be a combination of larger UPS
  units and a generator.
* **Fileserver** - the master is **not** the place to be putting build
  artefacts, the worker will download those later to a temporary
  location when the job starts. The development builds and the files
  built to support the LAVA test need to happen on a suitably powerful
  machine to match the expectations of the CI loop and the developers.
* **Shelving and racks** - quite quickly, the tangle of power cables,
  network cables, serial cables, devices, switches and other infrastructure
  will swamp a desk etc. For even a small lab of a handful of devices, a
  set of shelves or a wall-mounted rack is going to make things a lot
  easier to manage.

Architecture
============

.. include:: architecture-v2.rsti

.. _more_installation_types:

Recommended Installation Types
******************************

Single instance
===============

The basic guide shows how to install ``lava-server`` and ``lava-dispatcher``
on a single machine. This kind of instance can later be migrated to
the same master with one or more remote slaves when more devices become
available. Single instance installs are useful for local development,
testing inside virtual machines and small scale testing.

Limitations
-----------

The main limitation of a single instance is the number of devices which
can be supported and the need to connect some devices directly to that
machine. The solution then is to allocate a new machine as a slave and
move some devices onto the slave.

Master with one or more remote slaves
=====================================

Any single instance of LAVA V2 can be extended to work with one or more
slaves which only need ``lava-dispatcher`` installed.

.. seealso:: :ref:`Installing a slave <installing_pipeline_worker>`

Authentication and encryption
-----------------------------

When the slave is on the same subnet and behind the same firewall as the
master, admins can choose to use slaves without authentication. In all
other cases, the ZMQ socket used for passing control messages to the
slave and the socket used to pass logs back to the master need to use
authentication which will then turn on :ref:`encryption <zmq_curve>`.

Once authentication is configured on the master, one or more slaves can
be :ref:`prepared <installing_pipeline_worker>` and also configured to
use authentication.

Other installation notes
************************

A note on wsgi buffers
======================

When submitting a large amount of data to the django application,
it is possible to get an HTTP 500 internal server error. This problem
can be fixed by appending ``buffer-size = 65535`` to
``/etc/lava-server/uwsgi.ini``

.. _automated_installation:

Automated installation
======================

Using debconf pre-seeding with Debian packages
----------------------------------------------

Debconf can be easily automated with a text file which contains the
answers for debconf questions - just keep the file up to date if the
questions change. For example, to preseed a worker install::

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
page can be changed in the settings ``/etc/lava-server/settings.conf`` (JSON syntax)::

   "BRANDING_URL": "http://www.example.org",
   "BRANDING_ALT": "Example site",
   "BRANDING_ICON": "https://www.example.org/logo/logo.png",
   "BRANDING_HEIGHT": 26,
   "BRANDING_WIDTH": 32,
   "BRANDING_BUG_URL": "http://bugs.example.org/lava",
   "BRANDING_SOURCE_URL": "https://github.com/example/lava-server",

If the icon is available under the django static files location, this location
can be specified instead of a URL::

   "BRANDING_ICON": "path/to/image.png",

There are limits to the size of the image, approximately 32x32 pixels, to avoid
overlap.

The ``favicon`` is configurable via the Apache configuration::

 Alias /favicon.ico /usr/share/lava-server/static/lava-server/images/linaro-sprinkles.png

LAVA Dispatcher network configuration
=====================================

``/etc/lava-dispatcher/lava-dispatcher.conf`` supports overriding the
``LAVA_SERVER_IP`` with the currently active IP address using a list of
network interfaces specified in the ``LAVA_NETWORK_IFACE`` instead of a
fixed IP address, e.g. for LAVA installations on laptops and other devices
which change network configuration between jobs. The interfaces in the
list should include the interface which a remote worker can use to
serve files to all devices connected to this worker.

