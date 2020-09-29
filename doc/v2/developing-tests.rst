.. index:: writing tests - introduction

.. _test_developer:

Writing Tests
#############

The LAVA dispatcher currently supports tests being run in a number of
ways:

* :ref:`Lava-Test Test Definition 1.0 <writing_tests_1_0>` (POSIX
  shell based testing) using an overlay.

  * lava-test-case handling

  * MultiNode support

  * inline test definitions

  * regular expression pattern matching

* :ref:`LAVA Test Monitor <writing_tests_monitor>` (simple pass/fail
  pattern matching)

* :ref:`Interactive <writing_tests_interactive>` (direct control over
  the test device)

.. PatternFixup does not make it into Lava-Test Test Definition 2.0

The most common style of test currently in use is the ``Lava-Test Test
Definition 1.0`` using ``lava-test-case``. During the deploy action, an
overlay is added to the :term:`DUT` filesystem including the test
writer commands and LAVA helper scripts. The test action uses a helper
script to execute the test writer commands and other helper scripts are
used to report test results back to the dispatcher, wrapping results in
special marker text to allow for easy identification. The dispatcher
parses out those test results and reports them alongside the test job
log output. Test Shell Definitions contain individual inline commands
or references to repositories to deploy custom scripts using a variety
of programming languages, according to the support available on the
DUT.

Introduction to the LAVA Test Developer Guide
*********************************************

This guide aims to enable users to be able to

#. Submit desired jobs/tests on targets deployed where the LAVA server is
   located and report results.

#. Understand how test job files need to be written so that jobs get submitted
   properly.

#. Understand the options for running the test operation. No one test
   method can suit all test operations or all devices.

#. Understand how test shell definitions need to be written, depending
   on how the test should be executed.

Pay particular attention to sections on:

* :ref:`writing_pipeline_submission`
* :ref:`writing_test_commands`
* :ref:`custom_scripts`
* :ref:`best_practices`

Guide Contents
==============

* :ref:`dispatcher_actions`
* :ref:`lava_test_shell`
* :ref:`test_definition_portability`
* :ref:`writing_tests_monitor`
* :ref:`writing_tests_interactive`

Assumptions at the start of this guide
======================================

#. The desired board is already configured for use with a LAVA Server instance.

#. A user account (username, password, email address) is already created by a
   LAVA administrator on your behalf, with permissions to submit jobs.

#. ``lavacli`` is already installed on your test system and a suitable
   authentication token has been added.

#. You are familiar with submitting jobs written by someone else, including
   viewing the logs file for a job, viewing the definition used for that job
   and accessing the complete log.

.. If your desired board is not available in the LAVA instance you want to
   use, see :ref:`deploy_boards`.

To install ``lavacli``, see :ref:`lavacli`.

To authenticate ``lavacli``, see :ref:`authentication_tokens`.

To find out more about submitting tests written by someone else, see
:ref:`submit_first_job`.

To find out more about viewing job details, see :ref:`job_submission`.

.. index:: availability

Checking device availability
****************************

Use the LAVA scheduler to view the device types and devices available
in your LAVA instance. The main scheduler status page shows data for
each :term:`device type` as well as the currently active jobs. Also
check the Devices pages:

* All Devices - includes retired devices to which jobs cannot be submitted.

* All Active Devices - lists only devices to which jobs can be submitted

* All Devices Health - limited to just the latest health status of each device.

* My Devices - available from your profile menu by clicking on your
  name once signed into the instance.

For a :ref:`MultiNode <writing_multinode>` job, you may need to check
more than one :term:`device type`.

LAVA looks at the :ref:`device health <device_status>` when working
out if a particular device is available for a new job:

* Good, Unknown - jobs can be submitted OK.

* Restricted - only specific users may submit jobs.

* Retired - this device is not available; jobs will be rejected if all
  devices of this type are retired.

Finding an image to run on the device
*************************************

Typically, the easiest thing to do here is to start with an image
which is already in use in LAVA. You can find one of these images by
checking the :term:`device type` in LAVA and viewing some of the jobs
for devices of this type from the table on that page. e.g. for QEMU
devices on validation.linaro.org:

https://validation.linaro.org/scheduler/device_type/qemu

Actions to be run for a LAVA test
*********************************

There are three important sets of actions that will normally be run
for a LAVA test:

#. **Deploy**: The actions needed to set up a device to boot a test
   image. Each device type may support a range of different deployment
   methods.

#. **Boot**: The steps to follow to start the test image on the
   device. Each device type may support a range of different boot
   methods.

#. **Test**: Run the lava test definition, running the specified tests.
   All methods use the ``test`` action. Syntax varies according to
   the method chosen.

Example of Lava Test
********************

This example will use syntax for the Lava-Test Test Definition 1.0 as
well as covering device tags and checksums which may be useful for all
test jobs.

Deploying a pre-built QEMU image
================================

.. code-block:: yaml

  actions:
    - deploy:
        timeout:
          minutes: 5
        to: tmpfs
        images:
            rootfs:
              image_arg: -drive format=raw,file={rootfs}
              url: https://files.lavasoftware.org/components/lava/standard/debian/stretch/amd64/2/stretch.img.gz
              compression: gz

.. index:: device tag example

.. _device_tags_example:

Using device tags
=================

A :term:`device tag` marks a specified device as having specific
hardware capabilities which other devices of the same :term:`device
type` may not. To test these capabilities, a test job can specify a
list of tags which the device **must** support. If no devices exist
which match all of the required tags, the job submission will fail. If
devices support a wider range of tags than required in the test job
(or the test job requires no tags), any of those devices can be used
for the test job.

.. note:: Test jobs which use :term:`device tag` support can **only**
   be submitted to instances which have those tags defined **and**
   assigned to the requested boards. In your LAVA instance, check the
   device information to see what tags are used.

When writing a normal single-node test job, the desired tags should be
listed as a top level list of strings in the job definition, i.e. at
the same level as ``job_name``, ``timeouts``, ``metadata`` and
``device_type``:

.. code-block:: yaml

    # Your first LAVA JOB definition for an x86_64 QEMU
    device_type: qemu
    job_name: QEMU pipeline, first job

    tags:
    - tap_device
    - virtual_io

    timeouts:
      job:
        minutes: 15
      action:
        minutes: 5
    priority: medium
    visibility: public

    # context allows specific values to be overridden or included
    context:
      # tell the qemu template which architecture is being tested
      # the template uses that to ensure that qemu-system-x86_64 is executed.
      arch: amd64

    metadata:
      # please change these fields when modifying this job for your own tests.
      docs-source: first-job
      docs-filename: qemu-pipeline-first-job.yaml

For :term:`MultiNode` test jobs, the tags are defined as
part of the MultiNode protocol block:

.. code-block:: yaml

    protocols:
      lava-multinode:
        roles:
          client:
            device_type: qemu
            context:
              arch: amd64
            count: 1
            # In this example, only one role in the group uses tags
            tags:
            - tap_device
            - virtual_io
          server:
            device_type: qemu
            context:
              arch: amd64
            count: 1
        timeout:
          seconds: 60

Device tags are only relevant during scheduling of the test job and
have no meaning to the dispatcher once the job is running.

.. index:: checksum

.. _testjob_checksums:

Using checksums
===============

If an MD5 or SHA256 checksum is provided alongside the URL of the file to be
used in a test job, the downloaded content will be checked against the provided
checksum. The test job will fail as ``Incomplete`` if the checksum fails to
match.

Avoid using URLs which include shortcuts like ``latest`` when providing
the checksum. Specify the full URL to ensure consistency between tests.

.. seealso:: :ref:`make_tests_verbose`

Using Lava-Test Test Definition 1.0
===================================

The ``Lava-Test Test Definition 1.0`` action provides a way to employ a
black-box approach to testing on the target device. Its format is:

.. code-block:: yaml

    - test:
        failure_retry: 3
        name: kvm-basic-singlenode
        timeout:
          minutes: 5
        definitions:
            - repository:
                metadata:
                    format: Lava-Test Test Definition 1.0
                    name: smoke-tests-basic
                    description: "Basic system test command for Linaro Ubuntu images"
                run:
                    steps:
                        - printenv
              from: inline
              name: env-dut-inline
              path: inline/env-dut.yaml
            - repository: git://git.linaro.org/lava-team/lava-functional-tests.git
              from: git
              path: lava-test-shell/smoke-tests-basic.yaml
              name: smoke-tests
            - repository: https://git.linaro.org/lava-team/lava-functional-tests.git
              from: git
              path: lava-test-shell/single-node/singlenode03.yaml
              name: singlenode-advanced

The ``definitions`` list here may contain multiple test definition
URLs. These will all be run sequentially in one run on the test
device, and it will not be rebooted between the definitions.

.. seealso:: :ref:`Dispatcher Actions <test_action_definitions>`

.. seealso:: ``lava_test_shell`` `developer documentation <lava_test_shell.html>`_
