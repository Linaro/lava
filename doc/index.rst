LAVA Manual
###########

[ `Home <../../>`_ ] [ `Dashboard <../../dashboard/>`_ ] [ `Scheduler <../../scheduler/>`_ ] [ `API <../../api/help/>`_ ]

.. note:: Migrations from the current dispatcher to the :term:`pipeline`
   are beginning and will continue as more devices and new deployment
   methods gain support in the :term:`refactoring`. Please subscribe
   to the :ref:`mailing_lists` for information and support. Migrations
   are expected to take most of 2016 to complete. Support for the
   current dispatcher will be **removed** at a point after the
   completion of the migrations.
   See the :ref:`guide to migrating to the pipeline <migrating_to_pipeline>`.
   See also docs for the :ref:`deprecated JSON features <deprecated_features>`.

.. toctree::
   :maxdepth: 2

   overview.rst
   glossary.rst
   support.rst
   installation.rst
   migration.rst
   writing-tests.rst
   writing-multinode.rst
   test-repositories.rst
   lava-dashboard-image-reports.rst
   healthchecks.rst
   process.rst
   faq.rst

Deprecated features
###################

All features of the current dispatcher and some features of the server
UI which are bound to features of the current dispatcher are deprecated
in favour of the :term:`pipeline`. Support for these features will be
removed in a future release.

.. toctree::
   :maxdepth: 1

   deprecated/deprecated.rst
   deprecated/dispatcher-actions.rst
   deprecated/filters-reports.rst
   deprecated/vm-groups.rst
   deprecated/precise.rst
   deprecated/multinode.rst
   deprecated/multinode-usecases.rst
   deprecated/boot-management.rst
   deprecated/tftp-deploy.rst
   deprecated/hiddentypes.rst
   deprecated/data-export.rst
   deprecated/lmp_test_guide.rst
   deprecated/configuration.rst
   deprecated/running.rst
   deprecated/lava-image-creation.rst
   deprecated/known-devices.rst
   deprecated/qemu-deploy.rst
   deprecated/kvm-deploy.rst
   deprecated/dummy-deploy.rst
   deprecated/development.rst
   deprecated/schema.rst

LAVA Test Developer Guide
#########################

.. toctree::
   :maxdepth: 2

   developing-tests.rst
   pipeline-usecases.rst
   pipeline-schema.rst
   dispatcher-format.rst
   lava_test_shell.rst
   dispatcher-actions2.rst
   hacking-session.rst
   bootimages.rst

LAVA Administrator Guide
########################

.. toctree::
   :maxdepth: 2

   devicetypes.rst
   hiddentypes.rst
   proxy.rst
   pdudaemon.rst
   nexus-deploy.rst
   ipmi-pxe-deploy.rst
   ipxe.rst
   lxc-deploy.rst
   hijack-user.rst
   migrate-lava.rst

Other Topics
############

.. toctree::
   :maxdepth: 2

   extending.rst
   usage.rst
   arm_energy_probe.rst
   device-capabilities.rst
   packaging.rst
   installing_on_debian.rst
   lava-scheduler.rst
   lava-scheduler-device-help.rst
   lava-scheduler-device-type-help.rst
   lava-scheduler-submit-job.rst
   lava-scheduler-job.rst
   lava-tool.rst

Developer guides
################

.. toctree::
   :maxdepth: 2

   debian.rst
   dispatcher-design.rst
   dispatcher-testing.rst
   lava-results-queries.rst
