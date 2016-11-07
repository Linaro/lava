.. index:: pipeline design

.. _pipeline_design:

Pipeline Design
###############

Principles of the V2 design
***************************

Test Writer aspects
===================

* **Fail early** - full validation of the pipeline built for each test job
  before the job starts to run.

* **Clearer error handling** - distinguishing between an error in the test, the
  job or a problem in the code or the instance hardware.

* **Explicit details** - no guesswork based on filename extensions or
  convention. The test writer **must** specify the compression methods and
  other aspects of all files to be handled by LAVA.

* **Live results** - results are logged as the test job runs, so if the test
  fails, the device hangs or the job is interrupted, all results logged prior
  to that point remain available.

* **Give more control to test writers** - once the test job has got to a
  successful login, the rest of the test job operations are under the full
  control of the test writer. This includes launching virtual machines on the
  device. The V2 design provides methods to assist with running tests on
  devices or virtual machines but is designed to avoid imposing requirements
  other than those necessary for automation.

* **Simpler access to data** - all results are related directly to the test job
  and can be downloaded just by knowing the job ID.

* **Push notifications** - removing the need to poll to get status.
  Notifications can include a comparison of results against similar jobs which
  have already completed on the same instance.

  .. seealso:: :ref:`notifications`, :ref:`publishing_events` and
    :ref:`publishing_artifacts`

Administrator aspects
=====================

* **Simpler communications** - just one fault-tolerant connection between the
  master and the worker(s) using :term:`ZMQ` with authentication and encryption
  support for remote workers.

* **Simpler configuration** - all configuration is on the one master, the
  workers only need to update the base system packages as a standard admin
  task.
