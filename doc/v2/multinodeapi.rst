.. index:: MultiNode API

.. _multinode_api:

MultiNode API
=============

The LAVA MultiNode API provides a simple way to pass messages between devices in
a group, using the connection which is already available through LAVA. The API is
not intended for transfers of large amounts of data. Test definitions which need to
transfer files, long messages or other large amounts of data need to set up
their own network configuration, access and download methods and do the
transfer in the test definition.

Guidance in using the API
-------------------------

It is recommended to avoid doing a lot of calculation within the calls to the
API. There are times when a script is needed to retrieve data from the test
shell, but avoid running that script in the call to the API.
**Always** check the output of the script (e.g. with ``lava-test-case``) and/or
run the script separately in the test definition run steps so that the output
appears in the test job logs. Preparing and outputting the data before sending
it with the API will aid in debugging the test definition.

.. note:: Debugging of complex test definitions does **not** only happen during
   the initial development. There may be further issues and corner cases,
   uncovered only after a test job was in use for a while. Retain enough
   structure in your test definitions to be able to debug problems later
   without needing to resubmit the MultiNode test job (as some problems may
   be non-deterministic, etc.).

.. note:: It is not recommended to use ``lava-test-case`` command in
          conjunction with the MultiNode API calls. The first reason is that
          any errors that might occur within the API will be ignored by the
          lava-test-case and it will be seen as successful by
          ``lava-test-shell``. The second reason is that the job will end up with
          duplicate test cases for each API call (one from ``lava-test-case``
          and the other one from API command).

.. seealso:: :ref:`Limitations of hacking sessions <hacking_session_limitations>`

.. index:: lava-self

.. _lava_self:

lava-self
---------

Usage:
^^^^^^
 ``lava-self``

``lava-self`` reports the job ID, as the dispatcher itself has no
knowledge of the hostname of the deployed system or the original database
name of the device. The output of ``lava-group`` can also be used. (This
behavior changed in the 2017.9 release.)

.. index:: lava-role

.. _lava_role:

lava-role
---------

Usage:
^^^^^^
 ``lava-role``

Prints the role the current device is playing in a MultiNode job.

*Example.* In a directory with several scripts, one for each role involved in
the test::

    $ ./run-$(lava-role)

Usage:
^^^^^^
 ``lava-role list``

Prints a list of all roles within this MultiNode job, separated by
whitespace.::

    #!/bin/sh
    for role in `lava-role list`; do
        echo $role
    done

.. comment FIXME: seealso :ref:`use_case_four`

.. index:: lava-group

.. _lava_group:

lava-group
----------

Usage:
^^^^^^
 ``lava-group``

This command will produce in its standard output a representation of the device
group that is participating in the MultiNode test job.

The output format contains one line per device, and each line contains the
job ID and the role that job is playing in the test, separated by a TAB
character::

    12345     client
    12346     loadbalancer
    12347     backend
    12348     backend

.. caution:: This behavior changed in 2017.9 as V2 does not have knowledge
   of the device hostname, only the job ID for each role.

Usage:
^^^^^^
 ``lava-group <role>``

This command will produce in its standard output a list of the test jobs
assigned the specified role in the MultiNode test job.

The output format contains one line per job ID assigned to the specified role.
The name of the role itself is not printed::

    $ lava-group client
    12345
    $ lava-group backend
    12347
    12348

If there is no matching role, exits with non-zero status code and outputs
nothing::

    $ lava-group server ; echo $?
    1

If your test definition relies on a particular role, one of the first test
cases should be to check this role has been defined::

  - lava-test-case check-server-role --shell lava-group server

.. comment FIXME: seealso:: :ref:`use_case_four`

.. index:: lava-send

.. _lava_send:

lava-send
---------

Sends a message to the group, optionally passing associated key-value data
pairs. Sending a message is a non-blocking operation. The message is guaranteed
to be available to all members of the group, but some of them might never
retrieve it.

The message-id will be persistent for the lifetime of the target group managing
the entire multinode test job. Re-sending a different message with an existing
message-id is not supported.

Usage:
^^^^^^
 ``lava-send <message-id> [key1=val1 [key2=val2] ...]``

Examples are provided below, together with ``lava-wait`` and
``lava-wait-all``.

.. index:: lava-wait

.. _lava_wait:

lava-wait
---------

Waits until any device in the group sends a message with the given ID.
This call will block until such message is sent.

Usage:
^^^^^^
 ``lava-wait <message-id>``

If there was data passed in the message, the key-value pairs will be stored in
the cache file (``/tmp/lava_multi_node_cache.txt`` by default), each in one line.
If no key-values were passed, nothing is stored.

The message ID data is persistent for the life of the MultiNode group. The data
can be retrieved at any later stage using ``lava-wait`` and as the data is
already available, there will be no waiting time for repeat calls. If devices
continue to send data with the associated message ID, that new data will continue
to be added to the stored data for that message ID and will be returned by subsequent
calls to ``lava-wait`` for that message ID. Use different message ID(s) if you
don't want this effect.

.. seealso:: :ref:`flow_tables`

.. index:: lava-wait-all

.. _lava_wait_all:

lava-wait-all
-------------

``lava-wait-all`` operates in different ways, depending on the presence of the
``role`` parameter.

``lava-wait-all <message-id> [<role>]``

If data was sent by the devices with the message, the key-value pairs
will be stored in the cache file (``/tmp/lava_multi_node_cache.txt`` by default),
each in one line, prefixed with the target name and a colon.

Some examples for ``lava-send``, ``lava-wait`` and ``lava-wait-all`` are given
below.

The message returned can include data from devices which sent a message
with the relevant message ID, only the wait is dependent on particular devices
with a specified role.

As with ``lava-wait``, the message ID is persistent for the duration of the
MultiNode group.

lava-wait-all <message-id>
^^^^^^^^^^^^^^^^^^^^^^^^^^

``lava-wait-all <message-id>``

``lava-wait-all`` waits until **all** devices in the group send a message
with the given message ID. Every device in the group **must** use ``lava-send``
with the same message ID for ``lava-wait-all`` to finish, or any device using
this API call will wait forever (and eventually timeout, failing the
job).

Using ``lava-sync`` or ``lava-wait-all`` in a test definition effectively makes
all boards in the group run at the speed of the slowest board in the group up
to the point where the sync or wait is called.

.. seealso:: :ref:`flow_tables`

lava-wait-all <message-id> <role>
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

``lava-wait-all <message-id> <role>``

If ``<role>`` is used, only wait until all devices with that given role send a
message with the matching message ID. Devices of the given role do **not**
enter ``lava-wait``, but just send the message and continue the test
definition. Ensure the test continues for long enough for the devices using
``lava-wait-all`` to pick up the message and act on it. Typically, this
involves using a ``lava-sync`` after the ``lava-send`` on devices with the
given role and after the completion of the task on the devices which were
waiting for the message.

Not all roles in the group need to send a message or wait for a message. One
role will act as a sender, at least one role will act as a receiver and any
other roles can continue as normal. Note that this level of fine-grained control
is usually not needed. It is advisable to draw out the sequence in a table to
ensure that the correct calls are made.

.. seealso:: :ref:`flow_tables`

.. index:: lava-sync

.. _lava_sync:

lava-sync
---------

Global synchronization primitive. Sends a message, and waits for the same
message from all of the other devices.

Usage:
^^^^^^
 ``lava-sync <message>``

``lava-sync foo`` is effectively the same as ``lava-send foo`` followed by
``lava-wait-all foo``.

A :ref:`lava test result <recording_test_result_data>` is generated within the
current :ref:`results_test_suite`, recording the completion or failure of the
synchronization.

.. seealso:: :ref:`flow_tables`

Example 1: Simple client-server MultiNode test
----------------------------------------------

Two devices, with roles ``client``, ``server``

LAVA Test Shell test definition (say, ``example1.yaml``)::

    run:
        steps:
            - ./run-`lava-role`.sh

The test image or the test definition would then provide two scripts, with only
one being run on each device, according to the role specified.

``run-server.sh``::

    #!/bin/sh

    SPACE=`df -h | grep "/$" | awk '{print $4}'`
    echo $SPACE
    lava-send server-ready free-space=$SPACE

Notes:

* To make use of the server-ready message, some kind of client needs
  to do a ``lava-wait server-ready``

``run-client.sh``::

    #!/bin/sh

    lava-wait server-ready
    free-space=$(cat /tmp/lava_multi_node_cache.txt | cut -d = -f 2)
    echo "The free disk space on server is ${free-space}"

Notes:

* The client waits for the server-ready message then get the data
  which was sent by server from /tmp/lava_multi_node_cache.txt

Example 2: iperf client-server test
-----------------------------------

Two devices, with roles ``client``, ``server``

LAVA Test Shell test definition (say, ``example1.yaml``)::

    run:
        steps:
            - ./run-`lava-role`.sh

The test image or the test definition would then provide two scripts, with only
one being run on each device, according to the role specified.

``run-server.sh``::

    #!/bin/sh

    iperf -s &
    echo $! > /tmp/iperf-server.pid
    IP=`ip route get 8.8.8.8 | head -n 1 | awk '{print $NF}'`
    echo $IP
    lava-send server-ready server-ip=$IP
    lava-wait client-done
    kill -9 `cat /tmp/iperf-server.pid`

Notes:

* iperf server process needs to be run in the background to wait for
  the connection from the client and the process id will be stored
  somewhere for later use.
* To make use of the server-ready message, some kind of client needs
  to do a ``lava-wait server-ready``
* There needs to be a support on a client to do the ``lava-send
  client-done`` or the server role will fail with a timeout.
* If there was more than one client, the server could call
  ``lava-wait-all client-done`` instead.
* iperf server process must be killed after getting client-done
  message, otherwise the test job will not proceed.


``run-client.sh``::

    #!/bin/sh

    lava-wait server-ready
    server=$(cat /tmp/lava_multi_node_cache.txt | cut -d = -f 2)
    iperf -c $server
    # ... do something with output ...
    lava-send client-done

Notes:

* The client waits for the server-ready message as its first task,
  then does some work, then sends a "done" message so that the server can
  move on and do other tests.

Example 3: variable number of clients
-------------------------------------

``run-server.sh``::

    #!/bin/sh

    start-server
    lava-sync ready
    lava-sync done

``run-client.sh``::

    #!/bin/sh

    # refer to the server by name, assume internal DNS works
    server=$(lava-group | grep 'server$' | cut -f 1)

    lava-sync ready
    run-client
    lava-sync done

Example 4: peer-to-peer application
-----------------------------------

Single role: ``peer``, any number of devices

``run-peer.sh``::

    #!bin/sh

    initialize-data
    start-p2p-service
    lava-sync running

    push-data
    for peer in $(lava-group | cut -f 1); do
        if [ $peer != $(lava-self) ]; then
            query-data $peer
        fi
    done

.. _flow_tables:

Using a flow table to plan the job
----------------------------------

Synchronization of any type needs to be planned and the simplest way to manage
the messages between roles within a group is to set out a strict table of the
flow.

Set out the call and leave blank rows until that call is matched by the
appropriate roles, to represent the time that the devices with that role will
block in a wait loop with the coordinator.

+-----------------+----------------------------+-----------------+
| Server          | Client                     | Observer        |
+=================+============================+=================+
| deploy & boot   | deploy & boot              | deploy & boot   |
+-----------------+----------------------------+-----------------+
| lava-sync start | lava-sync start            | lava-sync start |
+-----------------+----------------------------+-----------------+
| server_start.sh | lava-wait-all ready server | lava-sync fin   |
+-----------------+----------------------------+-----------------+
| lava-send ready |                            |                 |
+-----------------+----------------------------+-----------------+
| lava-sync fin   | client-tasks.sh            |                 |
+-----------------+----------------------------+-----------------+
|                 | lava-sync fin              |                 |
+-----------------+----------------------------+-----------------+

In this overly simplistic table, the Observer role really has nothing useful to
do but to demonstrate that it will spend most of it's time in ``lava-sync
fin``.

All roles will wait in ``lava-sync start`` until all deploy and boot operations
(or whatever other tasks are put ahead of the call to ``lava-sync``) are
complete. The flow table does not include this delay.

The Server role runs a script to start a service, sending "ready" when the script
returns.

The Client role waits until all devices with the Server role have completed
``lava-send ready``. Observer is unaffected and Server moves directly into the
``lava-sync fin``. Once the Client completes ``lava-wait-all ready server``,
the Client can run the client tasks script. That script finally puts the
devices with the Client role into ``lava-sync fin`` at which point, the Client
role receives the message that everyone else is already in that sync, the sync
completes and the flow table ends.

Tables like this also help visualize how long the timeouts need to be to allow
the Observer role to wait for all the server tasks and all the client tasks to
complete.
