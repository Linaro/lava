Multi-Node LAVA
===============

LAVA multi-node support allows users to use LAVA to schedule, synchronize and
combine the results from tests that span multiple targets. Jobs can be arranged
as groups of devices (of any type) and devices within a group can operate
independently or use the MultiNode API to communicate with other devices in the
same group during tests.

Within a MultiNode group, devices are assigned a role and a ``count`` of devices to
include into that role. Each role has a ``device_type`` and any number of roles can
have the same ``device_type``. Each role can be assigned ``tags``.

Once roles are defined, actions (including test images and test definitions) can be marked
as applying to specific roles (if no role is specified, all roles use the action).

If insufficient boards exist to meet the combined requirements of all the roles specified
in the job, the job will be rejected.

If there are not enough idle boards of the relevant types to meet the combined requirements
of all the roles specified in the job, the job waits in the Submitted queue until all
devices can be allocated.

Once each board has booted the test image, the MultiNode API will be available for use within
the test definition in the default PATH.

Hardware requirements and virtualisation
========================================

Multi-Node is explicitly about synchronising test operations across multiple boards and running
Multi-Node jobs on a particular instance will have implications for the workload of that instance.
This can become a particular problem if the instance is running on virtualised hardware with
shared I/O, a limited amount of RAM or a limited number of available cores.

e.g. Downloading, preparing and deploying test images can result in a lot of synchronous I/O and
if this instance is running the server and the dispatcher, this can cause the load on that machine
to rise significantly, possibly causing the server to become unresponsive.

It is strongly recommended that Multi-Node instances use a separate dispatcher running on
non-virtualised hardware so that the (possibly virtualised) server can continue to operate.

Also, consider the number of boards connected to any one dispatcher. MultiNode jobs will commonly
compress and decompress several test image files of several hundred megabytes at precisely the same
time. Even with a powerful multi-core machine, this has been shown to cause appreciable load. It
is worth consdering matching the number of boards to the number of cores for parallel decompression
and matching the amount of available RAM to the number and size of test images which are likely to
be in use.

LAVA Test Shell multi-node submissions
======================================

To extend an existing JSON file to start a MultiNode job, some changes are required to define the
``device_group``. If all devices in the group are to use the same actions, simply create a single
role with a count for how many devices are necessary. Usually, a MultiNode job will need to assign
different test definitions to different boards and this is done by adding more roles, splitting the
number of devices between the differing roles and assigning different test definitions to each role.

If a MultiNode job includes devices of more than one ``device_type``, there needs to be a role for
each different ``device_type`` so that an appropriate image can be deployed.

Where all roles share the same action (e.g. ``submit_results_on_host``), omit the role parameter from
that action.

If more than one, but not all, roles share one particular action, that action will need to be repeated
within the JSON file, once for each role using that action.

Changes to submission JSON
--------------------------

1. ``device`` or ``device_type`` move into a **device_group** list
2. Each device type has a ``count`` assigned
  1. If a ``device`` is specified directly, count needs to be one.
  2. If ``device_type`` is used and count is larger than one, enough 
     devices will be allocated to match the count and all such devices will
     have the same role and use the same commands and the same actions.
3. Add tags, if required, to each role.
4. If specific actions should only be used for particular roles, add a
   role field to the parameters of the action.
5. If any action has no role specified, it will be actioned for all roles.

A simple device_group
^^^^^^^^^^^^^^^^^^^^^

Example JSON::

 {
    "timeout": 18000,
    "job_name": "simple multinode job",
    "logging_level": "INFO",
    "device_group": [
        {
            "role": "omap4",
            "count": 2,
            "device_type": "panda",
            "tags": [
                "mytag1"
            ]
        },
        {
            "role": "omap3",
            "count": 1,
            "device_type": "beaglexm",
            "tags": [
                "mytag2"
            ]
        }
    ],

Using actions for particular roles
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Example JSON::

    "actions": [
        {
            "command": "deploy_linaro_image",
            "parameters": {
                "image": "file:///home/instance-manager/images/panda-raring_developer_20130529-347.img.gz",
                "role": "omap4"
            }
        },
        {
            "command": "deploy_linaro_image",
            "parameters": {
                "image": "file:///home/instance-manager/images/beagle-ubuntu-desktop.img.gz",
                "role": "omap3"
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
                "timeout": 1800
            }
        }
    }

..

.. note:: Consider using http://jsonlint.com to check your JSON before submission.


MultiNode API
=============

The LAVA MultiNode API provides a simple way to pass messages using the serial port connection which
is already available through LAVA. The API is not intended for transfers of large amounts of data. Test
definitions which need to transfer files, long messages or other large amounts of data need to set up their
own network configuration, access and download methods and do the transfer in the test definition.

lava-self
---------

Prints the name of the current device.

Usage: ``lava-self``

lava-role
---------

Prints the role the current device is playing in a multi-node job.

Usage: ``lava-role``

*Example.* In a directory with several scripts, one for each role
involved in the test::

    $ ./run-$(lava-role)

lava-group
----------

This command will produce in its standard output a representation of the
device group that is participating in the multi-node test job.

Usage: ``lava-group``

The output format contains one line per device, and each line contains
the hostname and the role that device is playing in the test, separated
by a TAB character::

    panda01     client
    highbank01  loadbalancer
    highbank02  backend
    highbank03  backend

lava-send
---------

Sends a message to the group, optionally passing associated key-value
data pairs. Sending a message is a non-blocking operation. The message
is guaranteed to be available to all members of the group, but some of
them might never retrieve it.

Usage: ``lava-send <message-id> [key1=val1 [key2=val2] ...]``

Examples will be provided below, together with ``lava-wait`` and
``lava-wait-all``.

lava-wait
---------

Waits until any other device in the group sends a message with the given
ID. This call will block until such message is sent.

Usage: ``lava-wait <message-id>``

If there was data passed in the message, the key-value pairs will be
printed in the cache file(/tmp/lava_multi_node_cache.txt in default),
each in one line. If no key values were passed, nothing is printed.

The message ID data is persistent for the life of the MultiNode group.
The data can be retrieved at any later stage using ``lava-wait`` and as
the data is already available, there will be no waiting time for repeat
calls. If devices continue to send data with the associated message ID,
that data will continue to be added to the data for that message ID and
will be returned by subsequent calls to ``lava-wait`` for that message
ID. Use a different message ID to collate different message data.

lava-wait-all
-------------

Waits until **all** other devices in the group send a message with the
given message ID. IF ``<role>`` is passed, only wait until all devices
with that given role send a message.

``lava-wait-all <message-id> [<role>]``

If data was sent by the other devices with the message, the key-value
pairs will be printed in the cache file(/tmp/lava_multi_node_cache.txt
in default),each in one line, prefixed with the target name and
a colon.

Some examples for ``lava-send``, ``lava-wait`` and
``lava-wait-all`` are given below.

Using ``lava-sync`` or ``lava-wait-all`` in a test definition effectively
makes all boards in the group run at the speed of the slowest board in
the group up to the point where the sync or wait is called.

<<<<<<< HEAD
=======
Ensure that the message-id matches an existing call to ``lava-send`` for
each relevant test definition **before** that test definition calls
``lava-wait-all`` or any device using that test definition will wait forever
(and eventually timeout, failing the job).

The message returned can include data from other devices which sent a
message with the relevant message ID, only the wait is dependent on
particular devices with a specified role.

As with ``lava-wait``, the message ID is persistent for the duration of
the MultiNode group.

lava-sync
---------

Global synchronization primitive. Sends a message, and waits for the
same message from all of the other devices.

Usage: ``lava-sync <message>``

``lava-sync foo`` is effectively the same as ``lava-send foo`` followed
by ``lava-wait-all foo``.

lava-network
------------

Helper script to broadcast IP data from the test image, wait for data to be
received by the rest of the group (or one role within the group) and then provide
an interface to retrieve IP data about the group on the command line.

Raising a suitable network interface is a job left for the designer of the test
definition / image but once a network interface is available, ``lava-network``
can be asked to broadcast this information to the rest of the group. At a later
stage of the test, before the IP details of the group need to be used, call
``lava-network collect`` to receive the same information about the rest of
the group.

All usage of lava-network needs to use a broadcast (which wraps a call to
``lava-send``) and a collect (which wraps a call to ``lava-wait-all``). As a
wrapper around ``lava-wait-all``, collect will block until the rest of the group
(or devices in the group with the specified role) has made a broadcast.

After the data has been collected, it can be queried for any board specified in
the output of ``lava-group`` by specifying the parameter to query (as used in the
broadcast)::

 lava-network query panda19 ipv4
 192.168.3.56

 lava-network query beaglexm04 ipv6
 fe80::f2de:f1ff:fe46:8c21

 lava-network query arndale02 hostname
 server

 lava-network query panda14 hostname-full
 client.localdomain

 lava-network query panda19 netmask
 255.255.255.0

 lava-network query panda14 default-gateway
 192.168.1.1

 lava-network query panda17 dns_2
 8.8.8.8

``lava-network hosts`` can be used to output the list of all boards in the group
which have returned a fully qualified domain name in a format suitable for
``/etc/hosts``, appending to the specified file.

Usage:

 broadcast: ``lava-network broadcast [interface]``

 collect:   ``lava-network collect [interface] <role>``

 query:     ``lava-network query [hostname] [option]``

 hosts:     ``lava-network hosts [file]``

Example 1: simple client-server multi-node test
-----------------------------------------------

Two devices, with roles ``client``, ``server``

LAVA Test Shell test definition (say, ``example1.yaml``)::

    run:
        steps:
            - ./run-`lava-role`.sh

The test image or the test definition would then provide two scripts,
with only one being run on each device, according to the role specified.

``run-server.sh``::

    #!/bin/sh

    iperf -s &
    lava-send server-ready username=testuser
    lava-wait client-done

Notes:

* To make use of the server-ready message, some kind of client
  needs to do a ``lava-wait server-ready``
* There needs to be a support on a client to do the
  ``lava-send client-done`` or the wait will fail on the server.
* If there was more than one client, the server could call
  ``lava-wait-all client-done`` instead.


``run-client.sh``::

    #!/bin/sh

    lava-wait server-ready
    server=$(cat /tmp/lava_multi_node_cache.txt | cut -d = -f 2)
    iperf -c $server
    # ... do something with output ...
    lava-send client-done

Notes:

* The client waits for the server-ready message as it's first task,
  then does some work, then sends a message so that the server can
  move on and do other tests.

Example 2: variable number of clients
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

Example 3: peer-to-peer application
-----------------------------------

Single role: ``peer``, any number of devices

``run-peer.sh``::

    #!bin/sh

    initialize-data
    start-p2p-service
    lava-sync running

    push-data
    for peer in $(lava-group | cut -f 1); then
        if [ $peer != $(lava-self) ]; then
            query-data $peer
        fi
    fi


Example 4: using lava-network
-----------------------------

If the available roles include ''server'' and there is a board named
''database''::

   #!/bin/sh
   ifconfig eth0 up
   # possibly do your own check that this worked
   lava-network broadcast eth0
   # do whatever other tasks may be suitable here, then wait...
   lava-network collect eth0 server
   # continue with tests and get the information.
   lava-network query database ipv4

LAVA Multi-Node timeout behaviour
=================================

The submitted JSON includes a timeout value - in single node LAVA, this is applied to each individual action
executed on the device under test (not for the entire job as a whole). i.e. the default timeout can be smaller
than any one individual timeout used in the JSON or internally within LAVA.

In Multi-Node LAVA, this timeout is also applied to individual polling operations, so an individual lava-sync
or a lava-wait will fail on any node which waits longer than the default timeout. The node will receive a failure
response.

Recommendations on timeouts
---------------------------

MultiNode operations have implications for the timeout values used in JSON submissions. If one of the
synchronisation primitives times out, the sync will fail and the job itself will then time out.
One reason for a MultiNode job to timeout is if one or more boards in the group failed to boot the
test image correctly. In this situation, all the other boards will continue until the first
synchronisation call is made in the test definition for that board.

The time limit applied to a synchronisation primitive starts when the board makes the first request
to the Coordinator for that sync. Slower boards may well only get to that point in the test definition
after faster devices (especially KVM devices) have started their part of the sync and timed out
themselves.

Always review the top level timeout in the JSON submission - a value of 900 seconds (15 minutes) has
been common during testing. Excessive timeouts would prevent other jobs from using boards where the
waiting jobs have already failed due to a problem elsewhere in the group. If timeouts are too short,
jobs will fail unnecessarily.

LAVA Coordinator setup
======================

Multi-Node LAVA requires a LAVA Coordinator which manages the messaging within a group of nodes involved in
a Multi-Node job set according to this API. The LAVA Coordinator is a singleton to which nodes need to connect
over a TCP port (default: 3079). A single LAVA Coordinator can manage groups from multiple instances.
If the network configuration uses a firewall, ensure that this port is open for connections from Multi-Node dispatchers.

If multiple coordinators are necessary on a single machine (e.g. to test different versions of the coordinator
during development), each coordinator needs to be configured for a different port.

If the dispatcher is installed on the same machine as the coordinator, the dispatcher can use the packaged
configuration file with the default hostname of ``localhost``.

Each dispatcher then needs a copy of the LAVA Coordinator configuration file, modified to point back to the
hostname of the coordinator:

Example JSON, modified for a coordinator on a machine with a fully qualified domain name::

  {
    "port": 3079,
    "blocksize": 4096,
    "poll_delay": 3,
    "coordinator_hostname": "control.lab.org"
  }

An IP address can be specified instead, if appropriate.

Each dispatcher needs to use the same port number and blocksize as is configured for the Coordinator
on the specified machine. The poll_delay is the number of seconds each node will wait before polling
the coordinator again.
