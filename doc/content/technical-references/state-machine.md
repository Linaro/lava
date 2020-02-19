# State machine

The state machine describes and controls the state and health of Workers,
Devices and Test Jobs.

## Workers

For each worker, two variables describe the current status: **state** and **health**.

### State

The **state** is an internal variable, set by [lava-master](../services/lava-master/) when receiving (or not) pings from each worker.

* *Online*: the worker is sending PING to the master
* *Offline*: the worker hasn't sent any messages for a while

### Health

The **health** can be used by admins to control the **health** of all attached devices.

For instance, when set to *Maintenance*, all attached devices will be automatically put into maintenance mode so that no jobs will be scheduled on those devices.

The worker health can be:

* *Active*
* *Maintenance*
* *Retired*


!!! warning
    When a worker is *Offline*, none of the attached devices will be used to schedule new jobs.

## Devices


For each device, two variables describe the current status: **state** and **health**.

### State

The **state** is an internal variable, set by [lava-master](../services/lava-master/) and [lava-logs](../service/lava-logs/) when scheduling, starting, canceling and ending test jobs.

* *Idle*: not in use by any test job
* *Reserved*: has been reserved for a test job but the test job is not running yet
* *Running*: currently running a test job

### Health

The **health** can be used by admins to indicate if a device should be used by the scheduler or not.

Moreover, when ending an health-check, the device health will be set according to the test job health.

* *Good*: the device passed the health-check
* *Unknown*
* *Looping*: should run health-checks in a loop
* *Bad*: the device failed the health-check
* *Maintenance*
* *Retired*


## TestJobs

For each test job, two variables are describing the current status: **state** and **health**.

### State

* *Submitted*: waiting in the queue
* *Scheduling*: part of a multinode test job where some sub-jobs are still in *Submitted*
* *Scheduled*: has been scheduled. For multinode, it means that all sub-jobs are also scheduled
* *Running*: currently running on a device
* *Canceling*: has been canceled but not ended yet
* *Finished*

!!! note Multinode scheduling
    Only multinode test jobs use *Scheduling*. When all
    sub-jobs are in *Scheduling*, [lava-master](../services/lava-master/) will transition all test
    jobs to *Scheduled*.

### Health

* *Unknown*: default value that will be overriden when the job is finished.
* *Complete*: the job was able to finish
* *Incomplete*: the job was not able to dinish
* *Canceled*: the test job was canceled.


# Scheduler

The scheduler is called by [lava-master](../services/lava-master/) approximately every 20 seconds.
The scheduler starts by scheduling health-checks. The remaining devices are
then considered for test jobs.

## Health-checks

To ensure that health-checks are always scheduled when needed, they will be
considered first by the scheduler before regular test jobs.

The scheduler will only consider devices where:

* `device state` is *Idle*
* `device health` is *Good*, *Unknown* or *Looping*
* `worker state` is *Online*

## Test jobs

The scheduler will only consider devices where:

* ``device state`` is *Idle*
* ``device health`` is *Good* or *Unknown*
* ``worker state`` is *Online*
