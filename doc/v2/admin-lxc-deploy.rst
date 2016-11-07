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
takes a special parameter called `device_path` with which the usb path of the
:term:`DUT` is exposed to LXC for Android testing. The `device_path` takes a
list of paths (the path can be a symlink) which will get exposed to LXC.

.. include:: examples/device-configurations/hi6220-hikey.yaml
   :code: yaml

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
