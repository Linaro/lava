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

  * STATE_ONLINE
  * STATE_OFFLINE

* ``health``:

  * HEALTH_ACTIVE
  * HEALTH_MAINTENANCE
  * HEALTH_RETIRED

``state`` is an internal variable, set by ``lava-master`` when receiving (or
not) pings from each worker.

.. caution:: When a worker is in STATE_OFFLINE, none of the attached devices
   will be used to schedule new jobs.

``health`` can be used by admins to control the ``health`` of all attached
devices. For instance, when set to *HEALTH_MAINTENANCE*, all attached devices
will be automatically put into maintenance mode so that no jobs will be
scheduled on those devices.

Devices
*******

For each device, two variables describe the current status:

* ``state``:

  * STATE_IDLE: not in use by any test job

  * STATE_RESERVED: has been reserved for a test job but the test job is not
    running yet

  * STATE_RUNNING: currently running a test job

* ``health``:

  * HEALTH_GOOD
  * HEALTH_UNKNOWN
  * HEALTH_LOOPING: should run health-checks in a loop
  * HEALTH_BAD
  * HEALTH_MAINTENANCE
  * HEALTH_RETIRED

``state`` is an internal variable, set by ``lava-master`` and ``lava-logs``
when scheduling, starting, canceling and ending test jobs.

``health`` can be used by admins to indicate if a device should be used by the
scheduler or not. Moreover, when ending an health-check, the device health will
be set according to the test job health.

TestJobs
********

For each test job, two variables are describing the current status:

* ``state``:

  * STATE_SUBMITTED: waiting in the queue

  * STATE_SCHEDULING: part of a multinode test job where some sub-jobs are
    still in STATE_SUBMITTED

  * STATE_SCHEDULED: has been scheduled. For multinode, it means that all
    sub-jobs are also scheduled

  * STATE_RUNNING: currently running on a device

  * STATE_CANCELING: has been canceled but not ended yet

  * STATE_FINISHED

.. note:: Only multinode test jobs use STATE_SCHEDULING. When all
   sub-jobs are in STATE_SCHEDULING, ``lava-master`` will transition all test
   jobs to SCHEDULED.

* ``health``:

  * HEALTH_UNKNOWN: default value that will be overriden when the job is finished.

  * HEALTH_COMPLETE

  * HEALTH_INCOMPLETE

  * HEALTH_CANCELED: the test job was canceled.

.. _scheduler:

Scheduler
#########

The scheduler is called by ``lava-master`` approximatively every 20 seconds.
The scheduler starts by scheduling health-checks. The remaining devices are
then considered for test jobs.

Health-checks
*************

To ensure that health-checks are always scheduled when needed, they will be
considered first by the scheduler before regular test jobs.

The scheduler will only consider devices where:

* `state` is *STATE_IDLE*
* `health` is *HEALTH_GOOD*, *HEALTH_UNKNOWN* or *HEALTH_LOOPING*
* worker's `state` is *STATE_ONLINE*

.. note:: A device whose ``health`` is *HEALTH_BAD*, *HEALTH_MAINTENANCE* or
   *HEALTH_RETIRED* is never considered by the scheduler when it is looking for
   devices to run test jobs

Test jobs
*********

The scheduler will only consider devices where:

* ``state`` is *STATE_IDLE*
* ``health`` is *HEALTH_GOOD* or *HEALTH_UNKNOWN*
* worker's ``state`` is *STATE_ONLINE*
