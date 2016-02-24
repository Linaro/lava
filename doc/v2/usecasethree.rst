.. index:: network information

.. _use_case_three:

Use Case Three - Retrieve information about multiple network interfaces
***********************************************************************

Requirements
============

 * Multiple devices running the same test definition.
 * At least one device in the group has multiple network interfaces.
 * Some interfaces on some devices may be impossible to raise.
 * All devices are connected such that it is possible for each device to
   communicate with the other devices in the same group.
 * Discover which interface and therefore which IP address to use for each device within the group.
 * Data to be collected for IPv4 and IPv6, where possible.

Principles
==========

 * The group composition needs to be determined each run.
 * Network interfaces which can be raised are raised beforehand.

Method
======

Instead of needing to broadcast and collect for each interface across
all boards (including interfaces which only exist on some boards), this
use case looks at a simpler method of obtaining the relevant data outside
``lava-network``. 

The assumption in this use case is that a group of devices each with
multiple network interfaces needs to identify which IP addresses on which
interfaces can be used to allow communication between all devices in the
group. This requires that the devices are already connected in such a way
to allow such communication and that there is a simple way to tell which
IP address should be used. The methods are extensible to other network
configurations, as long as there remains some way to identify which IP
address should be used.

Send details of interfaces on each device
-----------------------------------------

On each device, a simple parsing of ``/sbin/ifconfig -a -s`` will show which
interfaces are available and a futher call for each interface will show
which have IPv4 addresses.

Shell snippet::

    #!/bin/sh
    
    set -e
    
    LINE="lava-send interfaces"
    LIST=`/sbin/ifconfig -a -s|cut -d' ' -f1|grep -v "^Iface" |grep -v "^lo"|tr '\n' ' '`
    for IFACE in $LIST; do
        IP4=`/sbin/ifconfig $IFACE|grep "inet addr"|cut -d: -f2|cut -d' ' -f1`
        if [ -z "$IP4" ]; then
            IP4=0
        fi
        LINE="$LINE ${IFACE}=${IP4}"
    done
    $LINE

This can be extended for IPv6 addresses::

    #!/bin/sh
    
    set -e
    
    LINE="lava-send interfaces"
    LIST=`/sbin/ifconfig -a -s|cut -d' ' -f1|grep -v "^Iface" |grep -v "^lo"|tr '\n' ' '`
    for IFACE in $LIST; do
        IP6=`/sbin/ifconfig $IFACE |grep "inet6 addr"|cut -d: -f2-|cut -d'/' -f1|cut -d' ' -f2`
        if [ -z "$IP6" ]; then
            IP6=0
        fi
        LINE="$LINE ${IFACE}=${IP6}"
    done
    $LINE

Combined script::

    #!/bin/sh
    
    set -e
    
    LINE="lava-send interfaces"
    LIST=`/sbin/ifconfig -a -s|cut -d' ' -f1|grep -v "^Iface" |grep -v "^lo"|tr '\n' ' '`
    for IFACE in $LIST; do
        IP4=`/sbin/ifconfig $IFACE|grep "inet addr"|cut -d: -f2|cut -d' ' -f1`
        if [ -z "$IP4" ]; then
            IP4=0
        fi
        LINE="$LINE ${IFACE}-ipv4=${IP4}"
        IP6=`/sbin/ifconfig $IFACE |grep "inet6 addr"|cut -d: -f2-|cut -d'/' -f1|cut -d' ' -f2`
        if [ -z "$IP6" ]; then
            IP6=0
        fi
        LINE="$LINE ${IFACE}-ipv6=${IP6}"
    done
    $LINE

This information is then sent to the rest of the group using :ref:`lava_send`.

Retrieve data from the rest of the group
----------------------------------------

Each device then needs to run ``lava-wait-all interfaces`` and parse the
cache file to get the data. (Use the ``role`` support in :ref:`lava_wait_all`
if appropriate.)

For the IPv4 snippet, this could be content along the lines of::

  playground-kvm01:eth0=192.168.11.144
  playground-kvm01:eth1=172.31.54.58
  playground-kvm02:eth0=192.168.24.15
  playground-kvm02:eth1=0

The cache content is cleared when the next LAVA MultiNode API 
synchronisation call is made (:ref:`lava_send`, :ref:`lava_sync`, :ref:`lava_network`,
:ref:`lava_wait`, :ref:`lava_wait_all`).

Parse data
----------

Match the device_name in the cache with the output of :ref:`lava_group`::

  playground-kvm01	rex
  playground-kvm02	felix

shell snippet to find local IPv4 addresses for use within the group::

    GROUP=`lava-group | cut -d: -f2 | cut -f1`
    for DEVICE in $GROUP; do
        VAL=`grep $DEVICE /tmp/lava_multi_node_cache.txt | grep 192\.168\.`
        echo $VAL
    done

Giving output along the lines of::

    playground-kvm01:eth0=192.168.11.144
    playground-kvm02:eth0=192.168.24.15

Further queries
---------------

With this information, each device can call ``lava-network broadcast``
and ``lava-network collect`` for the relevant interface(s), if more
information is needed about each device. (``lava-network query`` works
on data from the most recent ``collect`` operation.)
