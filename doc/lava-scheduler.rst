.. _scheduler_help:

LAVA Scheduler summary help
###########################

Device Type Overview
********************

  devices online
    The number of devices online and the number of devices defined (includes
    Offline devices but not Retired devices).

  health checks passed
    Each :term:`device type` can have a single :term:`health check` job
    defined which is run automatically. The number of health checks run
    can be higher than the number of devices if devices had to re-run a
    health check after an intervention.

  device summary table
    The number of idle, offline, busy or restricted devices of the
    specified type. Click on the :term:`device type` to see
    details of who has access to a :term:`restricted device`. If a
    device is counted as restricted, it can be idle, offline or busy
    and is included in the respective totals.
