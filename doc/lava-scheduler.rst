.. _scheduler_help:

LAVA Scheduler summary help
###########################

Device Type Overview
********************

Overall status
==============

  Online devices
    The number of devices online and the number of devices defined (includes
    Offline devices but not Retired devices). This is a link which
    takes to the page which shows a table with offline devices at the
    top along with the device type, status and restrictions (if any).

  Passing health checks
    Each :term:`device type` can have a single :term:`health check` job
    defined which is run automatically. The number of health checks run
    can be higher than the number of devices if devices had to re-run a
    health check after an intervention. It is a link which takes to a
    page that lists the health status of the devices (excluding
    Retired devices) with a link to the last run health job - "Last
    Report Job".

Reports
=======

  All devices
    List of all the devices available (includes Offline devices and
    Retired devices). This is a link which takes to the page which
    shows a table with all devices sorted alphabetically based on the
    hostname along with the device type, the worker host to which this
    device belongs to, status and restrictions (if any) and the device
    health status.

  All Active devices
    Same as "All devices" explained above, but does not include
    devices that are Retired.

  All Device Health
    List of all devices (without Retired devices) with their health
    status. Shows a link to the last health job that was run on this
    device and the health job completion time.

Device types
============

  The number of idle, offline, busy or restricted devices of the
  specified type. Click on the :term:`device type` to see details of
  who has access to a :term:`restricted device`. If a device is
  counted as restricted, it can be idle, offline or busy and is
  included in the respective totals. Queue column refers to the number
  of jobs that are waiting to grab the corresponding device type.

Active Jobs
***********

  Jobs that are actively considered by the scheduler for
  scheduling. The jobs with status such as "Submitted, Running" are
  listed in this table.

Workers
*******

  The worker hosts that are connected to this LAVA installation, are
  listed with details such as:
      - IP Address
      - Status: whether the worker host is reachable
      - Is Master?: is this the master node
      - Host Uptime: how long this worker node is up from last
        reboot/boot
      - Architecture: system architecture of the worker host
      - Last Master Scheduler Tick: when was the scheduler daemon last
        active in the master node
