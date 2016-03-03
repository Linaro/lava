.. _lava_v1:

LAVA V1 - deprecated
####################

[ `Help Overview <../>`_]
[ `Help Pipeline (V2) <../v2/>`_]
[ `Home <../../../>`_ ] [ `Dashboard <../../../dashboard/>`_ ]
[ `Scheduler <../../../scheduler/>`_ ]
[ `API <../../../api/help/>`_ ]


LAVA V1 is the collective name for the LAVA support which involves JSON submissions,
``deploy_linaro_kernel`` and associated actions, Bundles, BundleStreams, Filters
and Image Reports (including Image Reports 2.0).

The 2016.2 release marks the start of the migration away from V1 towards the
pipeline model in V2.

.. toctree::
   :maxdepth: 2

   overview.rst
   glossary.rst
   support.rst
   installation.rst
   writing-tests.rst
   writing-multinode.rst
   deprecated.rst
   test-repositories.rst
   filters-reports.rst
   lava-dashboard-image-reports.rst
   healthchecks.rst
   multinode-usecases.rst
   vm-groups.rst
   process.rst
   faq.rst

LAVA Test Developer Guide
#########################

.. toctree::
   :maxdepth: 2

   developing-tests.rst
   dispatcher-actions.rst
   lava_test_shell.rst
   hacking-session.rst
   multinode.rst
   vm-groups.rst
   boot-management.rst
   bootimages.rst
   tftp-deploy.rst
   external_measurement.rst
   data-export.rst
   lmp_test_guide.rst

LAVA Administrator Guide
########################

.. toctree::
   :maxdepth: 2

   configuration.rst
   running.rst
   devicetypes.rst
   hiddentypes.rst
   proxy.rst
   lava-image-creation.rst
   known-devices.rst
   qemu-deploy.rst
   pdudaemon.rst
   kvm-deploy.rst
   ipmi-pxe-deploy.rst
   dummy-deploy.rst
   ipxe.rst
   hijack-user.rst

Other Topics
############

.. toctree::
   :maxdepth: 2

   extending.rst
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

   development.rst
   debian.rst
   schema.rst
