.. index:: capabilities

.. _device_capabilities:

Device Capabilities Support
###########################

Device Capabilities include ways for individual users and groups to
get more information on LAVA devices, control who can submit jobs
to particular devices and manage device transitions without needing
full administrator access.

The user or group with physical access to the device is also stored,
this is useful when someone needs to interact with the device directly
rather than through network, serial or LAVA connections.

The Device Owner is a dedicated field in the admin interface which
displays the email address of the owner or the name of the group.

New device owners can only be created by the lab administrators. Equally,
assigning or transferring ownership of any device can only be done by the
lab administrators.

LAVA also identifies certain :ref:`device_type_information` from the
:term:`health check` jobs run on the device.

.. index:: owner

.. _device_owners:

Device owner abilities
**********************

* add free text comments to a :term:`device status transition`
* initiate a :term:`device status transition` on an owned device
* cancel any "current" job running on the device.
* restrict submissions to the device to just the owner for a period of
  time - (when unrestricted, devices remain in the general usage pool.)
  MultiNode submissions by the owner can use restricted and pool devices.
  Restricted devices are not included in the count of devices available
  during job submission by other users.
* Edit device-specific timeouts for stages within dispatcher processes.
  This allows the hardcoded values to be reset to general usage defaults
  and devices which need exceptions to specify such exceptions individually.
* :ref:`edit_device_description` - could include particular
  hardware support on this device or particular hardware constraints.
  Could also include details of why the device is currently restricted,
  beyond the short message sometimes added to the transition status change.
* Change the :term:`priority` for any submitted job which reserves an "owned"
  device. Priority can **only** be changed once an owned device has been
  reserved for the job and before the job starts running or an error
  will be returned.
* annotate individual job failures
* skip health check this time only when putting a device online. This
  omission is recorded in the state transition log for the device.
* force a health check without needing to take the device offline and
  then back online.
