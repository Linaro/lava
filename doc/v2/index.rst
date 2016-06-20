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

FIXME! <stuff>

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


