.. index:: V1 removal

.. _v1_removal:

Removal of V1 data objects
##########################

This page is to help administrators of LAVA instances handle the upgrade of
``lava-server`` which causes the **DELETION of ALL V1 test data**. Admins have
the choice of aborting the installation of this upgrade to protect the V1 test
data with the proviso that **no** further updates of LAVA will be possible on
such instances. Support for LAVA V1 ended with the block on submission of V1
test jobs in the 2017.10 release. All future releases of LAVA will only contain
V2 code and will only be able to access V2 test data. If admins choose to keep
an instance to act as an archive of V1 test data, that instance **must** stay
on the **2017.10** release of LAVA.

.. seealso:: :ref:`v1_end_of_life`

.. danger:: Upgrades normally try to avoid removal of data but this upgrade
   **deliberately drops the V1 data tables permanently**. Whilst this procedure
   has been tested, there is no guarantee that all instances will manage the
   removal of the V1 test data cleanly. It is strongly recommended that all
   instances have a usable :ref:`backup <admin_backups>` before proceeding.

   **DO NOT INTERRUPT this upgrade**. If anything goes wrong with the upgrade,
   **STOP IMMEDIATELY** and refer to this page, then :ref:`contact us
   <getting_support>`.

   At all costs, avoid running commands which activate or execute any further
   migration operation, especially ``lava-server manage migrate`` and
   ``lava-server manage makemigrations``. Remember that removing, purging or
   reinstalling the ``lava-server`` package without fixing the database will
   **not** fix anything as it will attempt to run more migrations. Even if you
   find third party advice to run such commands, **do not do so** without
   :ref:`talking to the LAVA software team <getting_support>`.

   It remains possible to escalate a failed upgrade into a **complete data
   loss** of V1 and V2 test data by trying to fix a broken system. In the event
   of a failed upgrade, the LAVA software team may advise you to restore from
   backup and then determine if there are additional steps which can be taken
   to allow the upgrade to complete, instead of attempting to fix the breakage
   directly. Without a backup, your only option may be to start again with a
   completely fresh installation with no previous test jobs, no users and no
   configured devices.

Maintenance window
******************

It is recommended that all instances declare a scheduled **maintenance window**
before starting this upgrade. Take all devices offline and wait for all running
test jobs to finish. For this upgrade is it also important to replace the
``lava-server`` apache configuration with a temporary holding page for all URLs
related to the instance, so that users get a useful page instead of an error.
This prevents accidental accesses to the database during any later recovery
work and also prevents new jobs being submitted.

.. _removing_v1_files:

Removing V1 files after the upgrade
***********************************

After a successful upgrade to 2017.12, the following V1 components will still
exist:

* V1 ``TestJob`` database objects (definition(s), status, submitter, device
  etc.)

* V1 test job log files in ``/var/lib/lava-server/default/media/job-output/``

* V1 bundles as JSON files in ``/var/lib/lava-server/default/media/bundles/``

* V1 attachments in ``/var/lib/lava-server/default/media/attachments/``

* Configuration files in ``/etc/init.d/``::

   /etc/init.d/lava-master*
   /etc/init.d/lava-publisher*
   /etc/init.d/lava-server*
   /etc/init.d/lava-server-gunicorn*
   /etc/init.d/lava-slave*

To delete the test job log files and the ``TestJob`` database objects, use the
``lava-server manage`` helper:

.. code-block:: none

  $ sudo lava-server manage jobs rm --v1

Bundles and attachments can be deleted simply by removing the directories:

.. code-block:: none

 $ sudo rm -rf /var/lib/lava-server/default/media/bundles
 $ sudo rm -rf /var/lib/lava-server/default/media/attachments

.. index:: V1 removal - abort

.. _aborting_v1_removal:

Aborting the upgrade
********************

If you have read `the roadmap to removal of V1
<https://lists.lavasoftware.org/pipermail/lava-announce/2017-September/000037.html>`_
and still proceeded with the upgrade to ``2017.12`` but then decide to abort,
there is **one** safe chance to do so, when prompted at the very start of the
install process with the following prompt::

 Configuring lava-server

 If you continue this upgrade, all V1 test data will be permanently DELETED.

 V2 test data will not be affected. If you have remaining V1 test data that you
 care about, make sure it is backed up before you continue here.

 Remove V1 data from database?

If you have answered **YES** to that prompt, **there is no way to safely abort
the upgrade**. You **must** proceed and then :ref:`recover from a backup
<admin_restore_backup>` if something goes wrong or you want to keep that
instance on a version of LAVA which no longer receives updates.

.. caution:: Many configuration management systems hide such prompts, to allow
   for smooth automation, by setting environment variables. **There is nothing
   LAVA can do to prevent this** and it is **not** a bug in LAVA when it
   happens.

What happens if I choose to abort?
**********************************

The system will continue operating with the existing version of LAVA from
before the upgrade was attempted. The upgrade will still be available and you
will be asked the question again, each time the package tries to upgrade. You
may want to use ``apt-mark hold lava-server`` to prevent ``apt`` considering
the newer version as an upgrade.

What happens if the LAVA package upgrade fails?
***********************************************

**STOP HERE!**
==============

.. warning:: Do not make **any** attempt to fix the broken system without
   :ref:`talking to us <getting_support>`. Put the full error messages and the
   command history into a pastebin and attach to an email to the lava-users
   mailing list. It is generally unhelpful to attempt to fix problems with this
   upgrade over IRC.

The system will be left with a ``lava-server`` package which is not completely
installed. ``apt`` will complain when further attempts are made to install any
packages (and will try to complete the installation), so take care on what
happens on that instance from here on.

#. Record the complete and exact error messages from the master. These may
   scroll over a few pages but **all** the content will be required.

#. Record the history of **all** commands issued on the master recently.

#. Declare an **immediate** maintenance window or tell all users any current
   window must be extended. Disable all access to the complete instance. For
   example, set up routing to prevent the apache service from responding on the
   expected IP address and virtual host details to avoid confusing users. Place
   a holding page elsewhere until the installation is fully complete and
   tested.

   .. caution:: Users must **not** be allowed to access the instance whilst
      recovery from this failure is attempted. There must be **no** database
      accesses outside the explicit control of the admin attempting the
      recovery.

   Complete downtime is the **only** safe way to attempt to fix the problems.

#. Assure yourself that a suitable, tested, backup already exists.

.. index:: disable v1 worker, fuse, psql, sshfs

.. _disable_v1_worker:

Disabling V1 on pipeline dispatchers
####################################

Existing remote workers with both V1 and V2 device support will need to 
migrate to supporting V2 only. Once all devices on the worker can 
support V2, the admin can disable V1 test jobs on that worker.

.. caution:: Due to the way that V1 remote workers are configured, it 
   is possible for removal of V1 support to **erase** data on the 
   master if these steps are not followed in order. It is particularly 
   important that the V1 SSHFS mountpoint is handled correctly and that 
   any operations on the database remain **local** to the remote worker 
   by using ``psql`` instead of any ``lava-server`` commands.

#. All device types on the dispatcher must have V2 health checks 
   configured.

#. Remove V1 configuration files from the dispatcher. Depending on 
   local admin, this may involve tools like ``salt`` or ``ansible`` 
   removing files from ``/etc/lava-dispatcher/devices/`` and 
   ``/etc/lava-dispatcher/device-types/``

#. Ensure lava-slave is pinging the master correctly:

   .. code-block:: shell

    tail -f /var/log/lava-dispatcher/lava-slave.log

#. Check for existing database records using ``psql``

   .. note:: Do **not** use ``lava-server manage shell`` for this step 
      because the developer shell has access to the master database, 
      use ``psql``.

   Check the LAVA_DB_NAME value from 
   ``/etc/lava-server/instance.conf``.  If there is no database with 
   that name visible to ``psql``, there is nothing else to do for this 
   stage.

   .. code-block:: shell

    $ sudo su postgres
    $ psql lavaserver
    psql: FATAL:  database "lavaserver" does not exist

   If a database does exist with LAVA_DB_NAME, it **should** be empty. 
   Check using a sample SQL command:

   .. code-block:: sql

    =# SELECT count(id) from lava_scheduler_app_testjob;

   If records exist, it is up to you to investigate these records and 
   decide if something has gone wrong with your LAVA configuration or 
   if these are old records from a time when this machine was not a 
   worker. Database records on a worker are **not** visible to the 
   master or web UI.

#. Stop the V1 scheduler:

   .. code-block:: shell

    sudo service lava-server stop

#. ``umount`` the V1 SSHFS which provices read-write access to the test 
   job log files **on the master**.

   * Check the output of ``mount`` and
     ``/etc/lava-server/instance.conf`` for the value of LAVA_PREFIX.
     The SSHFS mount is ``${LAVA_PREFIX}/default/media``. The directory
     should be empty once the SSHFS mount is removed:

     .. code-block:: shell

      $ sudo mountpoint /var/lib/lava-server/default/media
      /var/lib/lava-server/default/media is a mountpoint
      $ sudo umount /var/lib/lava-server/default/media
      $ sudo ls -a /var/lib/lava-server/default/media
      .  ..

#. Check if ``lavapdu`` is required for the remaining devices. If not, 
   you may choose to stop ``lavapdu-runner`` and ``lavapdu-listen``, 
   then remove ``lavapdu``:

   .. code-block:: shell

    sudo service lavapdu-listen stop
    sudo service lavapdu-runner stop
    sudo apt-get --purge remove lavapdu-client lavapdu-daemon

#. Unless any other tasks on this worker, unrelated to LAVA, use the 
   postgres database, you can now choose to drop the postgres cluster 
   on this worker, deleting all postgresql databases on the worker. 
   (Removing or purging the ``postgres`` package does not drop the 
   database, it continues to take up space on the filesystem).

   .. code-block:: shell

    sudo su postgres
    pg_lsclusters

   The output of ``pg_lsclusters`` is dependent on the version of 
   ``postgres``. Check for the ``Ver`` and ``Cluster`` columns, these 
   will be needed to identify the cluster to drop, e.g. ``9.4 main``.

   To drop the cluster, specify the ``Ver`` and ``Cluster`` to the
   ``pg_dropcluster`` postgres command, for example:

   .. code-block:: shell

    pg_dropcluster 9.4 main --stop
    exit

#. If lava-coordinator is installed, check the local config is not 
   localhost in ``/etc/lava-coordinator/lava-coordinator.conf`` and 
   then stop lava-coordinator::

    sudo service lava-coordinator stop

   .. caution:: ``lava-coordinator`` will typically be uninstalled in a 
      later step. Ensure that the working coordinator configuration is 
      retained by copying 
      ``/etc/lava-coordinator/lava-coordinator.conf`` to a safe 
      location. It will need to be restored later. The coordinator 
      process itself is not needed on the worker for either V1 or V2 
      was installed as a requirement of ``lava-server``, only the 
      configuration is actually required.

#. Remove ``lava-server``:

   .. code-block:: shell

    sudo apt-get --purge remove lava-server

#. Remove the remaining dependencies required for ``lava-server``:

   .. code-block:: shell

    sudo apt-get --purge autoremove

   This list may include ``lava-coordinator``, ``lava-server-doc``,
   ``libapache2-mod-uwsgi``, ``libapache2-mod-wsgi``, ``postgresql``,
   ``python-django-auth-ldap``, ``python-django-restricted-resource``,
   ``python-django-tables2``, ``python-ldap``, ``python-markdown``,
   ``uwsgi-core`` but may also remove others. Check the list carefully.

#. Check lava-slave is still pinging the master correctly.

#. Check for any remaining files in ``/etc/lava-server/`` and remove.

#. Create the ``/etc/lava-coordinator`` directory and restore
   ``/etc/lava-coordinator/lava-coordinator.conf`` to restore MultiNode
   operation on this worker.

#. Check for any remaining lava-server processes - only ``lava-slave`` 
   should be running.

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

   V1 setup required editing ``/etc/fuse.conf`` on the worker and 
   enabling the ``user_allow_other`` option. This can now be disabled.

#. Run healthchecks on all your devices.

.. index:: disable v1 master, revoke v1 postgres access

.. _disable_v1_master:

Disabling V1 support on the master
##################################

Once all workers on an instance have had V1 support disabled, there 
remain tasks to be done on the server. V1 relies on read:write database 
access from each worker supporting V1 as well as the SSHFS mountpoint. 
For the security of the data on the master, this access needs to be 
revoked now that V1 is no longer in use on this master.

The changes below undo the *Distributed deployment* setup of V1 for 
remote workers. The master continues to have a worker available and 
this worker is unaffected by the removal of remote worker support.

.. note:: There was a lot of scope in V1 for admins to make subtle 
   changes to the local configuration, especially if the instance was 
   first installed before the Debian packaging became the default 
   installation method. (Even if the machine has later been 
   reinstalled, elements such as system usernames, database names and 
   postgres usernames will have been retained to be able to access 
   older data.) Check the details in ``/etc/lava-server/instance.conf`` 
   on the master for information on ``LAVA_SYS_USER``, ``LAVA_DB_USER`` 
   and ``LAVA_PREFIX``. In some places, V1 setup only advised that 
   certain changes were made - admins may have adapted these 
   instructions and removal of those changes will need to take this 
   into account. It is, however, important that the V1 support changes 
   are removed to ensure the security of the data on the master.

SSH authorized keys
*******************

The SSH public keys need to be removed from the ``LAVA_SYS_USER`` 
account on the master. Check the contents of 
``/etc/lava-server/instance.conf`` - the default for recent installs is 
``lavaserver``. Check the details in, for example, 
``/var/lib/lava-server/home/.ssh/authorized_keys``:

.. code-block:: shell

 $ sudo su lavaserver
 $ vim /var/lib/lava-server/home/.ssh/authorized_keys

.. note:: V1 used the same comment for all keys. ``ssh key used by LAVA 
   for sshfs``. Once all V1 workers are disabled, all such keys can be 
   removed from ``/var/lib/lava-server/home/.ssh/authorized_keys``.

Prevent postgres listening to workers
*************************************

V1 setup advised that ``postgresql.conf`` was modified to allow 
``listen_addresses = '*'``. Depending on your version of postgres, this 
file can be found under the ``/etc/postgresql/`` directory, in the 
``main`` directory for that version of ``postgres``. e.g. 
``/etc/postgresql/9.4/main/postgresql.conf``

There is no need for a V2 master to have any LAVA processes connecting 
to the database other than those on the master. ``listen_addresses`` 
can be updated, according to the postgres documentation. The default is 
for ``listen_addresses`` to be commented out in ``postgresql.conf``.

Revoke postgres access
**********************

V1 setup advised that ``pg_hba.conf`` was modified to allow remote 
workers to be able to read and write to the postgres database. 
Depending on your version of postgres, this file can be found under the 
``/etc/postgresql/`` directory, in the ``main`` directory for that 
version of ``postgres``. e.g. ``/etc/postgresql/9.4/main/pg_hba.conf`` 
A line similar to the following may exist:

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
****************

For these changes to take effect, postgres must be restarted:

.. code-block:: shell

 sudo service postgresql restart

.. index:: archive v1

.. _archiving_v1:

Support for a V1 archive
########################

After the **2017.10** release of LAVA, :ref:`V1 jobs will no longer be 
supported<v1_end_of_life>`. Beyond that point, some admins might want 
to keep an archive of their old V1 test data to allow their users to 
continue accessing it.

The recommended way to do that is to create a read-only *archive* 
instance for that test data, alongside the main working LAVA instance. 
Take a backup of the test data in the main instance, then restore it 
into the new archive instance.

To set up an archive instance:

* Configure a machine to run Debian 9 (Stretch) or 8 (Jessie), which
  are the supported targets for LAVA 2017.10.

  .. note:: Remember that rendering the V1 test data can still be very
     resource-heavy, so be careful not to configure an archive instance 
     on a server or virtual machine that's too small for the expected 
     level of load.

* Restore a backup of the database and
  ``/etc/lava-server/instance.conf`` on a clean installation of 
  ``lava-server``. Do **not** be tempted to optimise or delete data 
  from this backup; this is completely unnecessary and may cause the 
  deletion of V1 test data from the archive.

  .. seealso:: :ref:`migrating_postgresql_versions`

* Make changes in the :ref:`django admin interface<django_admin_interface>`:

  * First, disable all the configured workers - the archive instance
    will not be running any test jobs. These workers will only exist
    in the restored database and will have no relevance to the
    archived test data.

  * Remove permissions from all users except a few admins - this will
    stop people from attempting to modify any of the test data.

  * Retire all devices. This will prevent new V2 submissions being
    accepted whilst allowing the archive to present the V1 test data.

    .. warning:: Do **not** simply delete the database objects for the
       devices - this may cause problems.

* Make changes in ``/etc/lava-server/settings.conf`` (JSON syntax):

  * Set the ``ARCHIVED`` flag to ``True``.

  * Add text in the ``BRANDING_MESSAGE`` (which will show on your LAVA
    instance home page) to inform users that this is an archived
    instance.

* Install lava-server 2017.10 from the :ref:`archive_repository`, and
  ensure that the archive instance will not upgrade past that version
  using ``apt-mark hold``. It's also a good plan to stop any upgrades
  to lava-server's direct dependencies ``python-django`` and
  ``python-django-tables2``:

  .. code-block:: none

   $ sudo apt-mark hold lava-server python-django python-django-tables2

  This step is important for your archived data! Later releases will
  deliberately remove access to the test data which is meant to be
  preserved in this archive.

* lava-server 2017.10 will make the dashboard objects read-only; new
  Filters, Image Reports and Image Reports 2.0 cannot be created and
  existing ones cannot be modified.

.. important:: The support for an archive of V1 test data **will be
   removed in 2017.11**, so be very careful of what versions are
   installed. 2017.11 will include more invasive changes to make V1
   test data invisible - be very careful not to upgrade to that
   version if that data matters to you.

.. seealso:: :ref:`archive_repository`
