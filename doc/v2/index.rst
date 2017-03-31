.. comment

   How the bootstrap theme works.

   Same for any files included into this file.
   Same for any files directly included into any file covered by the above.
   Pages need to appear in the contents.rst toctree for prev+next navigation.
   conf.py adds permanent links to genindex - the navbar
      gets folded into a menu by bootstrap on narrow screens.

.. index:: Documentation Index

.. _toc:

LAVA V2 - Pipeline model
########################

Navigation
**********

[ `Help Overview <../>`_]
[ `Help V1 <../v1/>`_]
[ `Home <../../../>`_ ]
[ `Results <../../../results/>`_ ]
[ `Scheduler <../../../scheduler/>`_ ]
[ `API <../../../api/help/>`_ ]
[ `V2 Help Index <genindex.html>`_ ]
[ `V2 Help Contents <contents.html>`_ ]

Use the navigation bar at the top of the page to quickly navigate between
sections of the documentation.

Each page also has a **Page** menu for topics within the page as well as
forward and back navigation to lead readers through in a logical manner.

.. figure:: images/lava.svg
    :width: 50%
    :align: center
    :alt: LAVA logo
    :figclass: fig-float

About LAVA V2
*************

LAVA V2 is the second major version of LAVA. The major user-visible features
are:

* The Pipeline model for the dispatcher
* YAML job submissions
* Results
* Queries
* Charts
* Data export APIs

The architecture has been significantly improved since V1, bringing major
changes in terms of how a distributed LAVA instance is installed, configured
and used for running test jobs.

Migration to V2 started with the 2016.2 release.

LAVA Overview
#############

.. include:: what-is-lava.rsti

Architecture
************

.. include:: architecture-v2.rsti

Preparation
***********

LAVA has a steep learning curve and this does not tend to level off as your lab
grows. Even small labs involve additional hardware, infrastructure and
administrative tasks.

#. Do **not** rush into LAVA setup.

#. :ref:`simple_admin_small`.

#. Think carefully about what you are trying to test. Avoid common pitfalls of
   :ref:`simplistic testing <simplistic_testing_problems>`.

#. Learn :ref:`how to debug LAVA <admin_debug_information>` with a small lab
   and :ref:`use standard test jobs <using_gold_standard_files>`.

#. Invest in :ref:`additional hardware <infrastructure_requirements>` - a
   device on your desk is not a good candidate for automation.

#. :ref:`Test with emulated devices <submit_first_job>` before thinking about
   the device on your priority list.

   * Integrating a completely new :term:`device type` is the probably **the most
     complex thing to do in LAVA**. It can take a few months of work for
     devices which do not use currently supported methods or bootloaders.

#. Start by adding :ref:`known devices <first_devices>`, including purchasing
   some of the low-cost devices already supported by LAVA.

#. :ref:`Talk to us <getting_support>` before looking at device types not
   currently supported on LAVA instances.

Methods
*******

Deployment methods
==================

All test jobs involve a deployment step of some kind, even if that is just to
prepare the overlay used to copy the test scripts onto the device or to setup
the process of parsing the results when the test job starts.

Boot methods
============

Hardware devices need to be instructed how to boot, emulated devices need to
boot the emulator. For other devices, a ``boot`` can be simply establishing a
connection to the device.

Test methods
============

The principal test method in LAVA is the Lava Test Shell which requires a POSIX
type environment to be running on the booted device. Other test methods
available include executing tests using ADB.

Multiple device testing
=======================

Some test jobs need to boot up multiple devices in a single, coordinated,
group. For example, a server could be tested against multiple clients. LAVA
supports starting these sub jobs as a group as well as passing messages between
nodes via the dispatcher connection, without needing the devices to have a
working network stack.

.. _scheduling:

Scheduling
==========

LAVA has advanced support for scheduling multiple jobs across multiple devices,
whether those jobs use one device or several. Scheduling is ordered using these
criteria, in this order:

#. :term:`health checks <health check>`
#. :term:`priority`
#. submit time
#. multinode group - see also :ref:`multinode`

In addition, scheduling can be restricted to devices specified by the admin
using:

* :term:`device tags <device tag>`
* user access limits - see :term:`restricted device` or
  :term:`hidden device type`.

Advanced use cases
==================

Advanced use cases expand on this support to include:

* creating and deleting customised virtual networks, where suitable hardware
  and software support exists.

* extracting data from LAVA to manage job submission and result handling to
  support developer-specific tasks like `KernelCI <https://kernelci.org/>`_.

.. # this toctable determines the Site menu (if configured to appear)
   and the next/prevous links on the top bar

.. toctree::
   :hidden:
   :maxdepth: 3

   self
   contents

Glossary
********

.. toctree::
   :maxdepth: 1

   glossary

Support
*******

.. toctree::
   :maxdepth: 1

   support

Full documentation
******************

LAVA V2 comes with :ref:`comprehensive documentation <contents_top>`
about use and installation, including advice on how to manage a test
lab.
