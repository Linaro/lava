.. _device_type_help:

Device type information in LAVA Scheduler
#########################################

There are tabs which provide more information on each :term:`device type`. Test
writers can see three tabs (**Status**, **Information** and **Support**),
superusers and administrators can see a fourth (**Admin**) which is a shortcut
into the :ref:`django_admin_interface` for this device type.

Status tab
**********

* Number of jobs running and the number of jobs queued

* Links to the graphical reports for test jobs using this device type.

* Frequency of health checks for all devices of this device type

* Number of Active, Idle, Offline and Retired devices of this device type.

.. _device_type_metadata:

Information tab
***************

Static information about the device type, usually populated by the admins when
the device type is integrated into LAVA.

#. **Architecture version** (e.g. ARMv7 or ARMv8)

#. **Processor Family** (e.g. OMAP4, Exynos)

#. **Alias** (e.g. omap4-panda, omap4-panda-es)

#. **CPU model** (often empty but may contain a list of model strings which are
   all equivalent within this device type).

#. **Bit width** - (e.g. 32 or 64)

#. **Cores** - a string constructed from the total number of cores specified
   and the list of cores selected for this device type. This **does not** infer
   that there are equal numbers of the specified cores.

#. **Description** - free text field which admins can use to clarify any issues
   or notable features / bugs in the hardware. e.g. if hardware floating point
   is not enabled when it would otherwise be expected or to clarify the actual
   arrangement of cores.

The information is available as metadata which can later be used in
:term:`queries <query>` for :term:`pipeline` results as well as providing basic
information on the type of device.

.. index:: device type information

.. _device_type_information:

Support tab
***********

The device type template provides the core configuration for all devices of
this device type and provides methods for certain values to be overridden. The
template can be downloaded, rendered as YAML, for comparison or debugging.

.. seealso:: :ref:`override_support`

The available methods and timeouts for this device type are also shown. Not all
devices of this type will support all methods. For example, some methods may
require additional hardware to be fitted like a USB stick or SATA drive.

.. seealso:: :ref:`boot_action`, :ref:`deploy_action`, :ref:`timeouts`

Health Job Summary
******************

Summary of :term:`health check` results, number of tests completed or failed
for all devices of this type in the last 24hours, week and month.

Devices Overview
****************

Summary of the devices of this type:

* hostname of each device with an indication of whether the device is
  available. (Tests the connection between the server and the dispatcher.)

* name of the dispatcher to which this device is connected.

* :ref:`device_status`

* Restrictions - summary of any restrictions applied to this device and whether
  the device is owned by a particular user or group.

* Device health - most recent :term:`health check` result.

Jobs for devices of this type
*****************************

A table of all jobs submitted to all devices of the specified :term:`device
type`, ordered by the most recent submission time.

Note that this differs from the Active Jobs table on the main scheduler which
is ordered by the most recent completion time by default.
