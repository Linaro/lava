.. _distributed_deployment:

Deploying Distributed Instances
###############################

When deploying a large LAVA "lab" instance with many :term:`DUT` it is
suggested to use :ref:`remote_worker` nodes.

.. _remote_worker:

Remote Worker
=============

A remote worker node is a reconfigured installation of ``lava-server``
that is capable of running test jobs and submitting the results back to
the master ``lava_server``. In a lab environment, you will likely have
too many test devices for a single server to handle, so a worker-node
can be used to spread the load. For example, a single LAVA server may
struggle to cope with multiple high-IO process while dispatching images
to a :term:`DUT`

Configuring Master server for remote workers
--------------------------------------------

When installing LAVA on a Debian based distribution, ``debconf`` will
ask if this installation is a single instance or a remote instance. Other
distributions will have different ways of configuring ``lava-server``.

Configuring remote worker
-------------------------

LAVA servers need to have an instance name. Each remote
worker must be given the instance name of the master
lava-server which it will poll for new jobs to run
on the devices attached to the worker.

A remote worker needs to know the network address of the Master
``lava_server``. This can be set with ``LAVA_MASTER``.
``LAVA_DB_PASSWORD`` can be used if you wish to preset the database
password, otherwise you will be asked in the prompt.

SSHFS mount operations
----------------------

``lava-server`` provides a script to manage the mounting of the media
directory over sshfs. On Debian-based distributions, this script
remounts the directory each time the ``lava-server`` package is
installed or reconfigured.

An SSH key will have been generated during the configuration of the
``lava-server`` package. The public part of this key '''must''' be
appended to the ``authorized_keys`` file on the master for the SSHFS
mount operation to work::

 sudo -u lavaserver cat /var/lib/lava-server/home/.ssh/id_rsa.pub 

Now enter this public key into the file on the server::

 sudo -u lavaserver vim /var/lib/lava-server/home/.ssh/authorized_keys

The SSHFS mount should then be visible on the worker::

 $ mount | grep lavaserver
 lavaserver@192.168.100.235:/var/lib/lava-server//default/media on 
 /var/lib/lava-server/default/media type fuse.sshfs 
 (rw,nosuid,nodev,relatime,user_id=110,group_id=115,allow_other)

Remote databases
----------------

Configuring database access from remote workers
-----------------------------------------------

Currently, remote workers need to be able to access the master database,
so postgres has to be manually configured to allow access from external
clients over the network.

.. note:: The communication between the remote worker and the master
          is likely to be re-designed and this step may become unnecessary
          in future. This section will be updated at that time.

The ``lava-server`` installation does not dictate how the remote database
connection is configured but an (overly permissive) example would be to
adjust the ``listen_addresses`` in ``postgresql.conf``::

 listen_addresses = '*'

Also adjust the host allowed to connect to this database::

 ALLOW="host    all    all    0.0.0.0/0    trust"

In most cases, the administrator for the machine providing the database
will want to constrain these settings to particular addresses and/or
network masks. LAVA just needs each remote worker to be in the list of
trusted connections and for the database to be listening to it.

``lava-server`` remoteworker installations assume the DB resides on the
LAVA_MASTER and remote worker installations will prompt to set up your
instance using a database on LAVA_MASTER.

.. note:: A remote postgres database only works with remote workers,
         the master install will still install a postgres server as
         part of the setup task. If you are using a remote database,
         the master instance will need to be configured separately.

``LAVA_MASTER`` is still needed to support sshfs connections for results.

Heartbeat
---------

Each dispatcher worker node sends heartbeat data to the master node
via xmlrpc. For this feature to work correctly the ``rpc2_url``
parameter should be set properly. Login as an admin user and go to
``http://localhost/admin/lava_scheduler_app/worker/``.  Click on the
machine which is your master and in the page that opens, set the
``Master RPC2 URL:`` with the correct value, if it is not set properly,
already. Do not touch any other values in this page except the
description, since all the other fields except description is populated
automatically. The following figure illustrates this:

.. image:: ./images/lava-worker-rpc2-url.png

Frequently encountered problems
-------------------------------

Make sure that your database connectivity is configured correctly in::

 /etc/lava-server/instance.conf

and your LAVA_SERVER_IP (worker ip address) is configured correctly in::

 /etc/lava-server/instance.conf
 /etc/lava-dispatcher/lava-dispatcher.conf

A :ref:`remote_worker` has configuration in::

 /etc/lava-server/worker.conf

Postgres on the master server is running on the default port 5432 (or
whatever port you have configured)

SSHFS on the worker has successfully mounted from the master. Check
`mount` and `dmesg` outputs for help.

Considerations for Geographically separate Master/Worker setups
===============================================================

A :ref:`remote_worker` needs to be able to communicate with the
``lava_server`` over SSH and Postgres (standard ports 22 and 5432)
so some configuration will be needed if the ``lava-server``
is behind a firewall.

* The :term:`DUT` console output logs are written to a filesystem that
  is shared over SSHFS from the master ``lava-server``. A side-effect
  of this is that over high latency links there can be a delay in seeing
  console output when viewing it on the scheduler job webpage. SSHFS can
  recover from network problems but a monitoring system to check the mount
  is still available is preferred.
* Latency over SSHFS
* Log file update speed
* Port forwarding behind firewalls

Scaling Deployments
===================

How many boards can a server "dispatch"?
  Some jobs require some heavy IO while LAVA reconfigures an image or
  compresses/decompresses. This blocks one processor.

Considerations of serial connections
====================================

* Modern server or desktop x86 hardware will often have no, or very
  few, serial ports, but :term:`DUT` are still often controlled by LAVA
  over serial. The 2 solutions we use for this in the LAVA lab are
  dedicated serial console servers or usb-to-serial adaptors. If you
  plan to use many usb-to-serial adaptors, ensure that your USB hub
  has an external power source. For ease of udev configuration, use a
  usb-to-serial chipset that supports unique serial numbers, such as
  FTDI.
* In a large deployment in server racks, rackmounted serial hardware
  is available. Avocent offer Cyclades serial console servers which
  work well however the cost can be high. An alternative is a 16 port
  rackmount USB serial adapters, available from companies such as
  StarTech. Combined with :ref:`ser2net`, we have found these to be
  very reliable.


Other Issues to consider
========================

Network switch bandwidth
  There will be huge data transfers happening between the dispatcher
  worker and the master, also between the devices attached to the
  dispatcher worker. In such a case careful thought must be given in
  placing and commissioning a network switch, in order to handle this
  huge bandwidth transfer.

Proxy server
  Since all the devices loads images from the URL given in the job
  file, it is a good idea to have a proxy server installed and route
  the download traffic via this proxy server, which prevents image
  downloads directly and saves bandwidth. The proxy server can be set
  for the dispatcher during installation via lava deployment tool or
  by editing the value of ``LAVA_PROXY`` in
  ``/etc/lava-server/instance.conf``.
