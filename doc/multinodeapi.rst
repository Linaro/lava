.. _multinode_api:

MultiNode API
=============

The LAVA MultiNode API provides a simple way to pass messages using the serial port connection which
is already available through LAVA. The API is not intended for transfers of large amounts of data. Test
definitions which need to transfer files, long messages or other large amounts of data need to set up their
own network configuration, access and download methods and do the transfer in the test definition.

.. index:: lava-self

.. _lava_self:

lava-self
---------

Prints the name of the current device.

Usage: ``lava-self``

.. index:: lava-role

.. _lava_role:

lava-role
---------

Usage: ``lava-role``

Prints the role the current device is playing in a multi-node job.

*Example.* In a directory with several scripts, one for each role
involved in the test::

    $ ./run-$(lava-role)

Usage: ``lava-role list``

Prints a list of all roles within this multi-node job, separated by
whitespace.::

    #!/bin/sh
    for role in `lava-role list`; do
        echo $role
    done

See :ref:`use_case_four`

.. index:: lava-group

.. _lava_group:

lava-group
----------

Usage: ``lava-group``

This command will produce in its standard output a representation of the
device group that is participating in the multi-node test job.

The output format contains one line per device, and each line contains
the hostname and the role that device is playing in the test, separated
by a TAB character::

    panda01     client
    highbank01  loadbalancer
    highbank02  backend
    highbank03  backend

Usage: ``lava-group role``

This command will produce in its standard output a list of the
device names assigned the specified role in the multi-node test job.

The output format contains one line per device assigned to the specified
role with no whitespace. The matched role is not output.::

    $ lava-group client
    panda01
    $ lava-group backend
    highbank02
    highbank03

If there is no matching role, exit non-zero and output nothing.::

    $ lava-group server ; echo $?
    1

If your test definition relies on a particular role, one of the first
test cases should be to check this role has been defined::

  - lava-test-case check-server-role --shell lava-group server

The output can be used to iterate over all devices with the specified
role::

    #!/bin/sh
    for device in `lava-group backend`; do
        echo $device
    done

See :ref:`use_case_four`

.. index:: lava-send

.. _lava_send:

lava-send
---------

Sends a message to the group, optionally passing associated key-value
data pairs. Sending a message is a non-blocking operation. The message
is guaranteed to be available to all members of the group, but some of
them might never retrieve it.

The message-id will be persistent for the lifetime of the target group
managing the entire multinode test job. Re-sending a different message
with an existing message-id is not supported.

Usage: ``lava-send <message-id> [key1=val1 [key2=val2] ...]``

Examples will be provided below, together with ``lava-wait`` and
``lava-wait-all``.

.. index:: lava-wait

.. _lava_wait:

lava-wait
---------

Waits until any other device in the group sends a message with the given
ID. This call will block until such message is sent.

Usage: ``lava-wait <message-id>``

If there was data passed in the message, the key-value pairs will be
printed in the cache file (/tmp/lava_multi_node_cache.txt in default),
each in one line. If no key values were passed, nothing is printed.

The message ID data is persistent for the life of the MultiNode group.
The data can be retrieved at any later stage using ``lava-wait`` and as
the data is already available, there will be no waiting time for repeat
calls. If devices continue to send data with the associated message ID,
that data will continue to be added to the data for that message ID and
will be returned by subsequent calls to ``lava-wait`` for that message
ID. Use a different message ID to collate different message data.

.. index:: lava-wait-all

.. _lava_wait_all:

lava-wait-all
-------------

Waits until **all** other devices in the group send a message with the
given message ID. IF ``<role>`` is passed, only wait until all devices
with that given role send a message.

``lava-wait-all <message-id> [<role>]``

If data was sent by the other devices with the message, the key-value
pairs will be printed in the cache file (/tmp/lava_multi_node_cache.txt
in default),each in one line, prefixed with the target name and
a colon.

Some examples for ``lava-send``, ``lava-wait`` and
``lava-wait-all`` are given below.

Using ``lava-sync`` or ``lava-wait-all`` in a test definition effectively
makes all boards in the group run at the speed of the slowest board in
the group up to the point where the sync or wait is called.

Ensure that the message-id matches an existing call to ``lava-send`` for
each relevant test definition **before** that test definition calls
``lava-wait-all`` or any device using that test definition will wait forever
(and eventually timeout, failing the job).

The message returned can include data from other devices which sent a
message with the relevant message ID, only the wait is dependent on
particular devices with a specified role.

As with ``lava-wait``, the message ID is persistent for the duration of
the MultiNode group.

.. index:: lava-sync

.. _lava_sync:

lava-sync
---------

Global synchronization primitive. Sends a message, and waits for the
same message from all of the other devices.

Usage: ``lava-sync <message>``

``lava-sync foo`` is effectively the same as ``lava-send foo`` followed
by ``lava-wait-all foo``.

.. index:: lava-network

.. _lava_network:

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

The key-value pairs will be printed in the cache
file (/tmp/lava_multi_node_network_cache.txt in default),
each in one line, prefixed with the target name and a colon.

The information broadcast about each interface is:

* hostname - ``hostname -f`` if supported, or just ``hostname``
* netmask
* broadcast
* MAC address
* nameserver entries in ``/etc/resolv.conf`` using the
  pattern ``dns_N``, starting at one.
* ipv4 address
* ipv6 address (if any)
* default-gateway

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

 lava-network query panda06 mac
 52:54:30:10:34:56

``lava-network hosts`` can be used to output the list of all boards in the group
which have returned a fully qualified domain name in a format suitable for
``/etc/hosts``, appending to the specified file.

 10.1.1.2	staging-kvm01
 10.1.1.6	staging-kvm02.localdomain
 10.1.1.2	staging-kvm03
 10.1.1.3	staging-kvm04

Usage:

 broadcast: ``lava-network broadcast [interface]``

 collect:   ``lava-network collect [interface] <role>``

 query:     ``lava-network query [hostname] [option]``

 hosts:     ``lava-network hosts [file]``

``lava-network alias-hosts`` is an optional extension which extends the
``lava-network hosts`` support to use the role of each device in the
group as an alias in the output. See :ref:`role_aliases` for more
information on the limitations of using roles as aliases.

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

If the available roles include ``server`` and there is a board named
``database``::

   #!/bin/sh
   ifconfig eth0 up
   # possibly do your own check that this worked
   lava-network broadcast eth0
   # do whatever other tasks may be suitable here, then wait...
   lava-network collect eth0 server
   # continue with tests and get the information.
   lava-network query database ipv4
