.. index:: admin deploy lxc

.. _lxc_deploy:

Deploying LXC devices
=====================

LXC is a userspace interface for the Linux kernel containment features. Through
a powerful API and simple tools, it lets Linux users easily create and manage
system or application containers. LXC devices can run lava tests within a
container without disturbing the dispatcher host. The prime advantage of having
LXC device in LAVA is the ability to provide a transparent, sandboxed
environment with support for different OS types, enabling testing in different
platforms.

Prerequisite
------------

Ensure that LXC is installed in your LAVA dispatcher host, if not use the
following command to install LXC in Debian::

  $ sudo apt install lxc

Refer the following links in order to setup networking for LXC in Debian:

* Network setup - https://wiki.debian.org/LXC#network_setup
* Simple Bridge - https://wiki.debian.org/LXC/SimpleBridge
* Masqueraded Bridge - https://wiki.debian.org/LXC/MasqueradedBridge
* VLAN Networking - https://wiki.debian.org/LXC/VlanNetworking
* libvirt - https://wiki.debian.org/LXC/LibVirtDefaultNetwork

Android testing with LXC support
--------------------------------

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

 {% set device_info = [{'board_id': '0123456789', 'usb_vendor_id': '0451', 'usb_vendor_id': 'd109'}] %}

Example 4 - A device and optional additional hardware ::

 {% set device_info = [{'board_id': '0123456789'}, {'board_id': 'adsd0978775'}, {'board_id': '45645629342'}] %}

.. note:: Do not run `adb daemon` on the dispatcher host, which will grab the
          :term:`DUT` and will hinder exposing it to LXC. Similarly, remove
          `fastboot` packages from the dispatcher host.

.. include:: examples/device-configurations/hi6220-hikey.yaml
   :code: yaml

Configuration: Persistent Containers
------------------------------------
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

Once the `lxc_path` key is set in dispatch configuration, both persistent and
non-persistent containers will get created in this path.

.. note:: LAVA does not have a mechanism to limit the amount of disk space such
          persistent containers could use. Hence, administrators should setup
          some kind of external monitoring in order to watch the size of these
          persistent containers and free space whenever required or destroy
          unused persistent containers.

Configuration: Unprivileged containers as root
----------------------------------------------

This is the recommended configuration for running your LXC devices within a
LAVA dispatcher. In this configuration the containers will run as unprivileged
user started by root user.

Allocate additional uids and gids to root::

  $ sudo usermod --add-subuids 100000-165536 root
  $ sudo usermod --add-subgids 100000-165536 root

Then edit ``/etc/lxc/default.conf`` and append lxc.uidmap entry like below::

  lxc.id_map = u 0 100000 65536
  lxc.id_map = g 0 100000 65536

With the above in place any container created as root will be an unprivileged
container.

.. note:: To apply configurations system wide for all LXC devices attached to
  the dispatcher use ``/etc/lxc/default.conf`` file.

Other resources
---------------

For advanced LXC configurations and usage refer the following links:

* https://wiki.debian.org/LXC
* https://linuxcontainers.org/lxc/getting-started/
* https://help.ubuntu.com/lts/serverguide/lxc.html
* https://www.stgraber.org/2013/12/20/lxc-1-0-blog-post-series/
* https://www.stylesen.org/access_android_devices_lxc
* https://www.stylesen.org/run_android_cts_within_lxc
