LAVA Overview
#############

[ `LAVA V1 <v1/index.html>`_ ]
[ `LAVA V2 <v2/index.html>`_ ]

Return to LAVA site:
[ `Home <../../>`_ ]
[ `Dashboard <../../dashboard/>`_ ]
[ `Results <../../results/>`_ ]
[ `Scheduler <../../scheduler/>`_ ]
[ `API <../../api/help/>`_ ]

.. index:: LAVA

What is LAVA?
*************

LAVA is the Linaro Automation and Validation Architecture.

LAVA is a continuous integration system for deploying operating
systems onto physical and virtual hardware for running tests.
Tests can be simple boot testing, bootloader testing and system
level testing, although extra hardware may be required for some
system tests. Results are tracked over time and data can be
exported for further analysis.

LAVA is a collection of participating components, the overall idea and
evolving architecture that allows us to make testing, quality control
and automation. LAVA-the-stack aims to make systematic, automatic and
manual quality control more approachable for projects of all sizes.

LAVA is for validation - telling whether the code the other Linaro
engineers are producing "works" in whatever sense that means. It could
be a simple compile or boot test for the kernel, testing whether the
code produced by gcc is smaller or faster, whether a kernel scheduler
change reduces power consumption for a certain workload, or many other
things.

Beyond simple validation though, what LAVA really about is automated
validation. LAVA builds and tests the kernel on all supported boards
every day. LAVA builds and tests proposed android changes in gerrit
before they are landed, and the same for the gcc work. There is a
validation lab in Cambridge - the boards from the Linaro members we
want to test on, but also Cyclades serial console servers, routers,
and a few servers.

.. note:: This overview document explains LAVA using
          http://validation.linaro.org/ which is the official
          production instance of LAVA hosted by Linaro. Where examples
          reference ``validation.linaro.org``, replace with the fully
          qualified domain name of your LAVA instance.

LAVA Migration
**************

LAVA is currently in the middle of a migration from the V1 model to a
new design, called the Pipeline Model, to create V2. These help pages are
divided into V1 and V2. Some LAVA instances will only support V2, some
will support both and some may only support V1. However, V1 support will
be removed at some point in 2017, so instances which do not migrate to
V2 will not be able to receive updates.

.. note:: Please subscribe to the :ref:`mailing_lists` for information
   and support.

LAVA V1
=======

V1 refers to the components of LAVA which are related to:

* JSON job submissions
* Bundles, BundleStreams and ``submit_results``
* Image Reports and Image Reports 2.0

All code supporting V1 is deprecated as of the **2016.2 release** and
is scheduled to be removed from the codebase during 2017.

.. warning:: When the code objects are removed, the corresponding database
   records, tables, indexes and relationships will also be **deleted**.
   Instances which want to continue using V1 from 2017 onwards **must not**
   install updates or **all V1 data will be lost**.

.. seealso:: `LAVA V1 <v1/index.html>`_

LAVA V2
=======

V2 refers to the **pipeline** model - a new design for how the test job
is constructed which also delivers a much simpler way of deploying distributed
instances and gives test writers a lot more room to write new test jobs
using new protocols and test methods.

* YAML job submissions, supporting comments
* Results, Queries and Charts
* Live result reporting (no final submission stage)
* Simplified setup for distributed instances

The code supporting V2 is being extended to support a wider range of
devices and deployment methods, with the migration to V2 expected to
last until the end of 2016.

.. seealso:: `LAVA V2 <v2/index.html>`_


.. include:: support.rst
.. include:: tables.rst
