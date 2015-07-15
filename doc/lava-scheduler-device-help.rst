.. _device_help:

Detailed device information in LAVA Scheduler
#############################################

.. _static_device_information:

Static device information
*************************

  **Hostname**
    The unique name of this device in this LAVA instance, used to link all
    jobs, results and device information to a specific device configuration.

  **Device type**
    See :term:`device type`

  **Device version**
    Optional field which can be edited by the lab administrators.

  **Device tags**
    Device specific labels to allow test jobs to request specific
    hardware capabilities. A :term:`device tag` can only be used in
    in TestJob if supported by a device of the relevant device type.

  **Worker Hostname**
    The dispatcher which has a configuration file for a device matching
    the hostname. Note that this is the result of checking the network
    communication between the dispatcher and the server, not the serial
    connection between the dispatcher and the board.

.. _device_owner_help:

Device ownership information
****************************

See also :ref:`device_capabilities`

  **Device owner**
    The user or group of users who can administer this device. Note that
    superusers of the LAVA instance are always able to administer any
    devices on that instance. The device owner has limited administrative
    control, see :ref:`owner_actions`. Devices can only be assigned to
    a device owner by the lab administrators.

  **Physical access**
    The user with :term:`physical access` to the device.

  **Description**
    Free text description of this individual device. This field can be
    used by the :term:`device owner` to give more information about the device. See
    :ref:`edit_device_description`.

  **Pipeline**
    A :term:`pipeline` device can accept jobs using the dispatcher :term:`refactoring`
    over `XMLRPC </api/help>`_. If **False**, the device only accepts JSON jobs. Some
    pipeline devices can support JSON and pipeline jobs and will be indicated as such
    here. Some pipeline devices are only supported by the changes
    within the refactoring, these are shown as **Exclusive**.

  **Exclusive**
    Devices which only support :term:`pipeline` jobs and which will reject JSON submissions
    are shown as exclusive.

.. index:: status

.. _device_status:

Device status
*************

  **Status**
    Describes the current device status which can be one of:
      * *Offline* - temporarily offline, possibly for short term maintenance
        or due to a :term:`health check` failure.
      * *Idle* - available for job submissions, subject to device ownership
        restrictions
      * *Running* - the device is running a test job. A link to the job
        will appear below this section of the page.
      * *Offlining* - the device owner or administrator has taken the
        device offline. The currently running job will complete normally
        before the device goes offline.
      * *Retired* - the device may have been relocated to another server,
        or failed due to a hardware fault or some other physical problem
        with the device. Contact the device owner or the user with
        physical access for more information.
      * *Reserved* - the device is part of a :term:`MultiNode` job but one
        or more other devices in the same job is not currently available.
        (Reserved is also used for single node jobs but the device quickly
        moves into Running.)
      * *Unreachable* - the network communication between this server and
        the dispatcher has been temporarily broken. The current state of the
        device or any currently running job may differ from that shown on the
        server.

  **Health Status**
    Status of the most recent :term:`health check` run. If the health
    status is ``Unknown``, a health check will be run as soon as the
    device is put online or has finished any current job but before
    starting any other submitted job.

.. _owner_actions:

Administrative controls
***********************

A device owner has permission to change the status of a particular
device, including taking the device out of the general purpose pool
of devices and making submissions available only to the device owner
or group of users of which the device owner is a member. Device owners
can also update the free text description of a device.

.. note:: Devices which are a :term:`hidden device type` cannot be
          returned to the pool until the type itself is visible to
          everyone.

.. index:: maintenance

.. _maintenance_mode:

Put into maintenance mode
=========================

A device in maintenance mode will be *Offline*, so any new job submissions
will wait in the submission queue until the device is online (*Idle*)
before starting. If the device was running a test job when the owner
or administrator put the device into maintenance mode, the device will
be in *Offlining* state until that job completes.

.. index:: looping

.. _looping_mode:

Put into looping mode
=====================

Devices already in maintenance mode can be put into looping mode where the device
continually runs the :term:`health check` defined for the :term:`device type`.
To cancel looping mode, either click the *Cancel Looping* button or
:ref:`maintenance_mode` - when the last health check completes, the device
will go into state *Offline*, the same as it was before looping mode
was enabled.

.. _put_online:

Put online
==========

Putting a device online involves running the :term:`health check` defined
for the :term:`device type`, if any, before moving to state *Idle* and
starting any jobs waiting in the submission queue. Device owners and
administrators are able to put devices which are *Offline* back online.
Only administrators can change the status of *Retired* devices.

.. index:: device description

.. _edit_device_description:

Edit device description
=======================

Device owners and administrators can edit a free text description of
this individual device. Suggested content includes more information about
the specific device, the reasons for restricting submissions, information
about the device owner and the purposes for which the device is used etc.
Text can include links to external sites for more information.

It can be particularly useful to expand on the :ref:`device_capabilities`
by adding details which cannot be easily identified at runtime, e.g.
big.LITTLE details or particular hardware features available on this
specific device.

.. index:: restricted

.. _restrict_device:

Restrict submissions
====================

An owned device can be restricted so that new job submissions will only
be accepted from the device owner. If the device owner is a group, any
user in that group will be able to submit new jobs.

Any currently running jobs will complete normally, unless the device
owner cancels the job.

Device owners are strongly recommended to edit the device description
in such a way as to explain why the restriction is necessary and how long
the restriction may last.

.. derestrict_device:

Return a device to the pool
===========================

Restricted devices can be returned to the common LAVA pool so that anyone
can submit jobs to the device. The device will be able to accept jobs
from any authorized user along with devices which have no device owner
assigned.

Changing the pipeline support of a device
=========================================

Devices which support :term:`pipeline` jobs can be enabled in the admin interface.
Devices which do not support JSON submissions can be set to **exclusive** by the admin
setting the *exclusive* flag in the :term:`device dictionary` for that device::

 {% set exclusive = 'True' %}

Whether a device supports the pipeline and / or is exclusive to the pipeline can
also be queried using `XMLRPC </api/help/#system.user_can_view_devices>`_
