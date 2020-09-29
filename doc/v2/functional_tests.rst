.. index:: functional testing

.. _functional_testing:

Functional testing of LAVA source code
######################################

Background
**********

Unit tests are routinely run against each change in a review and again
nightly against the master branch, as well as during development.
However, unit tests cannot properly test the ``run()`` functions or
performance of the code with real hardware. Two extra levels of testing
are available:

* :ref:`meta_lava` - tests the ``run()`` functions against static log
  files. This is useful for devices which are not available to a
  particular instance but will need updating if changes in the code
  cause differences in the messages sent to the device.

* :ref:`Functional testing <purpose_functional_tests>` - running test
  jobs on real hardware. The extra cost of infrastructure,
  administration and maintenance is worthwhile to ensure that changes
  actually perform the required work. Also provides opportunities to
  test the scheduling of the queue and can highlight resource
  limitations.

The LAVA UI is **not** part of functional testing. Wherever possible,
unit tests are used for the UI. Functional testing relates to the code
paths required to schedule, run and cleanup test jobs.

.. index:: meta-lava

.. _meta_lava:

meta-lava
*********

``meta-lava`` is a way of running idealized test jobs to test changes
in the LAVA codebase. It was developed to provide limited test coverage
when suitable hardware was not available. It can be used to provide
test coverage for code which detects unusual or intermittent behavior
by replaying a static log against changes in the codebase.
``meta-lava`` creates a DummySys device based on real log files and
then checks that the inputs from LAVA are correct for that specific use
case.

https://git.lavasoftware.org/lava/meta-lava

``meta-lava`` is a python script that will:

* build lava-server and lava-dispatcher docker image

  * install lava-server or lava-dispatcher using debian packaging

  * fetch the source from git and add the right symlinks

* start the containers and link them in the same network (lava-worker,
  lava-server-gunicorn)

* during the startup, fetch the last git commits (in case the docker
  image were build with an old version)

* wait for the xmlrpc api to show up

* wait for the worker to be up and running (polling the xmlrpc api)

* run a bunch of lava jobs and compare the results with the expected
  ones.

Currently we test:

* ``tests/health-checks``: Check that lava is sending exactly the same
  set of commands and providing the right binaries (ramdisk, kernel,
  dtb over tftp)

* ``tests/bootloader``: Check that lava is detecting and classifying
  common bootloader errors

* ``tests/notitications``: Check that lava is sending the notifications
  as expected (no irc or emails yet)

Future plans
============

* Add more use cases and job output (logs).

* Make test runs public

.. _purpose_functional_tests:

Purpose of functional tests
***************************

Functional tests serve to check the changes in the codebase against
unchanging test job images, resources, metadata, submitter and results
running on real hardware.

Functional tests are similar to health checks and both differ from test
jobs used elsewhere in your CI due to fundamentally different
objectives.

.. note:: Often, functional tests are developed from the sample test
   jobs submitted as part of :ref:`code reviews
   <developer_commit_for_review>` to merge changes to :ref:`integrate a
   new device-type <adding_new_device_types>`. Unit tests will need all
   URLs to be permanent to be able to check the code being reviewed.

In particular, functional tests exist to test code paths involved in
running test jobs which cannot be tested using other means, e.g. unit
tests or meta-lava. Testing the LAVA codebase using real hardware is
not without problems; infrastructure failures need to be isolated from
the results and issues like resource starvation need to be managed.
Where possible, testing the LAVA codebase needs to be done within the
codebase using unit tests or using meta-lava.

Functional tests are measured on a binary **Complete** or
**Incomplete** for each submitted test job.

For a successful run, the suite of functional tests provides a clean
set of Complete test job results. To be able to identify all test jobs
in the functional test run, always use a dedicated submitter for
functional tests, distinct from user tests and other automated tests.

.. _functional_requirements:

Requirements for a functional test job
======================================

The overriding principle for a functional test is that the job is
testing the LAVA software code, not the deployed system. This is
similar to a :term:`health check` which is designed to test the DUT and
related infrastructure to provide an assurance that test jobs will be
able to run successfully.

#. Image files used in functional tests need to remain static, and they
   need to be stored in static locations. Do not rely on files that may
   change easily, e.g. releases on snapshots.linaro.org. If you need
   those files, copy them to a stable location.

#. Use stable, unchanging tools (e.g from the stable release of a Linux
   distribution like Debian).

#. Use the deployment tools from the distribution to ensure that the
   behavior of those tools does not change unexpectedly.

#. Use checksums to ensure the downloaded files have not changed.

#. Separate out single and multiple deployment test jobs. If the DUT
   can support OE and AOSP or ramdisk and NFS, submit one test job for
   each variant **as well as** a functional test explicitly designed to
   test that the DUT can run a test in one environment and be
   redeployed with a new environment, if that can be supported.

#. Ensure that advanced LAVA software functionality is also covered by
   submitting representative :term:`MultiNode` test jobs, especially if
   the staging instance is capable of supporting :term:`VLANd`

#. Unreliable functional tests need to be triaged and removed if the
   problems cannot be fixed. This may lead to the underlying code
   support being deprecated or removed, including a device-type
   template.

#. Unreliable devices need to be triaged and test jobs using those
   devices removed from the functional tests if the problems cannot be
   fixed. If those devices are the sole use of a particular deployment
   method or boot method, then that code support needs to be reviewed
   and possibly removed.

#. If firmware has to be upgraded on devices and the functional test
   needs changes, create a new functional test with new metadata.
   Remove the old functional test unless devices running the old
   firmware remain available using a separate device-type.

#. Removing a functional test requires a review to remove source code
   support for a deployment method, boot method, device-type template
   etc.

#. Email notifications are optional but can be useful. Use sparingly
   to avoid flooding the developers with noise.

#. If a particular device or deployment method or boot method is not
   covered by at least one functional test, add a new functional test
   and/or add meta-lava support.

   If a test job exists which cannot be made into a functional test,
   and meta-lava support is not available, the code support for the
   affected method will need to be reviewed with a view to probable
   removal.

#. Test job definitions also remain static.

   #. No changes in prompts, metadata, image files, checksums, LXC
      suites or submitter.

   #. Changes to timeouts only by code review to handle resource
      limitations.

   #. Infrastructure to remain static, as far as possible. Only change
      ports (PDU, USB etc.) when failures have been identified. As much
      as possible, leave the devices undisturbed in the racks.

   #. Minimal work done in the test shell definitions. Smoke tests and
      setup checks if specific external hardware is configured, e.g.
      ARM Energy Probe. Any setup code **must** use ``lava-test-raise``
      for all known failure modes.

#. Devices are checked as per the current ``master`` branch
   configuration.

   #. Devices which do not have full support already merged are **not**
      candidates for functional testing.

   #. Test job use cases for which the device support is still in
      development are **not** candidates for functional testing.

   #. Test jobs which download third-party software which may change
      outside the control of the functional test are **not** candidates
      for functional testing.

Test jobs and use cases outside of these requirements can still be
submitted on a regular basis but **not** using the same metadata or
job submitter as the functional tests. Completion of these test jobs
will **not** count towards the functional test report. Consider using
the notification support to send email to developers when such tests
finish in state Incomplete as there will be no other coverage for
such failures.

.. seealso:: :ref:`change_one_thing`

Using the functional test frontend
**********************************

The LAVA software team will be setting up a dedicated frontend to run
functional tests across multiple instances to increase the functional
test coverage to include devices not available in the current
instances.

This service will coordinate:

* The list of test job submissions used in functional testing.

* The set of test shell definitions used in functional testing.

* The submission of functional tests to instances according to device
  availability, as determined using the XML-RPC API.

* The selection of the appropriate workers for available devices on
  each instance, using the relevant build of the master branch.

* The retrieval of functional test results from multiple instances.

* The display of a summary of the functional tests for a specific
  build of the master branch.

Dedicated workers
=================

If your instance has a mix of devices, some with upstream LAVA support
and some without (or with support in development / review), then one or
more dedicated workers will be needed to work with the functional test
frontend.

Any one piece of hardware can run multiple ``lava-worker`` processes, as
long as the ``hostname`` option is unique.

For functional testing, the worker will need to be running a specific
build of the master branch, so docker based workers will need to be
available.

During the functional tests, the relevant devices will be switched to
the functional test worker in the relevant docker container (API is yet
to be scoped) before test job submissions start. When all functional
test jobs are complete, the devices are switched back to the original
worker.

Currently, functional testing occurs on
https://staging.validation.linaro.org/ and more work is needed to
support combining results across multiple staging instances. More
content will be added here as the relevant services are developed.
