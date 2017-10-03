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

.. _v1_end_of_life:

End Of Life for LAVA V1
***********************

Migration to V2 started with the 2016.2 release as the new codebase
grew and improved. We are now reaching the end of this long
process. As `announced`_, LAVA V1 is now (September 2017) being
retired, in the following steps:

* **2017.9** is the last release of LAVA which will support running V1
  test jobs.

* **2017.10** will not support running V1 test jobs, but will include
  support for providing a read-only archive of V1 test data.

* **2017.11** will be the first release of LAVA which is V2 **only**. It
  will contain no support for accessing V1 data and this V1 documentation will
  be removed.

* **2017.12** will **permanently delete all V1 test data** from the database
  upon installation.

.. _`announced`: https://lists.linaro.org/pipermail/lava-announce/2017-September/000037.html

.. seealso:: [ `LAVA V2 Overview <../v2/>`_]

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
