.. _dispatcher_actions:

Dispatcher Action Reference
###########################

Job submissions for the pipeline dispatcher use YAML and test writers can
create a pipeline of actions based on three basic types. Parameters in the YAML
and in the device configuration are used to select the relevant Strategy for
the job and this determines which actions are added to the pipeline.

In addition, the job has some general parameters, including a job name
and :ref:`dispatcher_timeouts`.

Deploy Actions
**************

.. toctree::
   :maxdepth: 6

   actions-deploy.rst

Boot Actions
************

.. toctree::
   :maxdepth: 6

   actions-boot.rst

Test Actions
************

.. toctree::
   :maxdepth: 6

   actions-test.rst

Other test job elements
***********************

.. toctree::
   :maxdepth: 6

   actions-repeats.rst
   actions-protocols.rst
   actions-timeout.rst
   user-notifications.rst

reboot_to_fastboot
==================

This is specific to test jobs that operate on:

* `android` operating system
* :term:`DUT` requested by the job is fastboot based
* :term:`DUT` requested by the job does not use a :term:`PDU` for power control

It is used to specify whether the :term:`DUT` should reboot to fastboot mode at
the end of the test job. The default value is `true` i.e., the :term:`DUT` will
be rebooted to fastboot mode. This support is useful in the following use
cases:

* The :term:`DUT` does not charge in fastboot mode, in which case the user
  wants the :term:`DUT` to stay booted.
* A dedicated :term:`DUT` to a specific team, which does not want to deploy
  new images frequently to the :term:`DUT`, instead want to run some tests
  directly assuming the :term:`DUT` is booted.

Some disadvantages using this support are as follows:

* Some test images that gets deployed to the :term:`DUT` may have issues in
  retaining battery charge due to poor configuration. In such cases the
  :term:`DUT` runs out of charge and becomes unsuable for the next job, which
  should be handled by manual intervention, thus hindering automation.
* `Android` test images which are not built with USB debugging enabled,
  cannot be communicated with ``adb``, thus hindering automation. Since,
  ``adb`` is used to reboot the :term:`DUT` to bootloader mode, when the
  :term:`DUT` is booted, in the absence of a :term:`PDU` for power control.
* When a :term:`DUT` is shared between teams there is a possibility that a
  test image is flashed on the previous test job, which may not be the
  suitable test image for the next job by a different team's member, which
  assumes the device is booted and tries to run tests.
* It is the responsibility of the test writer who assumes the :term:`DUT` is
  booted already, to check if the previous test job left the :term:`DUT` in a
  state that is suitable for running the current test - LAVA does not take
  care of cleaning up the test environment in this case.

In order to keep the :term:`DUT` booted with `android` operating system at the
end of the test job run use the following in test job definition:

.. code-block:: yaml

  reboot_to_fastboot: false

.. note:: :term:`DUT` which is controlled by a :term:`PDU` will be powered off
          at the end of the test job run.

.. FIXME need to add notifications and metadata

Further Examples
****************

The number and range of test jobs is constantly increasing. The LAVA software
team develop functional tests in a dedicated git repository:
https://git.linaro.org/lava-team/refactoring.git Tests can then migrate into
standard tests and examples in the documentation. Even so, not all dispatcher
actions have a matching example.

.. seealso:: :ref:`using_gold_standard_files`
