.. index:: standard jessie qemu

.. _standard_amd64_jessie_qemu:

Standard test job for QEMU - Jessie amd64
#########################################

The first standard job to look at is a small step on from the first
example job:

.. include:: examples/test-jobs/qemu-amd64-standard-jessie.yaml
     :code: yaml
     :end-before: metadata:

`Download / view full job definition <examples/test-jobs/qemu-amd64-standard-jessie.yaml>`_

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
==========

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
