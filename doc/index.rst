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

.. include:: what-is-lava.rst

LAVA Migration
**************

LAVA is currently in the middle of a lengthy migration from its
original design (known as the V1 model) to a new design, called the
Pipeline model or the V2 model. During this migration, LAVA
installations will be able to support test devices and test jobs
targeting both models. These help pages are divided into V1 and V2
accordingly.

While this migration is taking place, it is expected that some LAVA
instances will only support V2, some will support both versions and
some may only support V1. However, V1 support is **deprecated** and will
be removed at some point in 2017. Instances which do not migrate to V2
will not be able to receive updates beyond that point so users are
strongly encouraged to move to V2 as soon as possible.

.. note:: Please subscribe to the :ref:`mailing_lists` for information
   and support.

LAVA V1
=======

V1 refers to the components of LAVA which are related to:

* JSON job submissions
* Bundles, BundleStreams and the ``submit_results`` action
* Image Reports and Image Reports 2.0

All code supporting V1 is deprecated as of the **2016.2 release** and
is scheduled to be removed from the codebase during 2017.

.. warning:: When the code objects implementing V1 are removed, the
   corresponding database records, tables, indexes and relationships
   will be **deleted** during later upgrades. Instances which want to
   continue using V1 from 2017 onwards **must not** install updates or
   **all V1 data will be lost**.

.. seealso:: `LAVA V1 <v1/index.html>`_

LAVA V2
=======

V2 refers to the **pipeline** model - a new design for how the test
job is constructed. It gives test writers much more freedom to write
new test jobs using new protocols and test methods, and it also
delivers a much simpler way of deploying distributed instances.

* YAML job submissions, supporting comments
* Results, Queries and Charts
* Live result reporting (no final submission stage)
* Simplified setup for distributed instances

The code supporting V2 is being extended to support a wider range of
devices and deployment methods. The migration to V2 is expected to last
until the end of 2016.

.. seealso:: `LAVA V2 <v2/index.html>`_


.. include:: support.rst
.. include:: tables.rst
