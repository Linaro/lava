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

Follows some examples for ``lava-send``, ``lava-wait`` and
``lava-wait-all``.

Using ``lava-sync`` or ``lava-wait-all`` in a test definition effectively
makes all boards in the group run at the speed of the slowest board in
the group up to the point where the sync or wait is called.

Ensure that the message-id matches an existing call to ``lava-send`` for
each relevant test definition **before** that test definition calls
``lava-wait-all`` or any device using that test definition will wait forever
(and eventually timeout, failing the job).

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
the output of ``lava-group``::

 lava-network query server
 192.168.3.56

``lava-network hosts`` can be used to output the list of all boards in the group
which have returned a fully qualified domain name in a format suitable for
``/etc/hosts``

Usage:

 broadcast: ``lava-network broadcast [interface]``

 collect:   ``lava-network collect [interface] <role>``

 query:     ``lava-network query [hostname]``

 hosts:     ``lava-network hosts``

Example 1: simple client-server multi-node test
-----------------------------------------------

2 devices, with roles ``client``, ``server``

LAVA Test Shell test definition (say, ``example1.yaml``)::

    run:
        steps:
            - lava-group >> /etc/hosts
            - ./run-`self-role`.sh

``run-server.sh``::

    #!/bin/sh

    iperf -s &
    lava-send server-ready ip=$(get-my-ip)
    lava-wait client-done

Notes:

* The implementation of ``get-my-ip`` is left as an exercise for the
  reader. ;-)

* if there was more than one client, the server could call
  ``lava-wait-all client-done`` instead. Actually if


``run-client.sh``::

    #!/bin/sh

    lava-wait server-ready
    server=$(cat /tmp/lava_multi_node_cache.txt | cut -d = -f 2)
    iperf -c $server
    # ... do something with output ...
    lava-send client-done

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

    lava-sync finished

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
   lava-network query database

..