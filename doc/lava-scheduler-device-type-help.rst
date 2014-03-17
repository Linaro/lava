.. _device_type_help:

Device type information in LAVA Scheduler
#########################################

Device type status
******************

* Number of jobs running and the number of jobs queued
* Details of the :term:`device type`.

.. index:: device type information

.. _device_type_information:

Device capabilities and information
***********************************

Device capabilities are shown if:

#. A :term:`health check` for this device type is defined
#. The health check uses ``lava_test_shell``- see :ref:`health_check_tests`.

Information displayed includes data retrieved from ``/proc/cpuinfo`` - all
fields are case sensitive and omitted if not present:

#. **Processor** : ``Processor`` or ``vendor_id``
#. **Model** : ``model name``. For ARM Cortex A series processors, the CPU part
   is expanded and appended to the model name.
#. **Flags** : ``flags`` or ``Features``
#. **Emulated** : Set to True if the Model is ``QEMU``
#. **Cores** : count of the number of ``processor`` fields.

Health Job Summary
******************

Summary of :term:`health check` results, number of tests completed
or failed for all devices of this type in the last 24hours, week and
month.

Devices Overview
****************

Summary of the devices of this type:

* hostname of each device with an indication of whether the device is
  available. (Tests the connection between the server and the dispatcher.)
* name of the dispatcher to which this device is connected.
* :ref:`device_status`
* Restrictions - summary of any restrictions applied to this device
  and whether the device is owned by a particular user or group.
* Device health - most recent :term:`health check` result.

Jobs for devices of this type
*****************************

A table of all jobs submitted to all devices of the specified
:term:`device type`, ordered by the most recent submission time.

Note that this differs from the Active Jobs table on the main
scheduler which is ordered by the most recent completion time by
default.
