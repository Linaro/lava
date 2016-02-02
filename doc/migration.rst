.. index:: migrations

.. _migrating_to_pipeline:

Migrating to the Pipeline Dispatcher
####################################

Basics
******

#. Understand the **objectives** of the current test job
#. Revise the Test Plan.
#. Use protocols and/or device configuration for any operation which
   is more than typing commands into a shell.
#. Use **comments** - the pipeline uses YAML submissions, so describe
   what the job is trying to do and why in comments - just start the
   line with ``#``.
#. Simplify the test job to make best use of the new functionality.
#. Master images are not necessary - the test writer can implement
   fallbacks to known working images for specific tasks.
#. Bundles do not exist, there is no submit action.
#. Start at the bootloader.
#. Support is being widened - :ref:`contact us <getting_support>` for
   specific information.

Specific information and guides
===============================

Test Writers
------------

.. toctree::
   :maxdepth: 2

   pipeline-writer.rst

Administrators
--------------

.. toctree::
   :maxdepth: 2

   pipeline-admin.rst

Understanding test job objectives
*********************************

.. warning:: The migration to a pipeline job is **not** a simple case of
   reformatting JSON. There is no direct equivalence between the old JSON
   and the pipeline YAML. It is imperative that the test writer fully
   understands the reasons why the old JSON job does the things it does
   before starting to migrate that job to the pipeline.

#. Is there pipeline support for the test device type?
#. How does the test job deploy the test files?
#. How does the test job boot the device?
#. Which test definitions can be joined into a single test action,
   which will need a simple reboot and which might need another
   deploy step?

Pipeline support
================

The pipeline support is changing the way that the test jobs run so that
some device types change and some multinode jobs can become single node.
e.g. the old KVM device type is now QEMU, with the architecture of the
QEMU binary specified by the test job. Equally, the availability of LXC
and other protocols means that there is often no need for a KVM to run
ADB or other components.

Viewing the available support
-----------------------------

XMLRPC: scheduler.get_pipeline_device_config
Device type detail: Deployment, boot and protocol tabs.

.. FIXME: needs expansion.

Deployments
===========

The range of deployments available in the pipeline dispatcher are being
enlarged, according to what Test Plans are required. Talk to the
Automation & CI team at Linaro about how to coordinate the needs of your
team with the available support and the planned developments.

The deployments for a pipeline job determine how the test files and the
LAVA test shell overlay files are delivered to the device prior to boot.
This can include making the files available for TFTP or copying the
files over to a running device using SCP.

The deployment method chosen must match the boot method requirements
and it is up to the test writer to ensure that a valid combination of
deployment and boot methods are used.

Boot methods
============

The boot method dictates how the device is instructed to boot. Depending
on the method, this will usually also involve how to deliver the deployed
files to the device, e.g. using TFTP, as well as controlling the commands
sent to the device to set boot options and commands.

Protocol support
================

The :ref:`multinode_protocol` is common to all device types. Other
protocols may require specific configuration for the device type or
not be available for all devices or on all instances.
