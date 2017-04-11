.. _setting_up_pipeline_instance:

Setting up a LAVA pipeline instance
###################################

.. _pipeline_install:

What is the Pipeline?
*********************

.. note:: Linaro production systems in the Cambridge lab began to
   migrate to the V2 Pipeline model with the 2016.2 production
   release, while retaining support for the deprecated V1 model until
   the migration is complete. The V1 support is due to be removed
   in 2017.

The :term:`dispatcher refactoring <refactoring>` in the V2 (Pipeline) model
introduces changes and new elements which should not be confused with the
previous production models. It is supported to install LAVA using solely the
new design but there are some :ref:`pipeline_install_considerations` regarding
your current device usage. Submission requirements and device support can
change before and during a migration to the new design.

This documentation includes notes on the new design, so to make things clearer,
the following terms refer exclusively to the new design and have no bearing on
`single_instance` or `distributed_instance` installation methods from V1 LAVA
which are being used for current production instances in the Cambridge lab.

#. :term:`pipeline`
#. :term:`refactoring`
#. :term:`device dictionary`
#. :term:`ZMQ`

The pipeline model also changes the way that results are gathered, exported and
queried, replacing the `bundle stream`, `result bundle` and `filter` dashboard
objects. This new :term:`results` functionality only operates on pipeline test
jobs and is ongoing development, so some features are incomplete and likely to
change in future releases. Admins can choose to not show the new results app,
for example until pipeline devices are supported on that instance, by setting
the ``PIPELINE`` to ``false`` in :file:`/etc/lava-server/settings.conf` - make
sure the file validates as JSON before restarting apache::

 "PIPELINE": false

If the value is not set or set to ``true``, the Results app will be displayed.

.. seealso:: :ref:`setting_up_pipeline_instance`

.. _pipeline_install_considerations:

Initial considerations
======================

#. The default setup of the LAVA packages and codebase is for the current
   dispatcher and the V1 distributed deployment but this will change during
   2017 before the old code is removed. Until then, installations will continue
   to provide both models.

#. A LAVA pipeline instance can have existing remote worker support alongside
   but uses a completely different mechanism to identify remote workers and run
   jobs on pipeline devices.

#. If both systems are enabled, devices can support both pipeline and current
   JSON submissions. Devices can be made :term:`exclusive` to prevent JSON
   submissions.

#. The default setup provides both mechanisms, the only step required to allow
   pipeline submissions to devices connected to ``http://localhost`` is to have
   pipeline devices available.

#. Distributed deployments need changes on each worker, see
   :ref:`changing_existing_workers` but this can be avoided if all devices on
   the instance are suitable for the pipeline.

#. Pipeline setup is a much simplified task for admins but still contains some
   manual steps. See :ref:`installing_pipeline_worker`.

#. If only pipeline devices are to be supported, the dispatchers running
   ``lava-slave`` do **not** need to have the ``lava-server`` package
   installed. Each dispatcher does need to be able to connect to the ZMQ port
   specified in the ``lava-master`` configuration of the instance (which is
   then the only machine related to that instance which has ``lava-server``
   installed). The ``lava-server`` package on the master should be installed as
   a single master instance of LAVA.

#. The :term:`ZMQ` protocol incorporates buffering at each end such that either
   the ``lava-master`` or the ``lava-slave`` service can be restarted at any
   time without affecting currently running jobs or requiring any changes or
   restarts at the other end of the connection. There are no other connections
   required between the slave and the master and the outgoing request from the
   slave is initiated by the slave, so it is possible for the slave to be
   behind a local firewall, as long as the relevant ports are open for outgoing
   traffic. i.e. the slave pulls from the master, the master cannot push to the
   slave. (This does then mean that a :term:`hacking session` would be
   restricted to those with access through such a firewall.)

.. _installing_pipeline_worker:

Detailed changes
****************

The pipeline design designates the machine running Django and PostgreSQL as the
``lava-master`` and all other machines connected to that master which will
actually be running the jobs are termed ``lava-slave`` machines.

Dependencies and recommends
===========================

Debian has the concept of Dependencies which must be installed and Recommends
which are optional but expected to be useful by most users of the package in
question.  Opting out of installing Recommends is supported when installing
packages, so if admins have concerns about extra packages being installed on
the slaves (e.g. if using ARMv7 slaves or simply to reduce the complexity of
the install) then Recommends can be omitted for the installation of these
dependencies,

The 2016.6 release adds a dependency on ``python-guestfs``. The Recommends for
GuestFS can be omitted from the installation, if admins desire, but this needs
to be done ahead of the upgrade to 2016.6::

 $ sudo apt --no-install-recommends install python-guestfs

.. _configuring_lava_slave:

Installing lava-dispatcher
==========================

If this slave has no devices which will be used by the current dispatcher, only
by the pipeline, i.e. :term:`exclusive` devices, only ``lava-dispatcher`` needs
to be installed, not ``lava-server``::

 $ sudo apt install lava-dispatcher

#. Change the dispatcher configuration in ``/etc/lava-dispatcher/lava-slave``
   to allow the init script for ``lava-slave`` (``/etc/init.d/lava-slave``) to
   connect to the relevant ``lava-master`` instead of ``localhost``. Change the
   port numbers, if required, to match those in use on the ``lava-master``::

     /etc/lava-dispatcher/lava-slave

     # Configuration for lava-slave daemon

     # URL to the master and the logger
     # MASTER_URL="tcp://<lava-master-dns>:5556"
     # LOGGER_URL="tcp://<lava-master-dns>:5555"

     # Logging level should be uppercase (DEBUG, INFO, WARNING, ERROR)
     # LOGLEVEL="DEBUG"

     # Encryption
     # If set, will activate encryption using the master public and the slave
     # private keys
     # ENCRYPT="--encrypt"
     # MASTER_CERT="--master-cert /etc/lava-dispatcher/certificates.d/<master.key>"
     # SLAVE_CERT="--slave-cert /etc/lava-dispatcher/certificates.d/<slave.key_secret>"

   .. seealso:: :ref:`zmq_master_encryption` and :ref:`zmq_slave_encryption`

#. Restart ``lava-slave`` once the changes are complete::

    $ sudo service lava-slave restart

#. The administrator of the master will then be able to allocate
   pipeline devices to this slave.

.. note:: For security reasons, the slave does not declare the devices
   connected to it to the master. The LAVA configuration on the slave actually
   needs no knowledge of what is connected or where as long as services like
   ``ser2net`` are configured. All the LAVA configuration data is stored solely
   in the database of the master. Once this data is entered by the admin of the
   master, the slave then needs to connect and the admin can then select that
   slave for the relevant devices. Once selected, the slave can immediately
   start running pipeline jobs on those devices.

The administrator of the master will require the following information about
the devices attached to each slave:

#. Confirmation that a suitable template already exists, for each device i.e.
   :ref:`adding_known_device`

#. A completed and tested :term:`device dictionary` for each device.

This information contains specific information about the local network setup of
the slave and will be transmitted between the master and the slave in **clear
text** over :term:`ZMQ`. Any encryption would need to be arranged separately
between the slave and the master. Information typically involves the hostname
of the PDU, the port number of the device on that PDU and the port number of
the serial connection for that device. The slave is responsible for ensuring
that these ports are only visible to that slave. There is no need for any
connections to be visible to the master.

.. _adding_pipeline_workers:

Adding pipeline workers to the master
*************************************

A worker which only has :term:`exclusive` pipeline devices attached can be
installed as a :ref:`pipeline worker <installing_pipeline_worker>`. These
workers need to be manually added to the master so that the admins of the
master have the ability to assign devices in the database and enable or disable
the worker.

To add a new pipeline worker::

 $ sudo lava-server manage pipeline-worker --hostname <HOSTNAME>

To add a pipeline worker with a description::

 $ sudo lava-server manage pipeline-worker --hostname <HOSTNAME> --description <DESC>

To add a pipeline worker in a disabled state::

 $ sudo lava-server manage pipeline-worker --hostname <HOSTNAME> --disable

Pipeline workers are enabled or disabled in the Django admin interface by
changing the ``display`` field of the worker. Jobs submitted to devices on that
worker will fail, so it is also recommended that the devices would be made
offline at the same time. (The django admin interface has support for selecting
devices by worker and taking all selected devices offline in a single action.)

.. seealso:: :ref:`create_device_database`

.. index:: ZMQ authentication, master slave configuration

.. _zmq_curve:

Using ZMQ authentication and encryption
***************************************

``lava-master`` and ``lava-slave`` use ZMQ to pass control messages and log
messages. When using a slave on the same machine as the master, this traffic
does not need to be authenticated or encrypted. When the slave is remote to the
master, it is **strongly** recommended that the slave authenticates with the
master using ZMQ curve so that all traffic can then be encrypted and the master
can refuse connections which cannot be authenticated against the credentials
configured by the admin.

To enable authentication and encryption, you will need to restart the master
and each of the slaves. Once the master is reconfigured, it will not be
possible for the slaves to communicate with the master until each is configured
correctly. It is recommended that this is done when there are no test jobs
running on any of the slaves, so a maintenance window may be needed before the
work can start. ZMQ is able to cope with short interruptions to the connection
between master and slave, so depending on the particular layout of your
instance, the changes can be made on each machine before the master is
restarted, then the slaves can be restarted. Make sure you test this process on
a temporary or testing instance if you are planning on doing this for a live
instance without using a maintenance window.

Encryption is particularly important when using remote slaves as the control
socket (which manages starting and ending testjobs) needs to be protected when
it is visible across open networks. Authentication ensures that only known
slaves are able to connect to the master. Once authenticated, all communication
will be encrypted using the certificates.

Protection of the secret keys for the master and each of the slaves is the
responsibility of the admin. If a slave is compromised, the admin can delete
the certificate from ``/etc/lava-dispatcher/certificates.d/`` and restart the
master daemon to immediately block that slave.

.. index:: encrypt, ZMQ certificates

Create certificates
===================

Encryption is supported by default in ``lava-master`` and ``lava-slave`` but
needs to be enabled in the init scripts for each daemon. Start by generating a
master certificate on the master::

 $ sudo /usr/share/lava-dispatcher/create_certificate.py master

Now generate a unique slave certificate on each slave. The default name for any
slave certificate is just ``slave`` but this is only relevant for testing. Use
a name which relates to the hostname or location or other unique aspect of each
slave. The admin will need to be able to relate each certificate to a specific
slave machine::

 $ sudo /usr/share/lava-dispatcher/create_certificate.py foo_slave_1

Distribute public certificates
==============================

Copy the public component of the master certificate to each slave. By default,
the master public key will be
``/etc/lava-dispatcher/certificates.d/master.key`` and needs to be copied to
the same directory on each slave.

Copy the public component of each slave certificate to the master. By default,
the slave public key will be ``/etc/lava-dispatcher/certificates.d/slave.key``.

Admins need to maintain the set of slave certificates in
``/etc/lava-dispatcher/certificates.d`` - only certificates declared by active
slaves will be used but having obsolete or possibly compromised certificates
available to the master is a security risk.

.. _preparing_for_zmq_auth:

Preparation
===========

Once enabled, the master will refuse connections from any slave which are
either not encrypted or lack a certificate in
``/etc/lava-dispatcher/certificates.d/``. So before restarting the master, stop
each of the slaves::

 $ sudo service lava-slave stop

.. _zmq_master_encryption:

Enable master encryption
========================

The master will only authenticate the slave certificates if the master is
configured with the ``--encrypt`` option. Edit ``/etc/lava-server/lava-master``
to enable encryption::

 # Encryption
 # If set, will activate encryption using the master public and the slave
 # private keys
 ENCRYPT="--encrypt"

If you have changed the name or location of the master certificate or the
location of the slave certificates, specify those locations and names
explicitly::

 # MASTER_CERT="--master-cert /etc/lava-dispatcher/certificates.d/<master.key_secret>"
 # SLAVES_CERTS="--slaves-certs /etc/lava-dispatcher/certificates.d"

.. note:: Each master needs to find the **secret** key for that master and the
   **directory** containing all of the  **public** slave keys copied onto that
   master by the admin.

.. seealso:: :ref:`preparing_for_zmq_auth`

.. _zmq_slave_encryption:

Enable slave encryption
=======================

.. seealso:: :ref:`preparing_for_zmq_auth`

Edit ``/etc/lava-dispatcher/lava-slave`` to enable encryption by adding the
enabling the ``--encrypt`` argument::

 # Encryption
 # If set, will activate encryption using the master public and the slave
 # private keys
 ENCRYPT="--encrypt"

If you have changed the name or location of the master certificate or the
location of the slave certificates, specify those locations and names in
``/etc/lava-dispatcher/lava-slave`` explicitly::

 # MASTER_CERT="--master-cert /etc/lava-dispatcher/certificates.d/<master.key>"
 # SLAVE_CERT="--slave-cert /etc/lava-dispatcher/certificates.d/<slave.key_secret>"

.. note:: Each slave refers to the **secret** key for that slave and the
   **public** master key copied onto that slave by the admin.

Restarting master and slaves
============================

For minimal disruption, the master and each slave can be prepared for
encryption and authentication without restarting any of the daemons. Only upon
restarting the master will the slaves need to authenticate.

Once all the slaves are configured restart the master and check the logs for a
message showing that encryption has been enabled on the master. e.g.

.. code-block:: none

 2016-04-26 10:08:56,303 LAVA Daemon: lava-server manage --instance-template=/etc/lava-server/{{filename}}.conf
  --instance=playground dispatcher-master --encrypt --master-cert /etc/lava-dispatcher/certificates.d/master.key_secret
  --slaves-certs /etc/lava-dispatcher/certificates.d pid: 17387
 2016-04-26 09:08:58,410 INFO Starting encryption
 2016-04-26 09:08:58,411 DEBUG Opening master certificate: /etc/lava-dispatcher/certificates.d/master.key_secret
 2016-04-26 09:08:58,411 DEBUG Using slaves certificates from: /etc/lava-dispatcher/certificates.d
 2016-04-26 09:08:58,411 INFO [INIT] LAVA dispatcher-master has started.

Now restart each slave in turn and watch for equivalent messages in the logs:

.. code-block:: none

 2016-04-26 10:11:03,128 LAVA Daemon: lava-dispatcher-slave
  --master tcp://localhost:5556 --hostname playgroundmaster.lavalab
  --socket-addr tcp://localhost:5555 --level=DEBUG
  --encrypt --master-cert /etc/lava-dispatcher/certificates.d/master.key
  --slave-cert /etc/lava-dispatcher/certificates.d/slave.key_secret pid: 17464
 2016-04-26 10:11:03,239 INFO Creating ZMQ context and socket connections
 2016-04-26 10:11:03,239 INFO Starting encryption
 2016-04-26 10:11:03,240 DEBUG Opening slave certificate: /etc/lava-dispatcher/certificates.d/slave.key_secret
 2016-04-26 10:11:03,240 DEBUG Opening master certificate: /etc/lava-dispatcher/certificates.d/master.key
 2016-04-26 10:11:03,241 INFO Connecting to master as <playgroundmaster.lavalab>
 2016-04-26 10:11:03,241 INFO Connection is encrypted using /etc/lava-dispatcher/certificates.d/slave.key_secret
 2016-04-26 10:11:03,241 DEBUG Greeting the master => 'HELLO'
 2016-04-26 10:11:03,241 INFO Waiting for the master to reply
 2016-04-26 10:11:03,244 DEBUG The master replied: ['HELLO_OK']
 2016-04-26 10:11:03,244 INFO Connection with the master established

(This example does use authentication and encryption over localhost, but that
is why the machine is called *playground*.)

.. _adding_pipeline_devices_to_worker:

Adding pipeline devices to a worker
***********************************

Admins use the Django admin interface to add devices to workers using the
worker drop-down in the device detail page.

It is up to the admin to ensure that pipeline devices are assigned to pipeline
workers and devices which can run JSON jobs are assigned only to distributed
deployment workers.

.. note:: A pipeline worker may have a description but does not have a record
   of the IP address, uptime or architecture in the Worker object.

.. _changing_existing_workers:

Changes for existing remote workers
***********************************

On an existing remote worker, a ``lava-master`` daemon will already be running
on localhost (doing nothing). Once the migration to the :term:`pipeline` is
complete, the ``lava-server`` package can be removed from all workers, so the
above information relates to this endpoint. In the meantime, remote workers
should have ``lava-master`` disabled on localhost once the slave has been
directed at the real master as above.

Disabling lava-master on workers
================================

.. note:: A pipeline worker will only have ``lava-dispatcher`` installed, so
   there will be no ``lava-master`` daemon which is installed by
   ``lava-server``.

.. warning:: Only do this on the remote worker but make sure it is done on
   **all** remote workers before submitting pipeline jobs which would need the
   devices on those workers.

If a **new** worker does not **need** to run jobs using the current dispatcher,
i.e. if all devices on this worker are :term:`exclusive`, then ``lava-server``
does not need to be installed and there is no ``lava-master`` daemon to
disable.

For existing workers, pipeline jobs will be likely be mixed with JSON jobs.
This leads to ``lava-server`` being installed on the workers (solely to manage
the JSON jobs). On such workers, ``lava-master`` should be **disabled** once
``lava-slave`` has been reconfigured::

 $ sudo invoke-rc.d lava-master stop
 $ sudo update-rc.d lava-master remove
 $ sudo chmod a-x /etc/init.d/lava-master
 $ sudo service lava-master status

Removing the executable bits stops the lava-master being re-enabled when the
packages are updated.

.. index:: disable v1 worker, fuse, psql, sshfs

.. _disable_v1_worker:

Disabling V1 on pipeline dispatchers
************************************

Existing remote workers with both V1 and V2 devices will need to migrate to
supporting V2 only. Once all devices on the worker can support V2, the admin
can disable V1 test jobs on that worker.

.. caution:: Due to the way that V1 remote workers are configured, it is
   possible for removal of V1 support to **erase** data on the master if these
   steps are not followed in order. It is particularly important that the V1
   SSHFS mountpoint is handled correctly and that any operations on the
   database remain **local** to the remote worker by using ``psql`` instead of
   any ``lava-server`` commands.

#. All device types on the dispatcher must have V2 health checks configured.

#. Make all devices on the dispatcher :term:`exclusive` to V2.

#. Remove V1 configuration files from the dispatcher. Depending on local admin,
   this may involve tools like ``salt`` or ``ansible`` removing files from
   ``/etc/lava-dispatcher/devices/`` and ``/etc/lava-dispatcher/device-types/``

#. Ensure lava-slave is pinging the master correctly:

   .. code-block:: shell

    tail -f /var/log/lava-dispatcher/lava-slave.log

#. Check for existing database records using ``psql``

   .. note:: Do **not** use ``lava-server manage shell`` for this step because
      the developer shell has access to the master database, use ``psql``.

   Check the LAVA_DB_NAME value from ``/etc/lava-server/instance.conf``.  If
   there is no database with that name visible to ``psql``, there is nothing
   else to do for this stage.

   .. code-block:: shell

    $ sudo su postgres
    $ psql lavaserver
    psql: FATAL:  database "lavaserver" does not exist

   If a database does exist with LAVA_DB_NAME, it **should** be empty. Check
   using a sample SQL command:

   .. code-block:: sql

    =# SELECT count(id) from lava_scheduler_app_testjob;

   If records exist, it is up to you to investigate these records and decide if
   something has gone wrong with your LAVA configuration or if these are old
   records from a time when this machine was not a worker. Database records on a
   worker are **not** visible to the master or web UI.

#. Stop the V1 scheduler:

   .. code-block:: shell

    sudo service lava-server stop

#. ``umount`` the V1 SSHFS which provices read-write access to the test job
   log files **on the master**.

   * Check the output of ``mount`` and ``/etc/lava-server/instance.conf`` for
     the value of LAVA_PREFIX. The SSHFS mount is
     ``${LAVA_PREFIX}/default/media``. The directory should be empty once the
     SSHFS mount is removed:

     .. code-block:: shell

      $ mountpoint /var/lib/lava-server/default/media
      /var/lib/lava-server/default/media is a mountpoint
      $ sudo umount /var/lib/lava-server/default/media
      $ sudo ls -a /var/lib/lava-server/default/media
      .  ..

#. Check if ``lavapdu`` is required for the remaining devices. If not, you may
   choose to stop ``lavapdu-runner`` and ``lavapdu-listen``, then remove
   ``lavapdu``:

   .. code-block:: shell

    sudo service lavapdu-listen stop
    sudo service lavapdu-runner stop
    sudo apt-get --purge remove lavapdu-client lavapdu-daemon

#. Unless any other tasks on this worker, unrelated to LAVA, use the postgres
   database, you can now choose to drop the postgres cluster on this worker,
   deleting all postgresql databases on the worker. (Removing or purging the
   ``postgres`` package does not drop the database, it continues to take up
   space on the filesystem).

   .. code-block:: shell

    sudo su postgres
    pg_lsclusters

   The output of ``pg_lsclusters`` is dependent on the version of ``postgres``.
   Check for the ``Ver`` and ``Cluster`` columns, these will be needed to
   identify the cluster to drop, e.g. ``9.4 main``.

   To drop the cluster, specify the ``Ver`` and ``Cluster`` to the
   ``pg_dropcluster`` postgres command, for example:

   .. code-block:: shell

    pg_dropcluster 9.4 main --stop
    exit

#. If lava-coordinator is installed, check the local config is not localhost in
   ``/etc/lava-coordinator/lava-coordinator.conf`` and then stop
   lava-coordinator::

    sudo service lava-coordinator stop

   .. caution:: ``lava-coordinator`` will typically be uninstalled in a later
      step. Ensure that the working coordinator configuration is retained by
      copying ``/etc/lava-coordinator/lava-coordinator.conf`` to a safe
      location. It will need to be restored later. The coordinator process
      itself is not needed on the worker for either V1 or V2 was installed
      as a requirement of ``lava-server``, only the configuration is actually
      required.

#. Remove ``lava-server``:

   .. code-block:: shell

    sudo apt-get --purge remove lava-server

#. Remove the remaining dependencies required for ``lava-server``:

   .. code-block:: shell

    sudo apt-get --purge autoremove

   This list may include ``lava-coordinator``, ``lava-server-doc``,
   ``libapache2-mod-uwsgi``, ``libapache2-mod-wsgi``, ``postgresql``,
   ``python-django-auth-ldap``, ``python-django-kvstore``,
   ``python-django-restricted-resource``, ``python-django-tables2``,
   ``python-ldap``, ``python-markdown``, ``uwsgi-core`` but may also remove
   others. Check the list carefully.

#. Check lava-slave is still pinging the master correctly.

#. Check for any remaining files in ``/etc/lava-server/`` and remove.

#. Create the ``/etc/lava-coordinator`` directory and restore
   ``/etc/lava-coordinator/lava-coordinator.conf`` to restore MultiNode
   operation on this worker.

#. Check for any remaining lava-server processes - only ``lava-slave`` should
   be running.

#. Check if apache can be cleanly restarted. You may need to run ``sudo
   a2dismod uwsgi`` and ``sudo a2dissite lava-server``:

   .. code-block:: shell

    sudo service apache2 restart

#. Copy the default ``apache2`` lava-dispatcher configuration into
   ``/etc/apache2/sites-available/`` and enable:

   .. code-block:: shell

    cp /usr/share/lava-dispatcher/apache2/lava-dispatcher.conf /etc/apache2/sites-available/
    $ sudo a2ensite lava-dispatcher
    $ sudo service apache2 restart
    $ sudo apache2ctl -M
    $ wget http://localhost/tmp/
    $ rm index.html

#. Undo fuse configuration

   V1 setup required editing ``/etc/fuse.conf`` on the worker and enabling the
   ``user_allow_other`` option. This can now be disabled.

#. Run healthchecks on all your devices.

.. index:: disable v1 master, revoke v1 postgres access

.. _disable_v1_master:

Disabling V1 support on the master
**********************************

Once all workers on an instance have had V1 support disabled, there remain
tasks to be done on the server. V1 relies on read:write database access from
each worker supporting V1 as well as the SSHFS mountpoint. For the security of
the data on the master, this access needs to be revoked now that V1 is no
longer in use on this master.

The changes below undo the *Distributed deployment* setup of V1 for remote
workers. The master continues to have a worker available and this worker is
unaffected by the removal of remote worker support.

.. note:: There was a lot of scope in V1 for admins to make subtle changes to
   the local configuration, especially if the instance was first installed
   before the Debian packaging became the default installation method. (Even if
   the machine has later been reinstalled, elements such as system usernames,
   database names and postgres usernames will have been retained to be able to
   access older data.) Check the details in ``/etc/lava-server/instance.conf``
   on the master for information on ``LAVA_SYS_USER``, ``LAVA_DB_USER`` and
   ``LAVA_PREFIX``. In some places, V1 setup only advised that certain changes
   were made - admins may have adapted these instructions and removal of those
   changes will need to take this into account. It is, however, important that
   the V1 support changes are removed to ensure the security of the data on the
   master.

SSH authorized keys
===================

The SSH public keys need to be removed from the ``LAVA_SYS_USER`` account on
the master. Check the contents of ``/etc/lava-server/instance.conf`` - the
default for recent installs is ``lavaserver``. Check the details in, for
example, ``/var/lib/lava-server/home/.ssh/authorized_keys``:

.. code-block:: shell

 $ sudo su lavaserver
 $ vim /var/lib/lava-server/home/.ssh/authorized_keys

.. note:: V1 used the same comment for all keys. ``ssh key used by LAVA for
   sshfs``. Once all V1 workers are disabled, all such keys can be removed
   from ``/var/lib/lava-server/home/.ssh/authorized_keys``.

Prevent postgres listening to workers
=====================================

V1 setup advised that ``postgresql.conf`` was modified to allow
``listen_addresses = '*'``. Depending on your version of postgres, this file
can be found under the ``/etc/postgresql/`` directory, in the ``main``
directory for that version of ``postgres``. e.g.
``/etc/postgresql/9.4/main/postgresql.conf``

There is no need for a V2 master to have any LAVA processes connecting to the
database other than those on the master. ``listen_addresses`` can be updated,
according to the postgres documentation. The default is for
``listen_addresses`` to be commented out in ``postgresql.conf``.

Revoke postgres access
======================

V1 setup advised that ``pg_hba.conf`` was modified to allow remote workers to
be able to read and write to the postgres database. Depending on your version
of postgres, this file can be found under the ``/etc/postgresql/`` directory,
in the ``main`` directory for that version of ``postgres``. e.g.
``/etc/postgresql/9.4/main/pg_hba.conf`` A line similar to the following
may exist:

.. code-block:: none

 host    lavaserver      lavaserver      0.0.0.0/0               md5

Some instances may have a line similar to:

.. code-block:: none

 host    all             all             10.0.0.0/8              md5

For V2, only the default postgres configuration is required. For example:

.. code-block:: none

 local   all             all                                     peer
 local   all             all                                     peer
 host    all             all             127.0.0.1/32            md5
 host    all             all             ::1/128                 md5

Check the entries in your own instance (in this example, 9.4) using:

.. code-block:: none

 sudo grep -v '#' /etc/postgresql/9.4/main/pg_hba.conf

Restart postgres
================

For these changes to take effect, postgres must be restarted:

.. code-block:: shell

 sudo service postgresql restart
