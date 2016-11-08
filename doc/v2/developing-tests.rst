.. index:: writing tests

.. _test_developer:

Writing Tests
#############

Introduction to the LAVA Test Developer Guide
*********************************************

This guide aims to enable users to be able to

#. Submit desired jobs/tests on targets deployed where the LAVA server is
   located and report results.

#. Understand how test job files need to be written so that jobs get submitted
   properly.

#. Understand how test shell definitions need to be written.

Ensure you have read through the introduction on :ref:`writing_tests`.

Pay particular attention to sections on:

* :ref:`writing_pipeline_submission`
* :ref:`writing_test_commands`
* :ref:`custom_scripts`
* :ref:`best_practices`

Guide Contents
==============

* :ref:`dispatcher_actions`
* :ref:`lava_test_shell`

Assumptions at the start of this guide
======================================

#. The desired board is already configured for use with a LAVA Server instance.

#. A user account (username, password, email address) is already created by a
   LAVA administrator on your behalf, with permissions to submit jobs.

#. ``lava-tool`` is already installed on your test system and a suitable token
   has been added.

#. You are familiar with submitting jobs written by someone else, including
   viewing the logs file for a job, viewing the definition used for that job
   and accessing the complete log.

.. If your desired board is not available in the LAVA instance you want to
   use, see :ref:`deploy_boards`.

To install ``lava-tool``, see :ref:`lava_tool`.

To authenticate ``lava-tool``, see :ref:`authentication_tokens`.

To find out more about submitting tests written by someone else, see
:ref:`submit_first_job`.

To find out more about viewing job details, see :ref:`job_submission`.

.. index:: availability

Checking device availability
****************************

Use the LAVA scheduler to view available device types and devices. The main
scheduler status page shows data for each :term:`device type` as well as the
currently active jobs. Also check the Devices pages:

* All Devices - includes retired devices to which jobs cannot be submitted.

* All Active Devices - lists only devices to which jobs can be submitted

* All Devices Health - limited to just the latest health status of each device.

* My Devices - available from your profile menu by clicking on your
  name once signed into the instance.

For a :ref:`writing_multinode` job, you may need to check more than one
:term:`device type`.

Devices are considered available for new jobs according to the
:ref:`device_status`.

* Idle, Reserved, Offline, Offlining - jobs can be submitted.

* Restricted - only available for submissions made by declared users.

* Retired - jobs will be rejected if all remaining devices of this type are
  retired.

Finding an image to run on the device
*************************************

Start with an image which is already in use in LAVA. You can find one of these
images by checking the :term:`device type` in LAVA and viewing some of the jobs
for devices of this type from the table on that page. e.g. for QEMU devices on
validation.linaro.org:

https://validation.linaro.org/scheduler/device_type/qemu

Actions to be run for a LAVA test
*********************************

There are three important sets of actions that will be run for a LAVA test:

#. Deploy: The information needed to set up a device to boot a test image. Each
   device type supports a range of deployment methods.

#. Boot: The steps to follow to start the test image on the device. Each device
   type supports a range of boot methods.

#. Test: Run the lava test shell, running the specified tests.

Examples
********

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
              url: https://images.validation.linaro.org/kvm/standard/stretch-2.img.gz
              compression: gz
        os: debian

.. index:: device tag

.. _device_tags_example:

Using device tags
=================

A :term:`device tag` marks a specified device as having specific hardware
capabilities which other devices of the same :term:`device type` do not. To
test these capabilities, a Test Job can specify a list of tags which the device
**must** support. If no devices exist which match all of the required tags, the
job submission will fail. If devices support a wider range of tags than
required in the Test Job (or the Test Job requires no tags), any of those
devices can be used for the Test Job.

.. note:: Test jobs which use :term:`device tag` support can **only** be
   submitted to instances which have those tags defined **and** assigned to the
   requested boards. Check the device information on the instance to get the
   correct tag information.

For singlenode jobs, tags are a top level list of strings in the job
definition, the same level as ``job_name``, ``timeouts``, ``metadata`` and
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

For :term:`multinode` test jobs, the tags are defined as part of the MultiNode
protocol:

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

Device tags are only relevant during scheduling of the testjob and have no
meaning to the dispatcher.

Using LAVA Test Shell
=====================

The ``lava_test_shell`` action provides a way to employ a black-box style
testing approach with the target device. Its format is:

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
            - repository: git://git.linaro.org/qa/test-definitions.git
              from: git
              path: ubuntu/smoke-tests-basic.yaml
              name: smoke-tests
            - repository: https://git.linaro.org/lava-team/lava-functional-tests.git
              from: git
              path: lava-test-shell/single-node/singlenode03.yaml
              name: singlenode-advanced

The "definitions" list here may contain multiple test definition URLs. These
will all be run sequentially in one go; the system will not be rebooted between
the definitions.

.. seealso:: :ref:`Dispatcher Actions <test_action_definitions>`

.. seealso:: ``lava_test_shell`` `developer documentation <lava_test_shell.html>`_
