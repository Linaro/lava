.. _health_checks:

Writing Health Checks for device types
**************************************

The purpose of the health check is to ensure that the support systems
of the device are suitable for running LAVA tests. To do this, the
health check is run periodically and if the health check fails for
any device, that device is automatically taken offline. Reports are
available which show these failures and track the general health of
the lab.

http://validation.linaro.org/scheduler/reports

For any one day where at least one health check failed, there is
also a table providing information on the failed checks:

http://validation.linaro.org/scheduler/reports/failures?start=-1&end=0&health_check=1

Health checks are defined in the admin interface for each device type
and run as the lava-health user.

The required entry is a JSON test file with the following changes::

* A job name describing the test as a health check
* The health_check boolean set to ```true```
* An optional list of email addresses to be notified if the health check fails.

 {
    "job_name": "lab-health-beaglebone-black",
    "health_check": true,
    "notify_on_incomplete": [
        "lava-notification@lists.linaro.org"
    ]
 }

Each health check also needs to submit results to a dedicated result
bundle stream for health checks::

 {
    "command": "submit_results",
    "parameters": {
        "server": "http://localhost/RPC2/",
        "stream": "/anonymous/lab-health/"
    }
 }

Tasks within health checks
==========================

The health check needs to at least check that the device will boot and
deploy a test image. Multiple deploy tasks can be set, if required, although
this will mean that each health check takes longer.

Wherever a particular device type has common issues, a specific test for
that behaviour should be added to the health check for that device type.

Health Checks are not generally suitable for functional tests of a LAVA
instance as the consequence of a health check failing is that devices of
the specified type will be automatically taken offline.
