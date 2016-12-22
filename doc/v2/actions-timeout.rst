.. _dispatcher_timeouts:

Timeout Reference
#################

.. note:: The behaviour of actions and connections has changed during the
   development of the V2 dispatcher. See :ref:`connection_timeout` and
   :ref:`default_action_timeout`. Action timeouts can be specified for the
   default for all actions or for a specific action. Connection timeouts can be
   specified as the default for all connections or for the connections made by
   a specific action.

Timeouts now provide more detailed support. Individual actions have uniquely
addressable timeouts.

Timeouts are specified explicitly in days, hours, minutes and seconds. Any
unspecified value is set to zero.

The pipeline automatically records the amount of time elapsed for the complete
run of each action class as ``duration`` as well as the action which sets the
current timeout. Server side processing can now identify when jobs are
submitted with excessively long timeouts and highlight exactly which actions
can use shorter timeouts.

.. _total_job_timeout:

Job timeout
===========

The entire job will have an overall timeout - the job will fail if this timeout
is exceeded, whether or not any other timeout is longer.

A timeout for a job means that the current action will be allowed to complete
and the job will then fail.

.. code-block:: yaml

 timeouts:
   job:
     minutes: 15

.. _default_action_timeout:

Action timeout
==============

Each action has a default timeout which is handled differently according to
whether the action has a current connection to the device.

.. note:: This timeout covers each action class, not per top level action. i.e.
   the top level ``boot`` action includes many actions, from interrupting the
   bootloader and substituting commands to waiting for a shell session or login
   prompt once the boot starts. Each action class within the pipeline is given
   the action timeout unless overridden using :ref:`individual_action_timeout`.

Think of the action timeout as::

  "no single operation of this class should possibly take longer than ..."

along with::

  "the pipeline should wait no longer than ... to determine that the device is not responding."

When changing timeouts, review the pipeline logs for each top level action,
``deploy``, ``boot`` and ``test``.  Check the duration of each action within
each section and set the timeout for that top level action. Specific actions
can be extended using the :ref:`individual_action_timeout` support.

Action timeouts only determine the operation of the action, not the operation
of any connection used by the action. See :ref:`connection_timeout`.

If no action timeout is given in the job, the default action timeout of 30
seconds will be used.

A timeout for these actions interrupts the executing action and marks the job
as Incomplete.

* Log message is of the form: ``${name}: timeout``::

   log: "git-repo-action: timeout. 45 seconds"

The action timeout covers the entire operation of that action and the action
will be terminated if the timeout is exceeded.

The log structure shows the action responsible for the command running within
the specified timeout.

::

   action:
     seconds: 45


.. _individual_action_timeout:

Individual action timeouts
--------------------------

Individual actions can also be specified by name - see the pipeline description
output by the ``validate`` command or the Pipeline Description on the job
definition page to see the full name of action classes::

   extract-nfsrootfs:
    seconds: 60

Individual actions can be referenced by the :term:`action level` and the job
ID, in the form::

 http://<INSTANCE_URL>/scheduler/job/<JOB_ID>/definition#<ACTION_LEVEL>

The level string represents the sequence within the pipeline and is a key
component of how the pipeline data is organised. See also
:ref:`pipeline_construction`.

This allows typical action timeouts to be as short as practical, so that jobs
fail quickly, while allowing for individual actions to take longer.

Typical actions which may need timeout extensions:

#. **lava-test-shell** - unless changed, the :ref:`default_action_timeout`
   applies to running the all individual commands inside each test definition.
   If ``install: deps:`` are in use, it could take a lot longer to update,
   download, unpack and setup the packages than to run any one test within the
   definition.

#. **expect-shell-connection** - used to allow time for the device to boot and
   then wait for a standard prompt (up to the point of a login prompt or shell
   prompt if no login is offered). If the device is expected to raise a network
   interface at boot using DHCP, this could add an appreciable amount of time.

.. _connection_timeout:

Connection timeout
==================

Actions retain the action timeout for the complete duration of the action
``run()`` function. If that function uses a connection to interact with the
device, each connection operation uses the **connection_timeout**, so the
action timeout **must** allow enough time for all the connection operations to
complete within expectations of normal latency.

* Log message is of the form: ``${name}: Wait for prompt``::

   log: "expect-shell-connection: Wait for prompt. 24 seconds"

Before the connection times out, a message will be sent to help prevent serial
corruption from interfering with the expected prompt.

* Warning message is of the form::

   Warning command timed out: Sending ... in case of corruption

The character used depends on the type of connection - a connection which
expects a POSIX shell will use ``#`` as this is a neutral / comment operation.

A timeout for the connection interrupts the executing action and marks the job
as Incomplete.

* Log message is of the form: ``${name}: timeout``::

   log: "git-repo-action: timeout. 45 seconds"

Individual actions may make multiple calls on the connection - different
actions are used when a particular operation is expected to take longer than
other calls, e.g. boot.

Set the default connection timeout which all actions will use when using a
connection:

.. code-block:: yaml

 timeouts:
   connection:
     seconds: 20

Individual connection timeouts
------------------------------

A specific action can be given an individual connection timeout which will be
used by whenever that action uses a connection: If the action does not use a
connection, this timeout will have no effect.

.. code-block:: yaml

 timeouts:
   connections:
     uboot-retry:
       seconds: 120

.. note:: Note the difference between ``connection`` followed by a value for
   the default connection timeout and ``connections``, ``<action_name>``
   followed by a value for the individual connection timeout for that action.

.. _usb_device_wait_timeout:

USB device wait timeout
=======================

When USB devices are disconnected and connected, it needs some time to settle
down, to get recognized by udev - the time required may vary based on various
factors. The `usb-device-wait` timeout applies during the entire job run. The
default value for USB device wait timeout is 30 seconds.

.. code-block:: yaml

 timeouts:
   job:
     minutes: 15
   usb-device-wait:
     seconds: 20
