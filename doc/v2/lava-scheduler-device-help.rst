.. _device_help:

Detailed device information in LAVA Scheduler
#############################################

.. _static_device_information:

Static device information
*************************

* **Hostname** - The unique name of this device in this LAVA instance,
  used to link all jobs, results and device information to a specific
  device configuration. The name does not necessarily relate to a
  specific piece of hardware - administrators can replace hardware at
  any time without needing to change any device details.

* **Device type** See :term:`device type`.

  .. seealso:: :ref:`jinja_template_triage` and :ref:`template_mismatch`

* **Owner** - If ``Restriction`` is not **Public**, submissions are
   restricted to the specified user or group. Administrators can
   restrict submissions by unchecking the ``Public`` option for the
   device in the admin interface.

* **Restriction** - ``Public`` or a listed user or group set by the
  administrators.

* **Device tags** - Device specific labels to allow test jobs to
  request specific hardware capabilities. A :term:`device tag` can only
  be used in a TestJob if supported by a device of the relevant device
  type.

* **State** - :ref:`device_status`

* **Health** - :ref:`device_status`

* **Worker Hostname** - The dispatcher which has a configuration file
  for a device matching the hostname. Note that this is the result of
  checking the network communication between the dispatcher and the
  server, not the serial connection between the dispatcher and the
  board.

* **Device dictionary** - link to the device dictionary information.

* **Physical access** - The user with :term:`physical access` to the
  device.

* **Description** - Free text description of this individual device.
  This field can be used to give more information about the device.
  This field can be edited by the lab administrators.

* **Device version** - Optional field which can be edited by the lab
  administrators.

.. index:: status

.. _device_status:

Device state
************

State
=====

Describes the current device status which can be one of:

* **Idle** - available for job submissions, subject to device ownership
  restrictions

* **Running** - the device is running a test job. A link to the job
  will appear below this section of the page.

* **Reserved** - the device is part of a :term:`MultiNode` job but one
  or more other devices in the same job is not currently available.
  (Reserved is also used for single node jobs but the device quickly
  moves into Running.)

Health
======

Health State
============

State of the health of the device, used to schedule a :term:`health
check`, if health checks have not been disabled for the :term:`device
type`. If the health status is ``Unknown``, a health check will be run
as soon as the device has finished any current job but before starting
any other submitted job.

* **Good** - the previous health check completed successfully. The
  device is available for immediate scheduling.

* **Unknown** - the device has not run a health check, either because
  a health check has not been defined for the :term:`device type` or
  health checks have been disabled for this device type.

* **Bad** - temporarily not available for scheduling due to a
  :term:`health check` failure. Test jobs can still be submitted. If no
  other devices of this :term:`device type` have Good or Unknown
  health, test jobs will be held in the Queue.

* **Maintenance** - temporarily not available for scheduling due to a
   manual admin action, possibly for short term maintenance. Test jobs
   can still be submitted. If no other devices of this :term:`device
   type` have Good or Unknown health, test jobs will be held in the
   Queue.

* **Looping** - an administrator mode which continuously submits a
  health check each time the previous health check completes,
  **irrespective** of how that health check finished. This is used to
  test health checks, devices and infrastructure. Looping is
  particularly useful to provide data to assist when triaging
  intermittent test job, device or infrastructure failures.

* **Retired** - the device may have been relocated to another server,
  or failed due to a hardware fault or some other physical problem with
  the device. Contact the device owner or the user with physical access
  for more information.

.. index:: device description

.. _edit_device_description:

Edit device description
=======================

Administrators can edit a free text description of this individual
device. Suggested content includes more information about the specific
device, the reasons for restricting submissions, information about the
device owner and the purposes for which the device is used etc. Text
can include links to external sites for more information.

It can be particularly useful to expand on the
:ref:`device_capabilities` by adding details which cannot be easily
identified at runtime, e.g. big.LITTLE details or particular hardware
features available on this specific device.

.. index:: restricted

.. _restrict_device:

Restrict submissions
====================

Administrators can restrict devices so that new job submissions will
only be accepted from the device owner. If the device owner is a group,
any user in that group will be able to submit new jobs.

Any currently running jobs will complete normally, unless the device
owner cancels the job.

Administrators are strongly recommended to edit the device description
in such a way as to explain why the restriction is necessary and how
long the restriction may last.
