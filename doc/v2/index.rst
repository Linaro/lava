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
ordered using these criteria:

* submit time
* priority
* device tags
* user access
* health checks

Advanced use cases
==================

Advanced use cases expand on this support to include:

* creating and deleting customised virtual networks, where suitable
  hardware and software support exists.
* extracting data from LAVA to manage job submission and result handling
  to support developer-specific tasks like
  `KernelCI <https://kernelci.org/>`_.

.. toctree::
   :maxdepth: 1

   glossary.rst
   support.rst
   process.rst

First Steps Using LAVA V2
#########################

.. toctree::
   :maxdepth: 1

   logging-in.rst
   authentication-tokens.rst
   first-job.rst
   lava-tool.rst

First Steps Installing LAVA V2
##############################

.. toctree::
   :hidden:
   :maxdepth: 1

   first-installation.rst
   installing_on_debian.rst
   first-devices.rst
   simple-admin.rst

Writing Tests
#############

.. toctree::
   :hidden:
   :maxdepth: 1

   developing-tests.rst
   bootimages.rst
   pipeline-design.rst
   pipeline-usecases.rst
   pipeline-schema.rst
   writing-tests.rst
   test-repositories.rst
   dispatcher-format.rst
   dispatcher-actions2.rst
   lava_test_shell.rst
   publishing-results.rst
   healthchecks.rst
   hacking-session.rst
   writing-multinode.rst
   multinodeapi.rst
   multinode-usecases.rst
   vland.rst
   test-examples.rst
   debugging.rst
   tests-reference.rst

Using Test Results
##################

.. toctree::
   :hidden:
   :maxdepth: 1

   storing-results.rst
   lava-queries-charts.rst
   data-export.rst

LAVA Administration
###################

.. toctree::
   :hidden:
   :maxdepth: 1

   advanced-installation.rst
   pipeline-server.rst
   pipeline-admin.rst
   proxy.rst
   pipeline-admin-example.rst
   devicetypes.rst
   device-capabilities.rst
   authentication.rst
   hijack-user.rst
   hiddentypes.rst
   migrate-lava.rst
   pdudaemon.rst
   nexus-deploy.rst
   ipmi-pxe-deploy.rst
   ipxe.rst
   lxc-deploy.rst
   vland-admin.rst

LAVA XML-RPC APIs
#################

.. toctree::
   :hidden:
   :maxdepth: 1

   results-api.rst
   control-api.rst

Developer guides
################

.. toctree::
   :hidden:
   :maxdepth: 1

   development.rst
   dispatcher-design.rst
   dispatcher-testing.rst
   debian.rst
   packaging.rst
   usage.rst

Migrating from V1
#################

.. toctree::
   :hidden:
   :maxdepth: 1

   migration.rst

Other Topics
############

.. toctree::
   :hidden:
   :maxdepth: 1

   faq.rst
   lava-scheduler.rst
   lava-scheduler-device-help.rst
   lava-scheduler-device-type-help.rst
   lava-scheduler-submit-job.rst
   lava-scheduler-job.rst


