.. index:: migrations, migrating to V2

.. _migrating_to_pipeline:

Migrating to LAVA V2
####################

Basics
******

#. Understand the **objectives** of the current test job.

   .. seealso:: :ref:`test_job_objectives`

#. Revise the Test Plan.

#. Use protocols and/or device configuration for any operation which is more
   than typing commands into a shell. If the V1 job required :term:`MultiNode`
   to be able to install custom software necessary to interact with the device,
   these commands should be executed using the :ref:`lxc_protocol_reference`
   which removes the need for MultiNode.

   * Test Jobs which used MultiNode in V1 in this way will also include calls
     to the :ref:`multinode_api` and these will need to be removed from the
     test definitions.

   .. seealso:: :ref:`protocols` and :ref:`test_definition_portability`.

#. Use **comments** - the pipeline uses YAML submissions, so describe what the
   job is trying to do and why in comments - just start the line with ``#``.

#. Simplify the test job to make best use of the new functionality.

#. Master images are not necessary - the test writer can implement fallbacks to
   known working images for specific tasks.

#. Start with :ref:`using_gold_standard_files`

#. Look for V2 jobs running on the same or similar :term:`device types <device
   type>`

#. Bundles no longer exist and there is no submit action. Results are reported
   live as the test job runs. Results can be downloaded or exported using the
   :ref:`results API <results_rest_api>`.

#. If the resuults of your V1 jobs were being retrieved or processed by another
   service, ensure that the calls are adapted to the new :ref:`results API
   <results_rest_api>`.

#. Filters and Image Reports (including Image Reports 2.0) have been
   **replaced** by :ref:`Queries and Charts <result_queries>`.

#. Certain :term:`device-types <device type>` have changed. In particular, to
   start with the simplest V2 test job, you will typically be submitting a job
   to the ``qemu`` device-type instead of ``kvm`` in V1.

Specific information and guides
===============================

Migrating to LAVA V2 is not a trivial process. It is recommended to start by
understanding how simple test jobs run, including starting from
:ref:`submitting your first V2 test job <submit_first_job>`.

Test Writers
------------

.. toctree::
   :maxdepth: 2

   first-job
   pipeline-writer
   developing-tests
   standard-test-jobs
   results-intro

Administrators
--------------

.. toctree::
   :maxdepth: 2

   pipeline-admin

.. _test_job_objectives:

Understanding test job objectives
*********************************

.. warning:: The migration to a pipeline job is **not** a simple case of
   reformatting JSON. There is no direct equivalence between the old JSON and
   the pipeline YAML. It is imperative that the test writer fully understands
   the reasons why the old JSON job does the things it does before starting to
   migrate that job to the pipeline. The migrated test job needs to provide
   equivalent validation to the V1 test job but that does not mean that the
   test job needs to work in the same or even a similar manner.

#. Is there pipeline support for the test device type?

#. How does the test job deploy the test files?

   * Does the V1 test job use a ``master image``? This support has been
     replaced in V2. In general, devices simply boot directly from the
     bootloader. Where this is problematic, test jobs can use use
     :ref:`secondary_media`.

#. How does the test job boot the device?

   * Does the V1 test job use ``linaro-media-create`` or download a ``hwpack``?
     This support has been **removed** and the files provided to the device
     using V2 will need to be in the form which the device can use directly.

#. Which test definitions can be joined into a single test action,
   which will need a simple reboot and which might need another
   deploy step?

#. Which test definitions use ``lava-test-case-attach``? These will need to be
   ported to :ref:`the Publishing API <publishing_artifacts>`.

Pipeline support
================

The pipeline support is changing the way that the test jobs run so that some
device types change and some multinode jobs can become single node. e.g. the
old KVM device type is now QEMU, with the architecture of the QEMU binary
specified by the test job. Equally, the availability of LXC and other protocols
means that there is often no need for a KVM to run ADB or other components.

Viewing the available support
-----------------------------

The :ref:`XML-RPC <xml_rpc>` call ``scheduler.get_pipeline_device_config`` can
provide the full configuration for a device, including all the deployment and
boot methods supported by that device and device-type on that instance.

The Device type detail page has a Support tab which contains details of the
methods supported by devices of this device type.

.. note:: Not all devices of any one device type necessarily support all
   methods of that type. e.g. some methods require additional hardware to
   be fitted. Check the :term:`device tags <device tag>` and other jobs running
   on devices of the same type.

.. seealso:: :ref:`dispatcher_actions`

Deployments
===========

.. seealso:: :ref:`deploy_action`

The deployments for a LAVA V2 test job determine how the test files and the
LAVA test shell overlay files are delivered to the device prior to boot. This
can include making the files available for TFTP or copying the files over to a
running device using SCP.

The deployment method chosen must match the boot method requirements and it is
up to the test writer to ensure that a valid combination of deployment and boot
methods are used.

Boot methods
============

.. seealso:: :ref:`boot_action`

The boot method dictates how the device is instructed to boot. Depending on the
method, this will usually also involve how to deliver the deployed files to the
device, e.g. using TFTP, as well as controlling the commands sent to the device
to set boot options and commands.

Protocol support
================

.. seealso:: :ref:`protocols`

The :ref:`multinode_protocol` is common to all device types. Other protocols
may require specific configuration for the device type or not be available for
all devices or on all instances.
