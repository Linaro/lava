.. _v2_hidden_device_type:

Hidden device types
###################

The :ref:`device_owners` can be extended to make certain device types invisible
to certain users for licensing reasons. Only lab administrators can set a
particular device type to **owners only**. All devices of this type will then
be hidden and only users who own at least one device of this type or are a
member of a group which owns at least one device of this type will be able to
see the device type.

Other users will not be able to access the job output, device status transition
pages or bundle streams of devices of a hidden type. Devices of a hidden type
will be shown as ``Unavailable`` in tables of test jobs and omitted from tables
of devices and device types if the user viewing the table does not own any
devices of the hidden type.

Anonymous users will be assumed to not have permission to view any hidden
device types.

.. index:: health checks - configuration error

Changes needed when managing a hidden device type
*************************************************

Private test job visibility
===========================

Public :term:`visibility` **cannot** be used with any device of a
hidden type. Group visibility **must** be accessible to the user
submitting the job (who must also be an owner or a member of an owner
group for a device of this type).

Health Checks
=============

A :term:`health check` is run by the ``lava-health`` user, so to use health
checks with a hidden device type, this user **must** be added as a member of a
group which owns at least one device of the hidden type.

Note that the device type is already hidden, so adding a health check is still
recommended. Any detailed information visible via the device type detail page
regarding :ref:`device_type_information` will only be visible to users who
already have submit permission on a device of this type.

If a public health check exists, the device transitions will show::

  Unknown → Bad (Invalid health check)

Also, the lava-master log file will identify which device was involved
by showing an entry like::

 2018-07-09 08:48:45,783   DEBUG  -> staging-db410c-04 (Idle, Unknown)
 2018-07-09 08:48:45,783   DEBUG   |--> scheduling health check
 2018-07-09 08:48:45,799   ERROR   |--> Unable to schedule health check
 2018-07-09 08:48:45,799   ERROR Publicly visible health check for restricted device
 Traceback (most recent call last):
   File "/usr/lib/python3/dist-packages/lava_scheduler_app/scheduler.py", line 130, in schedule_health_checks_for_device_type
    jobs.append(schedule_health_check(device, health_check))
   File "/usr/lib/python3/dist-packages/lava_scheduler_app/scheduler.py", line 147, in schedule_health_check
    orig=definition, health_check=True)
   File "/usr/lib/python3/dist-packages/lava_scheduler_app/models.py", line 1114, in _create_pipeline_job
   lava_common.exceptions.ConfigurationError: Publicly visible health check requested for a hidden device-type.

To fix this, ensure that the health check job YAML has restricted
:term:`visibility`:

.. code-block:: yaml

 visibility: personal

Alternatively, use:

.. code-block:: yaml

 visibility: group
   - group_name
