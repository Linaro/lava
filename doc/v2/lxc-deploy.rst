.. _lxc_deploy:

Deploying LXC devices
=====================

LXC is a userspace interface for the Linux kernel containment
features. Through a powerful API and simple tools, it lets Linux users
easily create and manage system or application containers. LXC devices
can run lava tests within a container without disturbing the
dispatcher host. The prime advantage of having LXC device in LAVA is
the ability to support different OS types, enabling testing in
different platforms.

Prerequisite
------------
Ensure that LXC is installed in your LAVA dispatcher host, if not use
the following command to install LXC in Debian / Ubuntu::

  $ sudo apt install lxc

For enabling networking bridge-utils should be installed as follows::

  $ sudo apt install bridge-utils

Refer https://wiki.debian.org/LXC/SimpleBridge to enable networking
for LXC devices.

Adding a LXC device to LAVA
---------------------------

You can use the :ref:`admin_helpers` support::

 $ sudo /usr/share/lava-server/add_device.py lxc lxc01

Configuration: Unprivileged containers as root
----------------------------------------------

This is the recommended configuration for running your LXC devices
within a LAVA dispatcher. In this configuration the containers will
run as unprivileged user started by root user.

Allocate additional uids and gids to root::

  $ sudo usermod --add-subuids 100000-165536 root
  $ sudo usermod --add-subgids 100000-165536 root

Then edit /etc/lxc/default.conf and append lxc.uidmap entry like
below::

  lxc.id_map = u 0 100000 65536
  lxc.id_map = g 0 100000 65536

With the above in place any container created as root will be an
unprivileged container.

.. note:: To apply configurations system wide for all LXC devices
          attached to the dispatcher use `/etc/lxc/default.conf`
          file.

Other resources
---------------
For advanced LXC configurations refer the following links:

* https://linuxcontainers.org/lxc/getting-started/
* https://help.ubuntu.com/lts/serverguide/lxc.html
* https://www.stgraber.org/2013/12/20/lxc-1-0-blog-post-series/

Sample job definitions:

https://git.linaro.org/people/senthil.kumaran/job-definitions.git/tree/0d1a8644ca0e53b28a0bc2a37de9b8d2f13116b5:/lxc
