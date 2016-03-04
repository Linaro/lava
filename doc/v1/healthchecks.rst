.. index:: health check

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

.. _json_health_checks:

Deprecated JSON health checks
=============================

.. note:: A health check using the deprecated JSON dispatcher is **not** suitable if
  **any** of the devices of this type are :term:`exclusive` to the pipeline
  dispatcher. A `pipeline health check` should be used. Avoid
  having exclusive devices unless all devices of that type have pipeline support -
  if this is unavoidable, the health check may need to be omitted or some devices split
  into a temporary device type.

The required entry for a health check using the deprecated dispatcher
is a JSON test file with the following change:

* The health_check boolean set to ```true```

In addition, it is recommended to use:

* A job name describing the test as a health check.
* A list of email addresses to be notified if the health check fails.
* A minimal ``lava_test_shell`` definition.
* A dedicated result bundle stream.
* A logging level of DEBUG - the one place where you do want to know
  why a job failed is when that job has taken a device offline.

::

 {
    "timeout": 900,
    "job_name": "lab-health-beaglebone-black",
    "logging_level": "DEBUG",
    "health_check": true,
    "actions": [
        {
            "command": "deploy_linaro_image",
            "parameters": {
                "image": "http://linaro-gateway/beaglebone/beaglebone_20130625-379.img.gz"
            },
            "metadata": {
                "ubuntu.distribution": "quantal",
                "ubuntu.build": "299",
                "rootfs.type": "nano",
                "ubuntu.name": "beaglebone-black"
            }
        },
        {
            "command": "lava_test_shell",
            "parameters": {
                "testdef_repos": [
                    {
                        "git-repo": "git://git.linaro.org/qa/test-definitions.git",
                        "testdef": "ubuntu/smoke-tests-basic.yaml"
                    }
                ],
                "timeout": 900
            }
        },
        {
            "command": "submit_results",
            "parameters": {
                "server": "http://localhost/RPC2/",
                "stream": "/anonymous/lab-health/"
            }
        }
    ]
 }

Tasks within health checks
==========================

The health check needs to at least check that the device will boot and
deploy a test image. Multiple deploy tasks can be set, if required, although
this will mean that each health check takes longer.

Wherever a particular device type has common issues, a specific test for
that behaviour should be added to the health check for that device type.

.. _health_check_tests:

Using lava_test_shell inside health checks
==========================================

It is a mistake to think that lava_test_shell should not be run in
health checks. The consequence of a health check failing is that
devices of the specified type will be automatically taken offline but
this applies to a job failure, not a fail result from a single
lava-test-case.

It is advisable to use a minimal set of sanity check test cases in all
health checks, without making the health check unnecessarily long:

.. code-block:: yaml

    - test:
       timeout:
         minutes: 5
       definitions:
         - repository: git://git.linaro.org/qa/test-definitions.git
           from: git
           path: ubuntu/smoke-tests-basic.yaml
           name: smoke-tests

Or for :ref:`json_health_checks` ::

    {
        "command": "lava_test_shell",
        "parameters": {
            "testdef_repos": [
                {
                    "git-repo": "git://git.linaro.org/qa/test-definitions.git",
                    "testdef": "ubuntu/smoke-tests-basic.yaml"
                }
            ],
            "timeout": 900
        }
    }

These tests run simple Ubuntu test commands to do with networking and
basic functionality - it is common for ``linux-linaro-ubuntu-lsusb``
and/or ``linux-linaro-ubuntu-lsb_release`` to fail as individual test
cases but these failed test cases will **not** cause the health check
to fail or cause devices to go offline.

Using ``lava_test_shell`` in all health checks has several benefits:

#. health checks should use the same mechanisms as regular tests,
   including ``lava_test_shell``
#. devices are tested to ensure that test repositories can be
   downloaded to the device.
#. device capabilities can be retrieved from the health check
   result bundles and displayed on the device type status page.
#. tests inside ``lava_test_shell`` can provide a lot more information
   than simply booting an image and each device type can have custom
   tests to pick up common hardware issues

See also :ref:`writing_tests`.
