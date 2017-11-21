.. index:: health check - writing, health check - migrating

.. _health_checks:

Writing Health Checks for devices
*********************************

A health check is a special type of test job, designed to validate that the a
test device and the infrastructure around it are suitable for running LAVA
tests. Health checks jobs are run periodically to check for equipment and/or
infrastructure failures that may have happened. If a health check fails for any
device, that device will be automatically taken offline. Reports are available
which show these failures and track the general health of the lab.

https://validation.linaro.org/scheduler/reports

For any one day where at least one health check failed, there is also a table
providing information on the failed checks:

https://validation.linaro.org/scheduler/reports/failures?start=-1&end=0&health_check=1

Health checks are defined in
``/etc/lava-server/dispatcher-config/health-checks`` according to the template
used by the device. Health checks are run as the lava-health user.

.. note:: To generate the filename of the health check of a device, the
   scheduler takes the name of the template extended in the device dictionary
   (for instance ``qemu.jinja2`` for qemu devices) and replace the extension
   with ``.yaml``. The health check will be called
   ``/etc/lava-server/dispatcher-config/health-checks/qemu.yaml``.  The health
   check job database field in the device-type is unused.

.. note:: Admins can temporarily disable health checks for all devices of a
   given type in the device-type admin page.

.. _yaml_health_checks:

LAVA YAML health checks
=======================

.. note:: Before enabling a health check, ensure that all devices of the
   specified type have been enabled as pipeline devices or the health check
   will force any remaining devices **offline**.

It is recommended that the YAML health check follows these guidelines:

* It has a job name describing the test as a health check
* It has a minimal set of test definitions
* It uses :ref:`gold standard files <providing_gold_standard_files>`

The rest of the job needs no changes.

.. _health_check_device_type:

Device Types and templates
--------------------------

Some jinja2 device-type templates use multiple inheritance, e.g. ``juno``. This
is to allow devices to use multiple types of firmware in test jobs. Admins need
to be aware that the ``device_type`` specified in the health check YAML must
match a DeviceType name which exists in the database and which has devices
available for health-check submissions. This can cause issues where admins want
to share health checks between multiple instances.

For example, if the DeviceType database object has the name ``juno-r2``, the
device dictionary can use:

.. code-block:: jinja

 {% extends 'juno.jinja2' %}

However, the health check YAML needs to use ``device_type: juno-r2`` or the
health check will not run.

Check ``/var/log/lava-server/django.log`` if you get a 404 when trying to force
a health check.

This situation can be avoided by converting a working test job into the health
check on the same instance.

Tasks within health checks
==========================

The health check needs to at least check that the device will boot and deploy a
test image. Multiple deploy tasks can be set, if required, although this will
mean that each health check takes longer.

Wherever a particular device type has common issues, a specific test for that
behaviour should be added to the health check for that device type.

.. _health_check_tests:

Using lava_test_shell inside health checks
==========================================

It is a mistake to think that lava_test_shell should not be run in health
checks. The consequence of a health check failing is that devices of the
specified type will be automatically taken offline but this applies to a job
failure, not a fail result from a single lava-test-case.

It is advisable to use a minimal set of sanity check test cases in all health
checks, without making the health check unnecessarily long:

.. code-block:: yaml

    - test:
       timeout:
         minutes: 5
       definitions:
         - repository: git://git.linaro.org/lava-team/lava-functional-tests.git
           from: git
           path: lava-test-shell/smoke-tests-basic.yaml
           name: smoke-tests

These tests run simple Debian/Ubuntu test commands to do with networking and
basic functionality - it is common for ``linux-linaro-ubuntu-lsusb`` and/or
``linux-linaro-ubuntu-lsb_release`` to fail as individual test cases but these
failed test cases will **not** cause the health check to fail or cause devices
to go offline.

Using ``lava_test_shell`` in all health checks has several benefits:

#. health checks should use the same mechanisms as regular tests, including
   ``lava_test_shell``

#. devices are tested to ensure that test repositories can be downloaded to the
   device.

#. device capabilities can be retrieved from the health check result bundles
   and displayed on the device type status page.

#. tests inside ``lava_test_shell`` can provide a lot more information than
   simply booting an image and each device type can have custom tests to pick
   up common hardware issues

See also :ref:`writing_tests`.

Skipping health checks
======================

When a device is taken online in the web UI, there is an option to skip the
manual health check. Health checks will still run in the following
circumstances when "Skip Health check" has been selected:

* When the health status of the device is in Unknown, Fail or Looping
* When the device has been offline for long enough that a health
   check is already overdue.
