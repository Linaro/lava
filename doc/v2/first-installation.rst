.. _installation:

Initial LAVA Installation
#########################

The default installation provides an Apache2 config suitable for
a simple LAVA server at ``http://localhost/`` once enabled.

See :ref:`packaging_distribution` for more information or for
debugging.

.. _lava_requirements:

Requirements to Consider Before Installing LAVA
###############################################

Architecture
************

.. include:: architecture-v2.rsti

Software Requirements
*********************

See :ref:`debian_installation` for instructions.

We currently recommend installing LAVA on `Debian`_ unstable, stretch
or jessie. Installations using jessie (the current Debian stable release)
should use updates available in ``jessie-backports``.

Contributions to support other distributions are welcome.

.. _Debian: https://www.debian.org/

If you'd like to help us provide support for other distributions, feel
free to contact us using the :ref:`lava_devel` mailing list.

Hardware Requirements
*********************

A small LAVA instance can be deployed on fairly modest hardware. We
recommend at least 1GB of RAM to cover the runtime needs of the
database server, the application server and the web server. For
storage, reserve about 20GB for application data, especially if you
wish to mirror the current public Linaro LAVA instance.  LAVA uses
append-only models, so storage requirements will grow over time.

If you are deploying many devices and expect to be running large
numbers of jobs, you will obviously need more RAM and disk space.

Device requirements
===================

Devices you wish to deploy in LAVA need to be:
 * Physically connected to the server via usb, usb-serial,
   or serial; or
 * connected over the network via a serial console server; or
 * a fastboot capable device accessible from the server; or
 * a virtual machine or simulator that emulates a serial connection

.. _multinode_hardware_requirements:

Multi-Node hardware requirements
********************************

If the instance is going to be sent any job submissions from third
parties or if your own job submissions are going to use Multi-Node,
there are additional considerations for hardware requirements.

Multi-Node is explicitly designed to synchronise test operations across
multiple test devices and running Multi-Node jobs on a particular instance
will have implications for the workload of that instance. This can
become a particular problem if the instance is running on virtualised
hardware with shared I/O, a limited amount of RAM or a limited number
of available cores.

.. note:: Downloading, preparing and deploying test images can result
 in a lot of synchronous I/O and if a single machine is running both
 the LAVA server and dispatcher, running synchronised Multi-Node jobs
 can cause the load on that machine to rise significantly, possibly
 causing the server to become unresponsive. For this reason, it is
 strongly recommended that Multi-Node instances use a separate
 dispatcher running on non-virtualised hardware so that the (possibly
 virtualised) server can continue to operate.

Also, consider the number of test devices connected to any one
dispatcher. Multi-Node jobs will commonly compress and decompress
several large test image files in parallel. Even with a powerful
multi-core machine, this can cause high load. It is worth considering
matching the number of devices to the number of cores for parallel
decompression, and matching the amount of available RAM to the number
and size of test images which are likely to be in use.

Which release to install
########################

The LAVA team makes regular releases (called ``production releases``),
typically monthly. These are installed onto Linaro's central instance
https://validation.linaro.org/ and they are also uploaded to Debian
unstable and backports (see :ref:`debian_installation`). These
``production releases`` are tracked in the ``release`` branch of the
upstream git repositories.

Interim releases are made available from the the
:ref:`staging-repo <lava_repositories>`.

If in doubt, install the ``production`` release of ``lava-server``
from official distribution mirrors. (Backports are included on Debian
mirrors.)

The ``lava-dev`` package includes scripts to assist in local developer
builds directly from local git working copies which allows for builds
using unreleased code, development code and patches under review.

.. _install_types:

Installation Types
##################

.. _single_instance:

Single Master Instance installation
***********************************

A single instance runs the web frontend, the database, the scheduler
and the dispatcher on a single machine. If this machine is also running
tests, the device (or devices) under test (:term:`DUT`) will also need
to be connected to this machine, possibly over the network, using
USB or using serial cables.

To install a single master instance and create a superuser, refer to
:ref:`debian_installation` installation.

LAVA V1 used to support a `distributed_instance` installation
method. This has been **deprecated** in V2; instead there is a much
improved architecture for remote workers using :term:`ZMQ`.

Detailed instructions for setting up workers follows - first, think
about the kind of configuration needed for your instance.

Running V1 only
***************

You're reading the wrong documentation - look at the `V1 docs
<../v1/>`_ instead. But be aware that V1 is reaching end of life soon,
so this would be a *frozen* instance.

.. warning:: Installing any updates of ``lava-server`` or ``lava-dispatcher``
   onto a *frozen* instance after the removal of V1 support will
   cause permanent data loss.

Running V2 only
***************

Layout
======

* The master needs ``lava-server`` installed as a :ref:`single_instance`.
* The worker only needs ``lava-dispatcher`` installed as a
  :ref:`pipeline installation <setting_up_pipeline_instance>`.
* Workers on the same subnet as the master can use :term:`ZMQ` without
  using authentication and encryption. Workers on a remote network
  are **strongly** recommended to use authentication and encryption
  of the ZMQ messages.

  .. seealso:: :ref:`zmq_curve`

* ZMQ supports buffering the messages, so master and workers can be
  independently restarted.

Configuration outline
======================

* Configure the master as a :ref:`single_instance`.
* Define some of the device-types likely to be used with this instance
  in the django administrative interface.
* Prepare device dictionaries for the devices of those types.

You can choose whether the master has devices configured locally or
only uses devices via one or more workers. Once you are happy with
that installation, think about adding workers - one at a time.

* Configure ``lava-master`` to use the ``--encrypt`` option if the
  master is to have any workers on remote networks.

  * Generate certificates if ``--encrypt`` is to be used.

* Configure ``lava-slave`` to look for the master ZMQ port instead of
  ``localhost``.

  * Install the master certificate and copy the slave certificate to
    the master.

* Add the worker to the database on the master using the django
  administration interface.
* Configure the device dictionaries on the master for all devices
  attached to this worker.
* Assign devices to that worker.
* Run health checks and be sure that all devices are properly configured.
* Repeat for additional workers.

Running a mix of V1 and V2
**************************

.. warning:: Administrators of instances which mix V1 and V2 must
   consider that V1 support **will** be removed during 2017, while V2
   support will continue. If you are running a mixed installation, we
   **strongly** encourage you to get involved in the migration to V2
   and subscribe to the :ref:`support mailing lists <mailing_lists>`
   to ensure a clean migration for your V1 devices before they stop
   working.

Layout
======

* The master and **all** workers which will have any V1 devices
  attached **must** use the V1 distributed deployment installation
  method as described in the `V1 documentation <../v1/>`_
* Selected devices can have the ``pipeline`` support enabled in the
  django administration interface. These devices will then accept
  both pipeline (YAML) and V1 (JSON) job submissions.
* Pipeline devices need a Device Dictionary to be able to run V2
  job submissions.
* The Device Dictionary can include a setting to make the device
  **exclusive** to V2 submissions, so V1 JSON submissions will not be
  allowed.
* All workers which have any devices which are not **exclusive** in
  this way **must** have SSHFS and Postgres connections configured for
  V1 support.
* Layouts which require workers to be geographically remote from the
  master are recommended to **only** have **exclusive** devices to
  limit the known issues with maintaining connections required for
  V1 across networks outside your control.

Configuration outline
=====================

The mixed configuration is the most complex to setup as it requires
knowledge of both V1 and V2.

* Follow all the documentation for V1 distributed deployments and
  ensure that all V1 devices are working.
* Configure the workers using V2. Remember that if the worker has
  V1 and V2 devices, that worker should be local to the master due
  to known limitations of the V1 configuration.

.. _pipeline_install:

What is the Pipeline?
#####################

.. note:: Linaro production systems in the Cambridge lab began to
   migrate to the V2 Pipeline model with the 2016.2 production
   release, while retaining support for the deprecated V1 model until
   the migration is complete. The V1 support is due to be removed
   in 2017.

In parallel with the **deprecated** :ref:`single_instance` and
`distributed_instance` models, the :term:`dispatcher refactoring
<refactoring>` in the V2 (Pipeline) model introduces changes and new
elements which should not be confused with the previous production
models. It is supported to install LAVA using solely the new design
but there are some :ref:`pipeline_install_considerations` regarding
your current device usage. Submission requirements and device support
can change before and during a migration to the new design.

This documentation includes notes on the new design, so to make things
clearer, the following terms refer exclusively to the new design and
have no bearing on `single_instance` or `distributed_instance`
installation methods from V1 LAVA which are being used for current
production instances in the Cambridge lab.

#. :term:`pipeline`
#. :term:`refactoring`
#. :term:`device dictionary`
#. :term:`ZMQ`

The pipeline model also changes the way that results are gathered,
exported and queried, replacing the `bundle stream`,
`result bundle` and `filter` dashboard objects. This new
:term:`results` functionality only operates on pipeline test jobs and is ongoing
development, so some features are incomplete and likely to change in future
releases. Admins can choose to not show the new results app, for example until
pipeline devices are supported on that instance, by setting the ``PIPELINE`` to
``false`` in :file:`/etc/lava-server/settings.conf` - make sure the file
validates as JSON before restarting apache::

 "PIPELINE": false

If the value is not set or set to ``true``, the Results app will be displayed.

.. seealso:: :ref:`setting_up_pipeline_instance`

.. index:: coordinator

LAVA Coordinator setup
**********************

Multi-Node LAVA requires a LAVA Coordinator which manages the messaging
within a group of nodes involved in a Multi-Node job set according to
this API. The LAVA Coordinator is a singleton to which nodes need to connect
over a TCP port (default: 3079). A single LAVA Coordinator can manage
groups from multiple instances. If the network configuration uses a
firewall, ensure that this port is open for connections from Multi-Node
dispatchers.

If multiple coordinators are necessary on a single machine (e.g. to test
different versions of the coordinator during development), each
coordinator needs to be configured for a different port.

If the dispatcher is installed on the same machine as the coordinator,
the dispatcher can use the packaged configuration file with the default
hostname of ``localhost``.

Each dispatcher then needs a copy of the LAVA Coordinator configuration
file (JSON syntax), modified to point back to the hostname of the coordinator:

Example JSON, modified for a coordinator on a machine with a fully
qualified domain name::

  {
    "port": 3079,
    "blocksize": 4096,
    "poll_delay": 3,
    "coordinator_hostname": "control.lab.org"
  }

An IP address can be specified instead, if appropriate.

Each dispatcher needs to use the same port number and blocksize as is
configured for the Coordinator on the specified machine. The poll_delay
is the number of seconds each node will wait before polling
the coordinator again.

.. _serial_connections:

Setting Up Serial Connections to LAVA Devices
#############################################

.. _ser2net:

Ser2net daemon
**************

ser2net provides a way for a user to connect from a network connection
to a serial port, usually over telnet.

http://ser2net.sourceforge.net/

``ser2net`` is a dependency of ``lava-dispatcher``, so will be
installed automatically.

Example config (in /etc/ser2net.conf)::

 #port:connectiontype:idle_timeout:serial_device:baudrate databit parity stopbit
 7001:telnet:0:/dev/serial_port1:115200 8DATABITS NONE 1STOPBIT

.. note:: In the above example we have the idle_timeout as 0 which
          specifies a infinite idle_timeout value. 0 is the
          recommended value. If the user prefers to give a positive
          finite idle_timeout value, then there is a possibility that
          long running jobs may terminate due to inactivity on the
          serial connection.

StarTech rackmount usb
**********************

W.I.P

* udev rules::

   SUBSYSTEM=="tty", ATTRS{idVendor}=="0403", ATTRS{idProduct}=="6001", ATTRS{serial}=="ST167570", SYMLINK+="rack-usb02"
   SUBSYSTEM=="tty", ATTRS{idVendor}=="0403", ATTRS{idProduct}=="6001", ATTRS{serial}=="ST167569", SYMLINK+="rack-usb01"
   SUBSYSTEM=="tty", ATTRS{idVendor}=="0403", ATTRS{idProduct}=="6001", ATTRS{serial}=="ST167572", SYMLINK+="rack-usb04"
   SUBSYSTEM=="tty", ATTRS{idVendor}=="0403", ATTRS{idProduct}=="6001", ATTRS{serial}=="ST167571", SYMLINK+="rack-usb03"

This will create a symlink in /dev called rack-usb01 etc. which can then be addressed in the :ref:`ser2net` config file.

Contact and bug reports
#######################

Please report bugs using Linaro's Bugzilla:
https://bugs.linaro.org/enter_bug.cgi?product=LAVA%20Framework

You can also report bugs using ``reportbug`` and the
Debian Bug Tracking System: https://bugs.debian.org/cgi-bin/pkgreport.cgi?pkg=lava-server

Feel free to contact us at validation (at) linaro (dot) org and on
the ``#linaro-lava`` channel on OFTC.
