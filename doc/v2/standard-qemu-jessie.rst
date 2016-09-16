.. index:: standard qemu jessie

.. _using_gold_standard_files:

Using the standard test jobs
############################

The next step after the :ref:`first example job <explain_first_job>`, is to
move on to the *gold standard* test jobs. These include a test job for QEMU and
test jobs for readily available ARM devices like *cubietruck* and
*beaglebone-black*.

.. seealso:: :ref:`creating_gold_standard_files`

Test writers are strongly recommended to follow these examples to have a known
working setup for later test jobs. These standard test jobs are part of the
regular functional testing performed by the LAVA software team prior to each
release. If you have problems debugging a test job failure on any instance of
LAVA, your recommended first action is to submit the closest standard test job
and compare the results against other instances like
``staging.validation.linaro.org``. To make this easier, all test writers are
recommended to use version control for all test jobs and to keep a local copy
of the closest standard test job for quick reference.

.. note:: A gold standard deployment for one device type is not necessarily
   supported for a second device type. Some devices will never be able to
   support all deployment methods due to hardware constraints or the lack of
   kernel support. This is **not** a bug in LAVA. If a particular deployment is
   supported but not stable on a device type, there will not be a gold standard
   image for that deployment. Any issues in the images using such deployments
   on that type are entirely down to the test writer to fix.

.. note:: Device type templates and other instance-specific configuration could
   affect the standard test jobs on specific instances. If a standard test job
   fails, check with the admins for that particular instance. The standard
   tests described here use support in the default device-type templates
   shipped with LAVA and are routinely tested on
   ``staging.validation.linaro.org``.

Metadata
********

Standard test jobs include metadata which links the test job back to the build
information, logs and scripts.

Ensure that you change the **metadata** to point at your local repository so
that you can easily distinguish between the results with and without your
modifications:

.. include:: examples/test-jobs/qemu-amd64-standard-jessie.yaml
     :code: yaml
     :start-after: visibility: public
     :end-before: context:

The set of gold standard jobs has been defined in association with the Linaro
QA team. These jobs will provide a known baseline for test definition writers,
in a similar manner to the way the existing QA test definitions provide a base
for more elaborate testing.

.. _standard_amd64_jessie_qemu:

Standard QEMU test job for Jessie
*********************************

The first standard job to look at is a small step from the first example job:

.. include:: examples/test-jobs/qemu-amd64-standard-jessie.yaml
     :code: yaml
     :end-before: metadata:

`Download / view <examples/test-jobs/qemu-amd64-standard-jessie.yaml>`_

Context
=======

Some :term:`device types <device type>` can support multiple types of
deployment in the template and the :term:`job context` variable is used in the
test job submission to dictate how the test job is executed. The first example
test job included the use of ``context`` and the standard test job for QEMU
extends this:

.. include:: examples/test-jobs/qemu-amd64-standard-jessie.yaml
     :code: yaml
     :start-after: CONTEXT_BLOCK
     :end-before: # ACTIONS_BLOCK

arch
----

The context variable ``arch`` dictates which QEMU binary is used to execute the
test job. The value needs to match the architecture of the files which QEMU is
expected to execute. In this case, ``amd64`` means that ``qemu-system-x86_64``
will be used to run this test job.

netdevice
---------

The context variable ``netdevice`` is used by the jinja template to instruct
QEMU to use the ``tap`` device on the command line. This support expects that
the dispatcher has a working network bridge available. (Setting up a network
bridge is beyond the scope of this documentation.) The purpose of the ``tap``
device is to allow the virtual machine to be visible for external connections
like reverse DNS and SSH. If your local instance does not support the tap
device, the ``netdevice`` option should be commented out so that QEMU can use
the default ``user`` networking support.

Deploy
======

This is also familiar from the first job. The addition here is that the
standard image build exports the SHA256sum of the prepared files to allow the
checksum to be passed to LAVA to verify that the download is the correct file:

.. include:: examples/test-jobs/qemu-amd64-standard-jessie.yaml
     :code: yaml
     :start-after: ACTIONS_BLOCK
     :end-before: # BOOT_BLOCK

Boot
====

Here is another small change from the first example job. The standard build
also outputs details of the prompts which will be output by the image upon
boot. This information is then used in the test job submission:

.. include:: examples/test-jobs/qemu-amd64-standard-jessie.yaml
     :code: yaml
     :start-after: BOOT_BLOCK
     :end-before: # TEST_BLOCK

Test
====

The standard QEMU test job for jessie adds an :term:`inline` test definition as
the only change from the example first job:

.. include:: examples/test-jobs/qemu-amd64-standard-jessie.yaml
     :code: yaml
     :start-after: TEST_BLOCK

Next steps
**********

Before moving on to the next standard test jobs for non-emulated devices like
the beaglebone-black and cubietruck, consider spending some time developing the
standard QEMU test job:

* Add more commands to the inline test definition
* Follow the link from the metadata and use the instructions to rebuild the
  image.

  * Modify the metadata to point at your build information
  * Modify the SHA256sum and the URL in the deploy action.

* Write a new test definition using version control and make it available
  publicly, then add that definition to your test job based on this first
  standard test job.

.. toctree::
   :hidden:
   :maxdepth: 1

   standard-armmp-ramdisk-bbb.rst
