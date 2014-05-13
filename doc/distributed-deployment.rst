.. _distributed_deployment:

Deploying Distributed Instances
*******************************

When deploying a large LAVA "lab" instance with many :term:`DUT` it is
suggested to use one machine for the web frontend and the master
scheduler with separate machines to act as remote worker nodes.

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

.. note:: You will need various settings from the
          ``/etc/lava-server/instance.conf`` configuration file on
          the master when setting up the remote worker. It is useful
          to have an SSH login to the master and the worker. So ensure
          the master is installed before any of the workers.

Configuring remote worker
-------------------------

LAVA servers need to have an instance name. Each remote
worker must be given the instance name of the master
lava-server which it will poll for new jobs to run
on the devices attached to the worker.

A remote worker needs to know the network address of the Master
``lava_server``. This can be a hostname or an IP address.

The remote worker will also need these variables from the master:

* LAVA_DB_NAME - Name of the database on the master.
* LAVA_DB_USER - Username for the database on the master.
* LAVA_DB_PORT - Port number of the database on the master.
* LAVA_DB_PASSWORD - Password for the database on the master.

LAVA Coordinator configuration
------------------------------

Only one coordinator is used for each lab, so the remote worker needs
to know where to find this coordinator. Specify the hostname or IP
address of the master running the coordinator in the 
``/etc/lava-coordinator/lava-coordiantor.conf`` file on each **worker**::

 {
   "port": 3079,
   "blocksize": 4096,
   "poll_delay": 3,
   "coordinator_hostname": "192.168.100.5"
 }

If ``lava-coordinator`` is installed as a package on the worker, this
package can be removed. If the install was made without recommended
packages, simply create the directory and the file. This support is
due for an upstream fix.

SSHFS mount operations
----------------------

``lava-server`` provides a script to manage the mounting of the media
directory over sshfs. On Debian-based distributions, this script
remounts the directory each time the ``lava-server`` daemon is
restarted.

SSH key setup
^^^^^^^^^^^^^

An SSH key will have been generated during the configuration of the
``lava-server`` package. The public part of this key '''must''' be
appended to the ``authorized_keys`` file on the master for the SSHFS
mount operation to work::

 sudo -u lavaserver cat /var/lib/lava-server/home/.ssh/id_rsa.pub

Now enter this public key into the file on the server::

 sudo -u lavaserver vim /var/lib/lava-server/home/.ssh/authorized_keys

fuse configuration
^^^^^^^^^^^^^^^^^^

Edit ``/etc/fuse.conf`` on the worker and enable the ``user_allow_other``
option.

Additionally, you will need to ensure that the ``fuse`` (and ``loop``)
kernel modules are loaded. ``lava-dispatcher`` provides a file in
``/etc/modprobe.d/``. Check the output of ``lsmod`` on the worker
and uncomment the lines to add calls to install the relevant 
module **only** if that module does not load automatically.

.. note:: Enabling the fuse or loop modules unnecessarily can cause
          protracted complaints from the kernel and the fuse package
          support may fail to operate. This can show up as the ``fuse``
          package failing to install or upgrade, it will also prevent
          the worker from mounting the ssfs and jobs will likely fail
          to run on the remote worker.

Mounting the SSHFS
^^^^^^^^^^^^^^^^^^

LAVA will unmount and re-mount the ssfs each time the ``lava-server``
daemon is restarted.

The SSHFS mount should be visible on the worker::

 $ mount | grep lavaserver
 lavaserver@192.168.100.235:/var/lib/lava-server//default/media on
 /var/lib/lava-server/default/media type fuse.sshfs
 (rw,nosuid,nodev,relatime,user_id=110,group_id=115,allow_other)

.. _remote_database:

Remote databases
----------------

Configuring database access from remote workers
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

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

 host    all    all    0.0.0.0/0    trust

Now restart postgresql to pick up these changes::

 sudo service postgresql restart

If postgresql gives no errors on restart, restart lava-server on the
worker::

 sudo service lava-server restart

You can also check the connection directly on the worker, e.g. if the
IP address of the master running postgres is 192.168.100.175::

 $ psql -h 192.168.100.175 -U lavaserver

.. note:: In most cases, the administrator for the machine providing the
          database will want to constrain these settings to particular
          addresses and/or network masks. LAVA just needs each remote
          worker to be in the list of trusted connections and for the
          database to be listening to it. See the example 
          :ref:`example_postgres` for a more restrictive postgres
          configuration. In particular, the connection should use
          ``md5`` rather than ``password`` or ``trust``.

Check the /var/log/lava-server/lava-scheduler.log for cnnection errors of a
normal startup of lava-scheduler::

 2014-05-05 20:17:20,327 Running LAVA Daemon
 2014-05-05 20:17:20,345 lava-scheduler-daemon: /usr/bin/lava-server manage 
  --instance-template=/etc/lava-server/{{filename}}.conf 
  --instance=default scheduler --logfile /var/log/lava-server/lava-scheduler.log 
  --loglevel=info pid: 10036

Create a superuser
------------------

On the master, create a :ref:`create_superuser`, if this has not been
done already.

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

Sign in to the master django admin interface and scroll down in the
Admin home page to Lava_Scheduler_App and select Workers - ensure
that the XML_RPC URL is valid. e.g. you may need to put the IP
address of the <MASTER> in place of a local hostname as the worker
will need to be able to resolve this address.

If this is working, a second worker will appear on the scheduler
status page, Workers table::

 http://localhost/scheduler/#worker_

If this is not working, you will likely see this report in the
scheduler log: ``/var/log/lava-server/lava-scheduler.log``::

 [ERROR] [lava_scheduler_daemon.worker.Worker] Unable to update the Heartbeat, trying later

Example configuration
=====================

Assumptions
-----------

* Device is connected to a machine on ``192.168.1.228``
* Master is running on ``192.168.100.235``
* Worker is running on ``192.168.100.204``

Device configuration on worker
------------------------------

::

 connection_command = telnet 192.168.1.228 6000

.. _example_postgres:

Postgresql configuration
------------------------

::

 $ grep listen /etc/postgresql/9.3/main/postgresql.conf
 listen_addresses = 'localhost, 192.168.100.235'


::

 $ sudo tail /etc/postgresql/9.3/main/pg_hba.conf
 host   lavaserver   lavaserver   192.168.100.204/32    md5

Lava coordinator setup
----------------------

::

 {
   "port": 3079,
   "blocksize": 4096,
   "poll_delay": 3,
   "coordinator_hostname": "192.168.100.235"
 }


Frequently encountered problems
===============================

::

 Is the server running on host "<MASTER>" and accepting
 TCP/IP connections on port 5432?

This is a postgres configuration change. See :ref:`remote_database`.


Make sure that your database connectivity is configured correctly in::

 /etc/lava-server/instance.conf

and your LAVA_SERVER_IP (worker ip address) is configured correctly in::

 /etc/lava-server/instance.conf
 /etc/lava-dispatcher/lava-dispatcher.conf

If there are errors in the postgres connection settings in the ``instance.conf``
file, use ``debconf`` to update the values::

 sudo dpkg-reconfigure lava-server

A :ref:`remote_worker` has an empty configuration file::

 /etc/lava-server/worker.conf

Postgres on the master server is running on the default port 5432 (or
whatever port you have configured)

SSHFS on the worker has successfully mounted from the master. Check
``mount`` and ``dmesg`` outputs for help.

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
