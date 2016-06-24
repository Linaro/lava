.. _v2_hidden_device_type:

Hidden device type
##################

The :ref:`device_owners` can be extended to make certain device types
invisible to certain users for licensing reasons. Only lab administrators
can set a particular device type to **owners only**. All devices of this
type will then be hidden and only users who own at least one device of
this type or are a member of a group which owns at least one device of
this type will be able to see the device type.

Other users will not be able to access the job output, device status
transition pages or bundle streams of devices of a hidden type. Devices
of a hidden type will be shown as ``Unavailable`` in tables of test
jobs and omitted from tables of devices and device types if the user
viewing the table does not own any devices of the hidden type.

Anonymous users will be assumed to not have permission to view any
hidden device types.

Changes needed when managing a hidden device type
*************************************************

Private test job visibility
===========================

Public visibility **cannot** be used with any device of a hidden type.
Group visibility **must** be accessible to the user submitting the job
(who must also be an owner or a member of an owner group for a device
of this type).

Health Checks
=============

A :term:`health check` is run by the ``lava-health`` user, so to use
health checks with a hidden device type, this user **must** be added
as a member of a group which owns at least one device of the hidden type.

Note that the device type is already hidden, so adding a health check is
still recommended. Any detailed information visible via the device type
detail page regarding :ref:`device_type_information` will only be visible to
users who already have submit permission on a device of this type.
