.. index:: admin deploy lxc, device_info - lxc, lxc - admin

.. _lxc_deploy:

Deploying LXC devices
#####################

LXC is a userspace interface for the Linux kernel containment features. Through
a powerful API and simple tools, it lets Linux users easily create and manage
system or application containers. LXC devices can run lava tests within a
container without disturbing the dispatcher host. The prime advantage of having
LXC device in LAVA is the ability to provide a transparent, sandboxed
environment with support for different OS types, enabling testing in different
platforms.

Prerequisite
************

Ensure that LXC is installed in your LAVA dispatcher host, if not use the
following command to install LXC in Debian::

  $ sudo apt install lxc

Refer the following links in order to setup networking for LXC in Debian:

* Network setup - https://wiki.debian.org/LXC#network_setup
* Simple Bridge - https://wiki.debian.org/LXC/SimpleBridge
* Masqueraded Bridge - https://wiki.debian.org/LXC/MasqueradedBridge
* VLAN Networking - https://wiki.debian.org/LXC/VlanNetworking
* libvirt - https://wiki.debian.org/LXC/LibVirtDefaultNetwork

.. _add_android_devices_lxc:

Android testing with LXC support
********************************

:ref:`LXC protocol <lxc_protocol_reference>` is used for Android testing
use-cases which removes the need for writing complex job definitions using
:ref:`Multinode <multinode>`. This is made possible by adding the usb path of
the :term:`DUT` that is attached to the dispatcher. The device configuration
takes a special parameter called `device_info` which will be used to expose the
:term:`DUT` to LXC for Android testing. The `device_info` takes a list of
dictionaries, where each dictionary value can contain keys such as `board_id`,
`usb_vendor_id`, `usb_product_id`.

Examples of `device_info` configuration are as follows.

Example 1 - Single device with just `board_id` ::

 {% set device_info = [{'board_id': '0123456789'}] %}

Example 2 - Single device with `board_id` and `usb_vendor_id` ::

 {% set device_info = [{'board_id': '0123456789', 'usb_vendor_id': '0451'}] %}

Example 3 - Single device with `board_id`, `usb_vendor_id` and `usb_product_id` ::

 {% set device_info = [{'board_id': '0123456789', 'usb_vendor_id': '0451', 'usb_product_id': 'd109'}] %}

.. note:: Do not run `adb daemon` on the dispatcher host, which will grab the
          :term:`DUT` and will hinder exposing it to LXC. Similarly, remove
          `fastboot` packages from the dispatcher host.

.. include:: examples/device-configurations/hi6220-hikey.yaml
   :code: yaml

.. index:: static_info devices

.. _add_usb_devices_lxc:

Arbitrary external devices needing LXC support
**********************************************

Some test devices have attached hardware which needs to be visible from the LXC
during the time that the test job is running.

* If the attached device re-enumerates on the worker each time that the
  :term:`DUT` is rebooted then ``device_info`` can be used.

* More commonly, the attached device is independent of the :term:`DUT` and
  is accessible to the worker even when the DUT is powered off. These attached
  devices need to use ``static_info``.

  * Static USB devices (using ``board_id``, ``usb_vendor_id`` or
    ``usb_product_id``) will be added to the LXC at the start of the test job,
    including associated ``/dev/`` nodes like ``/dev/tty*`` or
    ``/dev/serial/by-id/`` etc. Test writers will need to locate the correct
    device by inspecting paths like ``/dev/serial/by-id/``.

  * Other static devices which are accessible over the network can be made
    available to a test shell in the LXC through lava test shell helpers.

.. seealso:: :ref:`device_dictionary_commands`

One example is an energy probe, which may be measuring a single DUT whilst
being connected to the worker as a USB or network device.

For a USB probe, the ``id`` of that USB device needs to be in the
``static_info`` of the DUT so that the test shell running in the LXC can
control the probe.

For a network attached probe, the IP address of the probe and the channel which
the probe uses for this specific DUT need to be in the ``static_info``.

USB attached devices
====================

The value for ``board_id`` in the ``static_info`` is what shows up in
``pyudev`` bindings as the ``ID_SERIAL_SHORT``. This is typically the
``SerialNumber`` reported by ``dmesg`` but it is worth checking as the precise
syntax does matter and can differ between ``pyudev`` and ``dmesg``:

.. code-block:: python

  >>> import pyudev
  >>> context = pyudev.Context()
  >>> [ device.get('ID_SERIAL_SHORT') for device in context.list_devices(subsystem='usb')]
  [u'0000:00:1a.0', None, None, None, None, u'889FFAE94013', None, None, None, None,
  None, u'FTGNRL22', None, None, None, u'S_NO62200001', None, None, None, None,
  None, None, None, None, None, u'0000:00:1d.0', None, None, None]
  >>>

For ``usb_vendor_id``, the corresponding pyudev key is ``ID_VENDOR_ID``.
For ``usb_product_id``, the corresponding pyudev key is ``ID_MODEL_ID``.

The keys given in the dictionary are **not** arbitrary and follow the same
rules as for :ref:`Android devices <add_android_devices_lxc>`::

 [{'board_id': 'S_NO62200001'}]

.. caution:: Ensure that the ``static_info`` relates to a USB device which is
   attached to the same worker as the DUT but is **not** a DUT itself.

If using multiple keys for the same ``device_info``, ensure that the key value
pairs are in a single dictionary within the list of dictionaries::

 {% set static_info = [{'board_id': '0123456789'}, {'board_id': 'adsd0978775', 'usb_vendor_id': 'ACME54321'}] %}

.. note:: Devices which include a forward slash ``/`` in the serial number will have
   that replaced by an underscore when processed through ``pyudev``. e.g.::

    udev: ATTRS{serial}=="S/NO44440001"
    pydev: S_NO44440001
    static_info: {% set static_info = [{'board_id': 'S_NO44440001'}] %}

.. note:: LAVA instances running systemd newer than build 232 (e.g.
   Buster) need to allow scripts called by ``udev`` rules to access the
   network to get proper logging of the addition of dynamic USB devices
   to the LXC. LAVA achieves this by providing an override file for the
   ``systemd-udev.service` in
   ``/etc/systemd/system/systemd-udevd.service.d/override.conf``. The
   actual network change is not visible in the systemd show support for
   the udev service, so the override also updates the unit description
   to make it obvious. When this override is in effect, you will be
   able to see the change::

    $ sudo systemctl status udev
    systemd-udevd.service - udev Kernel Device Manager (LAVA)
    Loaded: loaded (/lib/systemd/system/systemd-udevd.service; static; vendor preset: enabled)
    Drop-In: /etc/systemd/system/systemd-udevd.service.d
             -override.conf

Other related devices
=====================

Devices which are not directly attached to the worker can also be supported,
for example energy probes which communicate over the network::

 {% set static_info = [{'probe_ip': '192.168.0.23', 'probe_channel': '4'}] %}

* **probe_ip** - The IP address at which the energy probe is accessible from
  the LXC.

* **probe_channel**  - Energy probes can often measure multiple devices at once,
  so the device dictionary needs to specify the channel so that the test job
  can know what channel refers to this LAVA device.

These values can be retrieved by test writers inside a LAVA test shell in the
LXC by using the associated test shell helpers.

* **lava-probe-ip** - echoes the ``probe_ip`` specified in the device
  dictionary.

* **lava-probe-channel** - echoes the ``probe_channel`` specified in the device
  dictionary.

  .. seealso:: https://github.com/ARM-software/lisa/wiki/Energy-Meters-Requirements#user-content-iiocapture---baylibre-acme-cape

Configuration
*************

Persistent Containers
=====================

A test job can request a persistent container which will not get destroyed after
the test job is complete. This allows the container to be reused for subsequent test
jobs. This is useful when users want to setup some software on a container and
use it for subsequent test jobs without re-creating the setup every time, which
may prove time consuming.

In such a case the admins can choose to switch the container creation path from
the default i.e., `/var/lib/lxc` to some other path, which could be a larger
partition mounted on the dispatcher to give more space for such persistent
container users. To set a different container creation path on a per dispatcher
basis `lxc_path` key is used in the dispatcher configuration as described in
:ref:`dispatcher_configuration`

Once the `lxc_path` key is set in dispatcher configuration, both persistent and
non-persistent containers will get created in this path.

.. note:: LAVA does not have a mechanism to limit the amount of disk space such
          persistent containers could use. Hence, administrators should setup
          some kind of external monitoring in order to watch the size of these
          persistent containers and free space whenever required or destroy
          unused persistent containers.

Unprivileged containers as root
===============================

This is the recommended configuration for running your LXC devices within a
LAVA dispatcher, provided your container does not access any devices attached
to the host. In this configuration the containers will run as unprivileged
user started by root user.

Allocate additional uids and gids to root::

  $ sudo usermod --add-subuids 100000-165536 root
  $ sudo usermod --add-subgids 100000-165536 root

Then edit ``/etc/lxc/default.conf`` and append lxc.uidmap entry like below::

  lxc.id_map = u 0 100000 65536
  lxc.id_map = g 0 100000 65536

With the above in place any container created as root will be an unprivileged
container.

.. warning:: Do not use unprivileged containers when your container has to
             interact with a :term:`DUT` that is attached to the host machine.

.. note:: To apply configurations system wide for all LXC devices attached to
  the dispatcher use ``/etc/lxc/default.conf`` file.

Other resources
***************

For advanced LXC configurations and usage refer the following links:

* https://wiki.debian.org/LXC
* https://linuxcontainers.org/lxc/getting-started/
* https://help.ubuntu.com/lts/serverguide/lxc.html
* https://stgraber.org/2013/12/20/lxc-1-0-blog-post-series/
* https://www.stylesen.org/access_android_devices_lxc
* https://www.stylesen.org/run_android_cts_within_lxc
