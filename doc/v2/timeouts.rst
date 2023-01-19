.. index:: timeouts

.. _timeouts:

Timeouts
########

V2 provides detailed control over timeouts within testjobs. The job has an
over-arching timeout, each action has a default runtime timeout, each
connection has a default timeout to get a reply and individual actions within
the pipeline can have the action or connection timeout modified in the test
definition or in the device configuration.

.. _need_for_timeouts:

Automation and Timeouts
***********************

Why must timeouts exist?
========================

Automation needs to be able to cope with failures during operation and one of
the most common failure modes is that a command never returns because some part
of the setup for that command has not been done, failed during operation or is
not supported for some reason.

.. note:: It is not usually the operation which times out which is the reason
   for the failure. Typically, a timeout results from one or more **previous**
   operations failing. A test job which fails due to a timeout **must always be
   investigated** - simply extending the timeout is the wrong approach.
   Equally, long timeouts **are directly harmful to other users**, choose your
   timeouts carefully and regularly evaluate whether existing timeouts can be
   shortened.

When operating the same test interactively, a human will typically notice that
a step has failed and either not attempt the operation that would later time
out or recognize that the operation should have completed by some point in time
and intervene. It is not always possible to check the success or failure of
operations within a test in an automated fashion - command outputs change from
one distribution to another or from one version of a package to another.

The timeout is a necessary part of automation, it allows test jobs to fail
instead of holding on to the job and the device indefinitely.

.. index:: calculating timeouts

.. _calculating_timeouts:

How long should an operation wait?
==================================

The best guidance here is to assess how the operation works when you use the
device interactively. Compare over a few runs of the operation and then use a
timeout which is slightly longer than the longest successful operation by
rounding up to the nearest whole minute or hour.

Timeouts do not need to be precise, 2 minutes is better than 90 seconds, but
yet **must not be excessive**. If an operation has routinely taken 5 minutes to
succeed previously and has now suddenly taken 30 minutes, this **needs to be
investigated**. It could easily be a kernel bug, hardware fault, infrastructure
fault or test job error. Increase timeouts **gradually** and keep a sense of
perspective of just what is reasonable to expect an operation to require.

.. important:: Do **not** simply transfer timeouts from V1 jobs! V1 timeouts do
   not have the same structure and cannot be easily mapped to individual
   actions or operations within an action.

Operations involving third party services
=========================================

When downloading, uploading or transferring data using third party services it
can be hard to estimate a reasonable timeout. If test jobs start to fail during
such operations, investigate whether the connection to the third party service
can be improved, cached or fixed.

Duration of actions
===================

The duration of every action in a test job is tracked and recorded. This allows
test writers to look at other similar jobs and evaluate the actual duration of
any operation within that testjob. Equally, it allows lab admins to compare
your timeouts against the actual duration of the operation. If your jobs start
to fail and sit idle for long periods waiting for a timeout, you have the
information to hand to fix the timeouts yourself before you get a prompt from
the admins.

.. _test_shell_timeouts:

Test shell timeouts
===================

The timeout used by the test action is a single value covering all test
operations. Actual durations are still tracked and recorded, so
excessive timeouts still need to be addressed.

.. index:: defining timeouts

.. _defining_timeouts:

Defining timeouts
*****************

For the test writer, the timeout is expressed as a single integer value of:

* seconds,
* minutes,
* hours or
* days

There is no need to specify sub-divisions or to overflow. Instead of ``seconds:
90`` use ``minutes: 2`` and instead of trying to specify two and a half
minutes, just use ``minutes: 3``. Using ``hours: 2`` when only ``minutes: 2``
is required is likely to get you a warning from the admins but using ``minutes:
10`` instead of ``seconds: 600`` is **strongly** recommended.

Although timeouts support ``days``, you need to have a **very** good reason to
set such a timeout to avoid being accused of denying access to the device to
other users (including the special ``lava-health`` user which is used to submit
health checks).

.. _job_timeout:

Job timeouts
************

The entire test job has a single over-arching timeout. This means that no
matter how long any action or connection timeout is set within the test job, if
the test job duration increases above the **job timeout** then the *slave* will
terminate the job and set the status as **Incomplete**.

The first reason for this timeout is so that individual actions or connections
can have freedom to set timeouts but the testjob still fails if more than one
or two of the operations take significantly longer than anticipated.

The second reason for a job timeout is that it allows the UI to derive an
estimate of how long the job will take to inform other users who may be waiting
for their jobs to start on the busy devices.

.. include:: examples/test-jobs/standard-armmp-ramdisk-arndale.yaml
   :code: yaml
   :start-after: job_name: standard Debian ARMMP ramdisk test on arndale
   :end-before: priority

The ``timeouts`` block specifies the job timeout, as well as the
:ref:`default_action_timeouts` (5 minutes in this example) and
:ref:`default_connection_timeouts` (4 minutes in this example).

.. seealso:: :ref:`action_block_timeout_overrides`,
   :ref:`individual_action_timeout_overides` and
   :ref:`individual_connection_timeout_overrides`.

Summary of the example job timeouts
===================================

* The test job will not take longer than **15 minutes** or it will timeout.
  This will happen irrespective of which action is currently running or how
  much time that action has before it would timeout.

* No one action (deploy, boot or test) will take longer than **5 minutes** or
  that action will timeout. Each operation within the action (the action class)
  will pass on the remaining time to the next operation. Enable the debug logs
  at the top of the log page to see this as a decreasing ``timeout`` value with
  each ``start`` operation:

  .. code-block:: none

   start: 1.3.4 compress-overlay (timeout 00:04:06)
   end: 1.3.4 compress-overlay (duration 00:00:03)
   start: 1.3.5 persistent-nfs-overlay (timeout 00:04:03)

* No one connection will take longer than **2 minutes** or the action will
  timeout. Connection timeouts are between prompts, so this is the maximum
  amount of time that any operation within the action can take before the
  action determines that there is not going to be any more output and to fail
  as a timeout. **Actions typically include multiple connections**, each with
  the same timeout. Connection timeouts are not affected by previous
  connections, each time a command is sent, the action expects to find the
  prompt again within the same connection timeout.

* All timeouts in this top level section can be overridden later in the test
  job definition.

.. seealso:: :ref:`test_shell_timeouts`

.. _default_action_timeouts:

Default action timeouts
***********************

An action timeout covers the entire operation of all operations performed by
that action. Check the V2 logs for lines like::

 start: 1.1.1 http_download (timeout 00:05:00)

::

 end: 1.1.1 file_download (duration 00:00:25)

The action timeout ``00:05:00`` comes from this part of the job definition:

.. include:: examples/test-jobs/standard-armmp-ramdisk-arndale.yaml
   :code: yaml
   :start-after: job_name: standard Debian ARMMP ramdisk test on arndale
   :end-before: connection

The complete list of actions for any test job is available from the job
definition page, on the pipeline tab.

.. note:: Not all actions in any one pipeline will perform any operations.
   Action classes are idempotent and can skip operations depending on the
   parameters of the testjob. Hence some actions will show a duration of
   ``00:00:00``.

.. _default_connection_timeouts:

Default connection timeouts
***************************

A connection timeout covers each single operation of sending a command to a
device and getting a response back from that device. A new connection timeout
is used for each operation of sending a command to the device. For example,
when sending a list of commands to a bootloader, each complete line has the
same connection timeout which is reset back to zero for the subsequent line.

Connection timeouts can be much shorter than action timeouts, especially if the
action needs to send multiple lines of commands.

.. _device_configuration_timeouts:

Inheriting timeouts from the device configuration
*************************************************

In addition, individual device types can set an action override or connection
override for all pipelines using devices of that type. This is to allow for
certain devices which need to initialize certain hardware that takes longer
than most other devices with similar support.

Details of these timeouts can be seen on the device type page on the *Support*
tab and can be overridden using the overrides in the test job.

.. note:: The actual timeout for each action is computed by taking the device
   configuration and overriding the values with the timeouts from the job
   definition.
   The timeout will be the first defined value in:
   :ref:`action_block_timeout_overrides`,
   :ref:`individual_action_timeout_overides` and :ref:`default_action_timeouts`.

.. _individual_action_timeout_overides:

Individual action overrides
***************************

For fine-grained control over action timeouts, individual actions can be named
in the timeout block at the top of the test job submission and assigned a
specific timeout which can be longer or shorter than the default or the action
block override.

.. code-block:: yaml

 timeouts:
   actions:
     http-download:
       minutes: 2

.. _individual_connection_timeout_overrides:

Individual connection overrides
*******************************

For fine-grained control over connection timeouts, individual actions can be
named in the timeout block at the top of the test job submission and assigned a
specific connection timeout which can be longer or shorter than the default.

.. code-block:: yaml

 timeouts:
   connections:
     http-download:
       minutes: 2

.. _action_block_timeout_overrides:

Action block overrides
**********************

The test job submission action blocks, (``deploy``, ``boot`` and ``test``) can
also have timeouts. These will override the default action timeout for all
actions within that block. Action blocks are identified by the start of the
:term:`action level` and the timeout value is set within that action block:

.. include:: examples/test-jobs/standard-armmp-ramdisk-arndale.yaml
   :code: yaml
   :start-after:   build-script: http://images.validation.linaro.org/snapshots.linaro.org/components/lava/standard/debian/stretch/armhf/3/armmp-nfs.sh
   :end-before: to: tftp

The default timeout for each action within this block will be set to the specified
value.

The timeout for individual actions in a block can also be redefined in the
timeouts section within the block:

.. code-block:: yaml

  actions:
  - deploy:
      timeout:
        minutes: 5
      timeouts:
        http-download:
          minutes: 1

.. _individual_action_block_timeout_overrides:

.. index:: timeouts - skipping

Skipping a test shell timeout
*****************************

In some cases, a test shell action is known to hang or otherwise cause
a timeout.

If the device is capable of booting twice in a single test job
(*deploy*, *boot*, *test*, *boot*, *test*) then the first test action
timeout can set ``skip: true`` which stops the job finishing as
Incomplete if the timeout occurs. The job will then continue to the
second boot action, allowing the device to reset to a known state and
start the second test action.

If the first test action does not timeout, the job completes that
test action and executes the second boot action as normal.

Test writers should consider using utilities like the ``timeout``
command inside their own test shell scripts to retain control within
the currently executing test shell scripts. Skipping a test shell
timeout is intended for tests which may cause a kernel panic or other
deadlock of the currently executing test shell.

.. important:: There are limitations to what can be achieved here:

   * Lava Test Shell is **not re-entrant** - it is not
     possible to restart or return to the previously executing test
     shell. The second test action is a separate test shell and the
     boot action **must** be defined by the test writer at submission.

   * Timeouts in :term:`MultiNode` test jobs **cannot be skipped**.

   * The timeout itself must still occur - the test job must wait,
     after the error has occurred, until the timeout. Ensure that the
     timeout value is still long enough to cover the actual execution
     time if the test shell action did not hang or fail.

   * This support will **not** protect the DUT in the case of a
     destructive test shell failure. If the test shell action simply
     takes too long because, for example, a parameter has been missed
     and the script is deleting all of ``/usr/lib/`` instead of
     ``/home/test/usr/lib/``, the DUT will likely fail to reboot
     without a new deployment regardless of the skip support.

   * This support is intended for predictable test shell errors.
     Support must be planned into the test job before submission.
     Design your test shell definition and test result handling
     carefully. Any expected test case results from the test shell
     definition which might have occurred after the timeout will be
     completely missing. It is recommended to put the operation which
     is expected to fail as the last command in the test shell
     definition before the test action would normally end.

   * Timeouts are immediate, aggressive and external to the test shell.
     There is no opportunity for the active test shell to respond or
     handle the timeout. The currently executing process will disappear
     and filesystems will **not** be unmounted - power is simply
     removed from the :term:`DUT`. This could affect the ability of the
     DUT to execute the next test shell after a reboot, for example if
     the filesystem cannot be mounted or the previous test action
     failed in the middle of an operation which relies on filesystem
     locks.

   Test writers are wholly responsible for cleaning up any artefacts of
   the failed test shell at the start of the second test shell. For
   example:

   * if the first test shell fails when making persistent changes to
     the filesystem(s) on the DUT, filesystem corruption is possible
     which could cause the second boot action to fail.

   * Test actions which install packages are likely to leave stale lock
     files in place, incompletely installed packages and other breakage.

     Use :ref:`portable test shell definitions
     <test_definition_portability>` and ensure the integrity of the
     packages on the DUT before trying to make more persistent changes
     in the second test action block. Assume that the second test
     action will start in a broken system if no deploy action is
     specified before the second boot action.

For some devices a *deploy* action is also needed to get to a point
where the device will boot successfully. (This is also a way of
ensuring that filesystem corruption issues are avoided - by
re-deploying the filesystem itself in a known clean state.)

.. code-block:: yaml

 - test:
    timeout:
      minutes: 5
      skip: true
    definitions:

 # ... rest of the first test action block

 - boot:
    timeout:
      minutes: 2

 # ... rest of the second boot action block

 - test:
    timeout:
      minutes: 5
    definitions:

 # ... rest of the second test action block
