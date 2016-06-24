.. index:: Documentation Index

.. _toc:

LAVA V2 - Pipeline model
########################

[ `Help Overview <../>`_]
[ `Help V1 <../v1/>`_]
[ `Home <../../../>`_ ]
[ `Results <../../../results/>`_ ]
[ `Scheduler <../../../scheduler/>`_ ]
[ `API <../../../api/help/>`_ ]

LAVA V2 is the second major version of LAVA. The major user-visible
features are:

* The Pipeline model for the dispatcher
* YAML job submissions
* Results
* Queries
* Charts
* Data export APIs

The architecture has been significantly improved since V1, bringing
major changes in terms of how a distributed LAVA instance is
installed, configured and used for running test jobs.

Migration to V2 started with the 2016.2 release.

LAVA Overview
#############

.. include:: what-is-lava.rst


Architecture
************

.. include:: architecture-v2.rsti

Features
********

Deployment methods
==================

All test jobs involve a deployment step of some kind, even if that is
just to prepare the overlay used to copy the test scripts onto the
device or to setup the process of parsing the results when the test job
starts.

Boot methods
============

Hardware devices need to be instructed how to boot, emulated devices need
to boot the emulator. For other devices, a ``boot`` can be simply establishing
a connection to the device.

Test methods
============

The principal test method in LAVA is the Lava Test Shell which requires
a POSIX type environment to be running on the booted device. Other test
methods available include executing tests using ADB.

Multiple device testing
=======================

Some test jobs need to boot up multiple devices in a single, coordinated,
group. For example, a server could be tested against multiple clients.
LAVA supports starting these sub jobs as a group as well as passing
messages between nodes via the dispatcher connection, without needing
the devices to have a working network stack.

Scheduling
==========

LAVA has advanced support for scheduling multiple jobs across multiple
devices, whether those jobs use one device or several. Scheduling is
ordered using these criteria, in this order:

#. :term:`health checks <health check>`
#. :term:`priority`
#. submit time
#. multinode group - see also :ref:`multinode`

In addition, scheduling can be restricted to devices specified by the
admin using:

* :term:`device tags <device tag>`
* user access limits - see :term:`restricted device` or
  :term:`hidden device type`.

Advanced use cases
==================

Advanced use cases expand on this support to include:

* creating and deleting customised virtual networks, where suitable
  hardware and software support exists.
* extracting data from LAVA to manage job submission and result handling
  to support developer-specific tasks like
  `KernelCI <https://kernelci.org/>`_.

Glossary
********

.. toctree::
   :maxdepth: 1

   glossary.rst

Support
*******

.. toctree::
   :maxdepth: 1

   support.rst

First Steps Using LAVA V2
*************************

.. toctree::
   :maxdepth: 1

   first_steps.rst
