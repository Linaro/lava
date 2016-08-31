.. index:: vland

.. _admin_vland_lava:

Administering VLANd support in LAVA
###################################

Mandatory Constraints
*********************

VLANd is a daemon to support virtual local area networks. It can be used alone
and can also be used within LAVA. VLANd is a specialised tool and the LAVA
support cannot and will not protect against misconfiguration causing the
network to become unusable. Admins require careful consideration of the risks
and time to manually prepare a configuration map of the entire LAVA instance,
including the physical layout of the switches, all cables connected to all of
those switches and all the devices of that instance (not just test devices).
These constraints **must all be met** and can be summarised as:

* :ref:`single_set_switches`
* :ref:`vland_switch_support`
* :ref:`network_topology_map`
* :ref:`identify_primary_interfaces`
* :ref:`vland_recommends`

.. _single_set_switches:

Single set of switches
======================

All devices and all dispatchers must be on a single set of physical switches.
These virtual networks are **local**, no other topology is supported.

.. _vland_switch_support:

Switches must have drivers in vland
===================================

Switches which are expected to support a VLAN must have driver
support in `VLANd <https://git.linaro.org/lava/vland.git>`_.

.. index:: network map

.. _network_topology_map:

Accurate map of network topology
================================

The physical topology of the LAN needs to be manually mapped and translated
into the :term:`device dictionary` of the LAVA instance. This information must
be **maintained and updated manually** whenever the network topology is
changed.

The map must be complete and cover the identity of the switches and all the
port number(s) for all connections to those switches. It is **strongly**
recommended that administrators use the VLANd administration interface to
**lock** ports for devices that are not expected to be controlled in LAVA
tests, such as PDUs and the dispatcher itself. This will ensure that mistakes
in test configuration cannot alter connections to those devices which might
break the network.

The network map consists of:

* The **identity of the switch and the port** to which each interface of each
  device under test is connected.

* The **MAC address and full sysfs path** of the network interface of each
  supported device. The ``/sys/`` path should **not** include the current
  interface name (``eth0`` etc.) as this can be changed with a different
  userspace. e.g. ::

   /sys/devices/platform/ocp/4a100000.ethernet/net/

* The list of unique **interface names**  for network interfaces on the device.
  This *may* be something like eth0, eth1, etc., but the names used here will
  **not** necessarily match up with the names that show up when the device is
  actually running due to ordering issues when Linux boots. To remove any
  possible confusion here, it is therefore recommended to **not** use the
  eth0/eth1 names here.

* The **interface tags** to describe each interface of each device. See
  :ref:`vland_device_tags`. These tags will be useful information for test
  writers to know, and will be used when selecting devices and interfaces to
  match test definitions. Useful properties to list here may include things
  like supported link speeds (100M, 1G, 10G etc.), device manufacturer (Intel,
  Realtek, etc.), physical interface type (RJ45, SFP, etc.) - whatever test
  writers are going to care about.

.. _identify_primary_interfaces:

Identification of primary interfaces
====================================

Devices may have requirements that booting can only use certain interfaces
(which may be considered as *primary*), e.g. bootloaders may lack the ability
to detect and/or use a network interface which uses a USB network converter
when a physical ethernet port is also fitted. If the physical ethernet port is
put onto a VLAN, the bootloader may be unable to raise a network interface.
Test writers need to be able to know which interfaces should be typically be
avoided and lab admins can choose different methods for this support. See
:ref:`vland_device_tags`.

* Not specifying tags for **primary** interfaces or

* Specifying only a **special** tag which test writers should normally avoid
  using.

The method chosen needs to fit with the :ref:`network_topology_map` and the
particular use cases within each lab and LAN. See also
:ref:`vland_multiple_interfaces`.

.. _vland_recommends:

Additional advice
=================

In addition, the following advice is strongly recommended:

* Admins should keep the device dictionary data in VCS and keep those copies
  synchronised with the database.

* Admins need to use the XML-RPC support to periodically **verify** that all
  the devices have the correct configuration.

* Admins need to ensure that any locked ports are re-established should there
  be a power outage, maintenance window or other cause of switches being reset
  or reconfigured.

* Admins need to record the interfaces which may be considered **primary** for
  each device. See :ref:`identify_primary_interfaces`.

These items are an extension of the admin requirements for PDU ports and
connection commands and are to be considered in the same way. Any time that any
cables are moved around in the physical world, there will need to be a software
change, preferably in VCS and also in the database of the LAVA instance.

Example device dictionary
*************************

This example uses a non-existent ``vland.yaml`` template and imaginary sysfs
locations. Real datasets must extend a known template, typically the device
type template which itself extends the base template.

.. code-block:: jinja

    {% extends 'vland.yaml' %}
    {% set interfaces = ['iface0', 'iface1'] %}
    {% set sysfs = {
    'iface0': "/sys/devices/pci0000:00/0000:00:19.0/net/",
    'iface1': "/sys/devices/pci0000:00/0000:00:1c.1/0000:03:00.0/net/"} %}
    {% set mac_addr = {'iface0': "f0:de:f1:46:8c:21", 'iface1': "00:24:d7:9b:c0:8c"} %}
    {% set tags = {'iface0': ['1G', '10G'], 'iface1': ['1G']} %}
    {% set map = {'iface0': {'switch2': 5}, 'iface1': {'switch1': 7}} %}

This dictionary defines two interfaces belonging to the relevant device. It
uses python syntax to **map** each of those interfaces to values which need to
be extracted from the device itself:

* **sysfs**: the full path in ``/sys`` to the device providing the interface.

* **mac_addr**: the MAC address of each interface - if the device is incapable
  of retaining the same MAC address across power resets, the test writer will
  need to use the ``sysfs`` information to work out which interface is which.

* **tags**: tags are used to select which devices of a particular :term:`device
  type` can be assigned to the LAVA job. Although the link speed is the most
  common value to be used, it could also be anything else which differs between
  otherwise similar devices. See :ref:`vland_device_tags`. Tags are expressed
  as a python dictionary of python lists.

* **map**: the switch and port map - the IP address or hostname of the switch
  and the port on that switch from which there is a direct cable to the
  physical port declared in the ``sysfs`` entry.

.. _vland_network_map:

Viewing the network map
=======================

Device information can be viewed using ``XML-RPC`` using the
``system.pipeline_network_map`` request. The function collates all the vland
information from pipeline devices to create a complete map, then return YAML
data for all switches or a specified switch.

.. code-block:: yaml

    switches:
      '192.168.0.2':
      - port: 5
        device:
          interface: iface0
          sysfs: "/sys/devices/pci0000:00/0000:00:19.0/net/"
          mac: "f0:de:f1:46:8c:21"
          hostname: bbb1
