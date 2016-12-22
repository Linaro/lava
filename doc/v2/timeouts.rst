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
out or recognise that the operation should have completed by some point in time
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

Duration of actions in V2
=========================

The duration of every action in a V2 test job is tracked and recorded. This
allows test writers to look at other similar jobs and evaluate the actual
duration of any operation within that testjob. Equally, it allows lab admins to
compare your timeouts against the actual duration of the operation. If your
jobs start to fail and sit idle for long periods waiting for a timeout, you
have the information to hand to fix the timeouts yourself before you get a
prompt from the admins.

.. _test_shell_timeouts:

Test shell timeouts
===================

Whilst V1 is still supported, the timeout used by the test action is a single
value covering all test operations. This behaviour is expected to change once
V1 submissions are rejected to allow each test definition to specify a timeout.
Actual durations are still tracked and recorded, so excessive timeouts still
need to be addressed.

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

Job timeouts in V2
******************

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

.. comment: FIXME: choose a UBoot example job for this guide once such a job exists
            makes it easier to talk about connection timeouts.
            ensure it uses actions and connections timeout overrrides

.. include:: examples/test-jobs/qemu-pipeline-first-job.yaml
   :code: yaml
   :start-after: job_name: QEMU pipeline, first job
   :end-before: # ACTION_BLOCK

.. _default_action_timeouts:

Default action timeouts
***********************

An action timeout covers the entire operation of all operations performed by
that action. Check the V2 logs for lines like::

 start: 1.1.1 http_download (max 300s)

::

 http_download duration: 25.65

The action timeout ``(max 300s)`` comes from this part of the job definition:

.. include:: examples/test-jobs/qemu-pipeline-first-job.yaml
   :code: yaml
   :start-after: job_name: QEMU pipeline, first job
   :end-before: connection

The complete list of actions for any test job is available from the job
definition page, on the pipeline tab.

.. note:: Not all actions in any one pipeline will perform any operations.
   Action classes are idempotent and can skip operations depending on the
   parameters of the testjob. Hence some actions will show a duration of
   ``0.00``.

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
certain devices which need to initialise certain hardware that takes longer
than most other devices with similar support.

Details of these timeouts can be seen on the device type page on the *Support*
tab and can be overridden using the overrides in the test job.

.. _action_block_timeout_overrides:

Action block overrides
**********************

The test job submission action blocks, (``deploy``, ``boot`` and ``test``) can
also have timeouts. These will override the default action timeout for all
actions within that block. Action blocks are identified by the start of the
:term:`action level` and the timeout value is set within that action block:

.. include:: examples/test-jobs/qemu-pipeline-first-job.yaml
   :code: yaml
   :start-after: qemu-pipeline-first-job.yaml
   :end-before: to: tmpfs

Unless individual actions within this block have overrides, the default action
timeout for each will be set to the specified timeout.

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
     http_download:
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
     http_download:
       minutes: 2

.. seealso:: :ref:`usb_device_wait_timeout`
