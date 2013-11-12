Features
========

At a high-level LAVA includes:

* `deployment tool <http://lava-deployment-tool.readthedocs.org/en/latest/index.html>`_
  to help guide users through installing server components.
* web interface that includes:
   * `scheduler <http://validation.linaro.org/lava-server/scheduler/>`_
     for viewing the status of testing targets.
   * `dashboard <http://validation.linaro.org/lava-server/dashboard/>`_
     for viewing the results of tests performed.
   * admin panel for configuring the system.
   * "`filters <http://validation.linaro.org/lava-server/dashboard/filters/>`_"
     mechanism to help derive `report views <http://validation.linaro.org/lava-server/dashboard/image-reports/>`_
     from.
* `command line interface <https://lava-scheduler.readthedocs.org/en/latest/usage.html#submitting-jobs>`_
  that includes:
   * support for submitting, re-submitting, and cancelling test jobs.
   * support for adding/retrieving test result bundles.
* An extensible server that allows for new custom extensions to be added.
* Test framework support for `Android <http://lava-android-test.readthedocs.org/en/latest/>`_, `Ubuntu <http://lava-test.readthedocs.org/en/latest/>`_, and `OpenEmbedded <http://lava-dispatcher.readthedocs.org/en/latest/jobfile.html#using-lava-test-shell>`_ based images.
* A variety of `supported devices <http://bazaar.launchpad.net/~linaro-validation/lava-dispatcher/trunk/files/head:/lava_dispatcher/default-config/lava-dispatcher/device-types/>`_.
