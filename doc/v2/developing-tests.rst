.. _test_developer:

Introduction to the LAVA Test Developer Guide
#############################################

This guide aims to enable engineers to be able to

#. Submit desired jobs/tests on target deployed where the LAVA server
   is located and report results.
#. Understand how test job files need to be written so that jobs get
   submitted properly.
#. Understand how test shell definitions need to be written.

Ensure you have read through the introduction on
:ref:`writing_tests`.

Pay particular attention to sections on:

* :ref:`writing_pipeline_submission`
* :ref:`writing_test_commands`
* :ref:`custom_scripts`
* :ref:`best_practices`

Guide Contents
**************

* :ref:`new_dispatcher_actions`
* :ref:`lava_test_shell`
* :ref:`multinode`

Assumptions at the start of this guide
**************************************

#. The desired board is already deployed at the LAVA Server location.
#. A user account (username, password, email address) is already created
   by a LAVA administrator on your behalf, with permissions to submit jobs.
#. ``lava-tool`` is already installed on your test system and a suitable
   token has been added.
#. You are familiar with submitting jobs written by someone else, including
   viewing the logs file for a job, viewing the definition used for that
   job and accessing the complete log.

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

Use the LAVA scheduler to view available device types and devices. The
main scheduler status page shows data for each :term:`device type` as
well as the currently active jobs. Also check the Devices pages:

* All Devices - includes retired devices to which jobs cannot be
  submitted.
* All Active Devices - lists only devices to which jobs can be submitted
* All Devices Health - limited to just the latest health status of each
  device.
* My Devices - available from your profile menu by clicking on your
  name once signed into the instance.

For a :ref:`multinode` job, you may need to check more than one
:term:`device type`.

Devices are considered available for new jobs according to the
:ref:`device_status`.

* Idle, Reserved, Offline, Offlining - jobs can be submitted.
* restricted - only available for submissions made by declared users.
* Retired - jobs will be rejected if all remaining devices of this type
  are retired.

Finding an image to run on the device
*************************************

Start with an image which is already in use in LAVA. You can find one
of these images by checking the :term:`device type` in LAVA and viewing
some of the jobs for devices of this type from the table on that page.
e.g. for QEMU devices on validation.linaro.org:

https://validation.linaro.org/scheduler/device_type/qemu

Actions to be run for a LAVA test
*********************************

#. Deploy: Each device type supports a range of deployment
   methods.
#. Boot: Each device type supports a range of boot methods.
#. Test: Run the lava test shell.

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
              url: http://images.validation.linaro.org/kvm-debian-wheezy.img.gz
              compression: gz
        os: debian

.. _device_tags_example:

Using device tags
=================

A :term:`device tag` marks a specified device as having specific hardware
capabilities which other devices of the same :term:`device type` do not.
To test these capabilities, a Test Job can specify a list of tags which
the device **must** support. If no devices exist which match all of the
required tags, the job submission will fail. If devices support a wider
range of tags than required in the Test Job (or the Test Job requires
no tags), any of those devices can be used for the Test Job.

.. note:: Test jobs which use :term:`device tag` support can **only** be
          submitted to instances which have those tags defined **and**
          assigned to the requested boards. Check the device information
          on the instance to get the correct tag information.

Using LAVA Test Shell
=====================

The ``lava_test_shell`` action provides a way to employ a more black-box style
testing approach with the target device. The action only requires that a
deploy action (deploy_linaro_image/deploy_linaro_android_image) has been
executed. Its format is:

.. code-block:: yaml

    - test:
        failure_retry: 3
        name: kvm-basic-singlenode  # is not present, use "test $N"
        # only s, m & h are supported.
        timeout:
          minutes: 5 # uses install:deps, so takes longer than singlenode01
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
              # name: if not present, use the name from the YAML. The name can
              # also be overriden from the actual commands being run by
              # calling the lava-test-suite-name API call (e.g.
              # `lava-test-suite-name FOO`).
              name: smoke-tests
            - repository: http://git.linaro.org/lava-team/lava-functional-tests.git
              from: git
              path: lava-test-shell/single-node/singlenode03.yaml
              name: singlenode-advanced

You can put multiple test definition URLs in "definitions"
list. These will be run sequentially without reboot.

.. seealso:: :ref:`Dispatcher Actions <test_action_definitions>`

.. seealso:: ``lava_test_shell`` `developer documentation <lava_test_shell.html>`_
