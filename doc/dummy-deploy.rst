Deploying dummy devices
=======================

Dummy devices are not proper devices, but rather interactive sessions in
existing machines. There are 3 types of dummy devices:

* ``dummy-schroot`` runs lava tests inside a schroot(1) session. You can
  configure the base chroot used, so for instance you can have different
  dummy devices for different OS types.

* ``dummy-ssh`` runs lava tests in a remote host using a ssh(1) connection.
  Interacts with the file system using sshfs(1) to mount the remote host
  root directory locally. You can configure which host to connect to, at
  which port, with which username to log in (although root is more or
  less mandatory due to the way the rest of dispatcher works), and which
  identity file (i.e. private key) to use for authentication. At least
  hostname and identity file must be provided in the configuration file.

* ``dummy-host`` runs lava tests on the actual host where the dispatcher
  is running. It should be unnecessary to say that having a device like
  this available to all users *is dangerous*, because **submitted test
  code (i.e.  arbitrary code) will be running on your LAVA server as
  root**. This device should never be used without proper access
  restrictions.

Configuration: dummy-schroot
----------------------------

Before anything, you will want to create one or more chroots to use with
``dummy-schroot`` devices. The Debian wiki contains instructions_ to get
started with schroot. After you create your chroot(s) you will want to
take note of their names.

.. _instructions: https://wiki.debian.org/Schroot

A ``dummy-schroot`` device has a single configuration variable:

* ``dummy_schroot_chroot`` indicates the name of the base chroot to be
  used. Default value: *default*.

Example configuration file (e.g. *schroot01.conf*)::

    device_type = dummy-schroot
    dummy_schroot_chroot = precise

Configuration: dummy-ssh
------------------------

``dummy-ssh`` has 4 configuration variables:

========================= ===================================== =============
Variable                  Description                           Default value
========================= ===================================== =============
dummy_ssh_host            Hostname to connect to                *None*
dummy_ssh_username        User name to login with               `root`
dummy_ssh_port            Port to connect to                    22
dummy_ssh_identity_file   SSH private key file to connect with  *None*
========================= ===================================== =============

**Note:** ``dummy_ssh_host`` and ``dummy_ssh_identity_file`` are mandatory
configuration variables.

Example configuration file (e.g. *ssh01.conf*)::

    device_type = dummy-ssh

    dummy_ssh_host = localhost
    dummy_ssh_port = 8022
    dummy_ssh_identity_file = /usr/share/vagrant/keys/vagrant


Configuration: dummy-host
-------------------------

This device type does not have any configuration variables, other than
specifying the device_type.

Example configuration file (*localhost.conf*)::

    device_type = dummy-host
