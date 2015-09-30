.. index:: vland

.. _vland_in_lava:

VLANd support in LAVA test jobs
###############################

What is a VLAN?
***************

In terms of VLANd and the LAVA support based upon it, a VLAN is a way to provide isolation of various network ports
across switches - similar to changing the connections to provide a private network. e.g. we want to be able to connect
switch 3/port 7 & switch 1/port 6 to make one VLAN, then repeat for more arbitrary selections of switch and port. Once
the VLAN is created, the interfaces connected to the switch/port will only be able to access addresses within that VLAN.

.. _vlan_support:

VLANd and LAVA
**************

VLANd provides a simple utility to control switches on a single site, single network basis. The LAVA
integration is implemented as one of the :ref:`protocols` supported by the :term:`refactoring`. As such,
the LAVA integration inherits the restrictions of the original design of :term:`VLANd`.

Unlike the :ref:`multinode_protocol`, the ``lava-vland`` protocol has only a minimal API for use during the
test shell, providing static information about the network interfaces on the device. The :ref:`multinode_api`
is also available, as with all other multinode jobs.

VLANd test shell helpers
========================

lava-vland-self
---------------

Prints details of the ``sysfs`` path, mac address and admin-assigned interface name for each interface on this
device::

 /sys/devices/platform/ocp/47400000.usb/47401c00.usb/musb-hdrc.1.auto/usb1/1-1/1-1:1.0/net/eth1
 00:e0:4c:53:44:58
 iface1
 /sys/devices/platform/ocp/4a100000.ethernet/net/eth0
 90:59:af:5e:69:fd
 iface0

lava-vland-tags
---------------

Prints details of the :ref:`vland_interfaces`::

 iface1
 100M
 iface0
 1G
 iface0
 100M

.. _vland_restrictions:

VLANd Restrictions
==================

The design of VLANd set out some clear constraints on the support to be created:

* 1 **access** port on 1 switch being on 1 VLAN, no more, no less.

  * aka a port-based or static or manually-created VLAN (depending on which vendor’s docs you read!).

* No support for dynamic VLANs

  * (switch calling out to external services to determine which VLAN a newly-detected connection should be connected to)

* No support for filtering on ports to set up VLANs by traffic analysis etc.
* No support for egress/ingress control such that a port may interact with ports outside of its own defined VLAN.
* No support for cross-site VLANs via QinQ or similar.
* Ports defined in terms of the switch/port combination.
* Some switch/port combinations are to be **locked** so that test jobs cannot put infrastructure devices into a test VLAN.

.. _vland_design:

VLANd Design goals and considerations
=====================================

* Set up arbitrary sets of VLANs
* Map interfaces to switch ports in the LAVA device instance configuration.
* Run a single VLAN daemon instance per lab
* Switches are identified by IP or hostname - DNS must work for names to be used
* Support a regular background read-only check that the switch config is reflected in the DB

.. _lava_vland_devices:

LAVA and VLANd Device considerations
====================================

.. _vland_multiple_interfaces:

Requirement for multiple interfaces
-----------------------------------

Initial support for VLANd in LAVA sets up the VLANs at the start of the job. Many test jobs will require the
device to download artifacts from the dispatcher (which itself has downloaded from third party sites) using
protocols like TFTP. The device therefore needs to be able to reach the dispatcher over the network and this
has implications for which devices are usable with VLANd at this stage.

Devices to be used with VLANd **must** have multiple network interfaces. It is **not** required that
all interfaces are enabled at boot, simply that the boot process has a usable network interface. It is up to the
test job writer whether the other interface(s) are enabled at boot or enabled/disabled during the test job - VLANd
has no requirement other than that the physical hardware has a cable attached to the specified switch/port.

Future changes are expected to allow for devices with only a single interface to use VLANd but this requires code
changes to support setting up the VLAN after the device has downloaded files using TFTP but before the serial
connection is used to run the boot commands. This could result in a test job where the device has no access to
the internet or the dispatcher during the rest of the test job. LAVA continues to control the physical device
using the serial connection, including to implement the :ref:`multinode_api` but some test jobs may use dynamic
connections made from the dispatcher - such test jobs would not be able to use VLANd on devices with only a single
network interface.

.. _vland_locking:

LAVA and locked switch/port combinations
----------------------------------------

VLANd supports locking particular switch/port combinations to prevent test jobs interfering with critical
lab infrastructure (like a PDU or the dispatcher itself). The dispatcher is serving many jobs
simultaneously, so cannot be part of any VLAN created by a test job.

The ``lava-vland`` protocol will **not** be allowed to modify locked switch/port combinations or to lock switch/port
combinations used within the test job. LAVA will control the raising and tear down of VLANs using the ``lava-vland``
protocol, so that each test job gets access only to the VLANs that the test job itself defines.

.. _vland_multinode:

VLANd and Multinode
===================

* VLANd is restricted to a single mapping of a switch and port to a single interface on a device
* A VLAN which only ever contains a single device is not typically a useful test of the networking
  support on that device.
* The multinode :term:`role` determines which devices go onto which named VLAN.

So the ``lava-vland`` protocol is directly tied to the ``lava-multinode`` protocol, with one additional
restriction:

* Any :term:`role` used by ``lava-vland`` **must only** set a count of **one**. There is no limit to the
  number of roles as long as each is unique across the multinode job.

.. _lava_vlan_database:

LAVA VLANd database support
***************************

Details of which interface of which board is on which port of which switch is collectively called the
:ref:`network map <vland_network_map>` which is maintained by the lab admins. See :ref:`admin_vland_lava`.

Test writers get to see which :term:`types of device <device type>` support which interfaces and which
:term:`vland_device_tags`, together with :term:`device tags <device tag>`. This allows test writers to
specify which devices are used for a particular test, without being tied to a set of device hostnames
that may change from time to time. LAVA then maps the test writer request to a specific device,
interface and switch/port combination and constructs the commands to pass to :term:`VLANd`.

Test writers do not provide explicit switch/port instructions; the test job simply defines the type of device to
use, the interfaces to use and any device tags required. LAVA then assembles this into a series of instructions
to VLANd. This allows test jobs to be re-used without regard to whether the lab admins have had to change the
physical topology of the network, as long as the same services remain available.

.. _vland_interfaces:

Interfaces and link speeds
==========================

Test writers provide information about the device interfaces using the **lava-vland** protocol syntax which matches
a :term:`role` with a name for a VLAN and a list of tags (which may be loosely related to link speeds) which that
role needs to be able to provide. **All** of the specified tags must be supported by the interface before the
device will be accepted as suitable for the test job.

Devices may also have requirements that booting can only use certain interfaces (which may be considered as
*primary*), e.g. bootloaders may lack the ability to detect and/or use a network interface which uses a USB
network converter when a physical ethernet port is also fitted. If the primary ethernet port is put onto a
VLAN, the bootloader may be unable to raise a network interface. See :ref:`identify_primary_interfaces` and
check with your local admins about how such issues may be identified and avoided, e.g. by not specifying
tags for *primary* interfaces.

.. _vland_device_tags:

VLANd and interface tags in LAVA
--------------------------------

LAVA can use interface tags to distinguish between devices of the same :term:`device type`.
Commonly, the values in the tags might relate to useful features of an interface: the link
speeds it supports, the interface types it supports (RJ43, SFP) or other things like its
manufacturer. The tags that can be used are entirely arbitrary: LAVA itself attaches no
particular meaning to the tags. When selecting devices for a test job, a device is assigned
if the device dictionary tags match or exceed the requested tags in the job definition.

Therefore, if tags are to be expressed as link speeds, all link speeds
must be included in the device dictionary, using whatever notation is agreed
between the admins and the test writers. A 10G link which is also capable of
1G needs to be expressed as ``['1G', '10G']`` (ordering is irrelevant). A device
with such an interface can then be assigned a testjob requiring a
10G link or a testjob requiring a 1G link.

The syntax of the interface tag is arbitrary - individual labs can choose to
extend the tag to embed more information than the link speed or use a different
pattern of their own choice.

This is in line with how a :term:`device tag` is used elsewhere in LAVA,
it is the use of such a tag in the device dictionary which is custom to
VLANd.

The list of vland-type tags available for a device will be declared on
the server page for that device but in a different section from other tags.


.. _vland_vlan_name:

Assigning roles to a VLAN
=========================

The name for the VLAN, as specified by the test writer, is an arbitrary label - the actual name used by VLANd will be
calculated by LAVA based on the test job ID and the multinode target group ID. In a similar way to a role, the name
is used to associate different roles onto the same VLAN.

.. _example_vland_protocol:

Example vland protocol YAML
===========================

All uses of the **lava-vland** protocol also require the :ref:`multinode_protocol`, this example just looks
at the vland component.

.. code-block:: yaml

  lava-vland:
    client:
      vlan_one:
        - 10G
    server:
      vlan_one:
        - 1G

Any one role can be put onto multiple vlans. Managing the routing and specifying which
interface is up or down at any particular point of a test job is entirely within the
remit of the test writer:

.. code-block:: yaml

  lava-vland:
    master:
      vlan_one:
        - 10G
      vlan_two:
        - 1G
    slave:
      vlan_one:
        - 1G
    soldier:
      vlan_two:
        - 1G

.. _example_test_yaml:

Example YAML for the protocols
==============================

Combining the ``lava-vland`` protocol with the ``lava-multinode`` protocol shows how the roles match up.

.. note:: :ref:`vland_multinode` support dictates that the ``count`` for roles which are used by
   ``lava-vland`` can only ever be **1**.

This example will create a single VLAN which the test writer will be able to see as **vlan_one** and this
VLAN will contain a single beaglebone-black and a single cubietruck. The beaglebone-black is required to
provide at least one interface capable of a 10G link speed (so this example is unlikely to ever find a
suitable device) and the cubietruck is required to provide an interface capable of 1G. (The actual meaning of
the interface tags is up to the lab admins but it is expected that most admins will use the established convention
of G === gigabit per second.) In addition, this example stipulates that the beaglebone-black is to support a
:term:`device tag` called ``usb-eth`` and the cubietruck is to support a device tag called ``sata``. Depending on
the setup of the lab, these tags can be used to indicate that the beaglebone-black has a USB ethernet converter
as well as the on-board physical ethernet support and that the cubietruck has an accessible SATA drive.

.. code-block:: yaml

 protocols:
   lava-multinode:
     roles:
       client:
         device_type: bbb
         count: 1
         tags:
         - usb-eth
       server:
          device_type: cubietruck
         count: 1
         tags:
         - sata
     timeout:
       seconds: 60
   lava-vland:
     client:
       vlan_one:
         - 10G
     server:
       vlan_one:
         - 1G
