.. index:: state machine, scheduling, hacking

.. _state_machine:

State machine
#############

The state machine describes and controls the state and health of Workers,
Devices and Test Jobs.

Workers
*******

For each worker, two variables describe the current status:

* ``state``:

  * *Online*
  * *Offline*

* ``health``:

  * *Active*
  * *Maintenance*
  * *Retired*

``state`` is an internal variable, set by ``lava-master`` when receiving (or
not) pings from each worker.

.. caution:: When a worker is in *Offline*, none of the attached devices
   will be used to schedule new jobs.

``health`` can be used by admins to prevent jobs to run on attached devices.
For instance, when set to *Maintenance*, no jobs will be scheduled on attached
devices.

Devices
*******

For each device, two variables describe the current status:

* ``state``:

  * *Idle*: not in use by any test job

  * *Reserved*: has been reserved for a test job but the test job is not
    running yet

  * *Running*: currently running a test job

* ``health``:

  * *Good*
  * *Unknown*
  * *Looping*: should run health-checks in a loop
  * *Bad*
  * *Maintenance*
  * *Retired*

``state`` is an internal variable, set by ``lava-server-gunicorn`` and ``lava-scheduler``
when scheduling, starting, canceling and ending test jobs.

``health`` can be used by admins to indicate if a device should be used by the
scheduler or not. Moreover, when ending an health-check, the device health will
be set according to the test job health.

TestJobs
********

For each test job, two variables are describing the current status:

* ``state``:

  * *Submitted*: waiting in the queue

  * *Scheduling: part of a multinode test job where some sub-jobs are
    still in *Submitted*

  * *Scheduled*: has been scheduled. For multinode, it means that all
    sub-jobs are also scheduled

  * *Running*: currently running on a device

  * *Canceling*: has been canceled but not ended yet

  * *Finished*

.. note:: Only multinode test jobs use *Scheduling*. When all
   sub-jobs are in *Scheduling*, ``lava-master`` will transition all test
   jobs to *Scheduled*.

* ``health``:

  * *Unknown*: default value that will be overridden when the job is finished.

  * *Complete*

  * *Incomplete*

  * *Canceled*: the test job was canceled.

.. _scheduler:

Scheduler
#########

The scheduler is called by ``lava-master`` approximately every 20 seconds.
The scheduler starts by scheduling health-checks. The remaining devices are
then considered for test jobs.

Health-checks
*************

To ensure that health-checks are always scheduled when needed, they will be
considered first by the scheduler before regular test jobs.

The scheduler will only consider devices where:

* `state` is *Idle*
* `health` is *Good*, *Unknown* or *Looping*
* worker's `state` is *Online*

.. note:: A device whose ``health`` is *Bad*, *Maintenance* or *Retired* is
   never considered by the scheduler when it is looking for devices to run test
   jobs

Test jobs
*********

The scheduler will only consider devices where:

* ``state`` is *Idle*
* ``health`` is *Good* or *Unknown*
* worker's ``state`` is *Online*
