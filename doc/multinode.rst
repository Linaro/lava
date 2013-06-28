LAVA Test Shell multi-node
==========================

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
printed in the standard output, each in one line. If no key values were
passed, nothing is printed.

lava-wait-all
-------------

Waits until **all** other devices in the group send a message with the
given message ID. IF ``<role>`` is passed, only wait until all devices
with that given role send a message.

``lava-wait-all <message-id> [<role>]``

If data was sent by the other devices with the message, the key-value
pairs will be printed one per line, prefixed with the device name and
whitespace.

Follows some examples for ``lava-send``, ``lava-wait`` and
``lava-wait-all``.

lava-sync
---------

Global synchronization primitive. Sends a message, and waits for the
same message from all of the other devices.

Usage: ``lava-sync <message>``

``lava-sync foo`` is effectively the same as ``lava-send foo`` followed
by ``lava-wait-all foo``.

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

    server=$(lava-wait server-ready | cut -d = -f 2)
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


