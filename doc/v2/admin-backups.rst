.. index:: admin backup, backup

.. _admin_backups:

Creating Backups
################

Disaster recovery is an important role for all lab admins. If anyone cares
about the data within the instance and/or the availability of the instance,
then steps need to be taken, in advance, to prepare for the worst.
Additionally, these steps will also help with growing your lab by making it
easier to deploy an initial working setup onto a new master or worker without
going through all the steps manually.

Backups may take up a lot of space, and take a long time to perform. This is a
particular problem with the master where the added load could impact on overall
performance. Investigate methods of writing backups to external storage without
causing undue latency.

Backups may also contain sensitive information like database passwords,
authentication and encryption certificates and keys. Protect your backups from
access by anyone except the admins.

Any backup which has not been tested to successfully restore the previous
service is not worth having as a backup. It may be infeasible to test every
backup but intermittently, one backup needs to be fully tested and all backups
then checked that the equivalent files exist in each.

Avoid backup solutions which try to image the entire drive. For such systems to
work reliably with a database, the database server would have to be stopped.
That first requires that all ``lava-server`` services are stopped and all
running TestJobs are canceled. i.e. A backup like this would require a
maintenance window (scheduled downtime) every time the backup was to be
performed.

.. note:: As such, restoration of backups is not a simple (or particularly
   quick) process. See :ref:`admin_restore_backup`.

If you use configuration management, as recommended in
:ref:`best_admin_practices`, then this forms part of your backup and recovery
plan.

.. _admin_backup_dependencies:

Dependencies within backups
***************************

Backups **must** be considered as self-contained. It is **dangerous** to try to
mix files from a backup on one date with files from a different date. This is a
particular problem with the database and the ``lava-server`` package but also
applies to device configuration and can include the ``python-django`` package
as well as other dependencies. Do **not** use an incremental backup procedure
that separates the database from the code or from the device configuration.

Admins may wish to download the currently installed ``lava-server`` package
(and possibly other packages) and add the file(s) to the backup. This can be
done using the ``download`` support in ``# apt-get``:

.. code-block:: none

 # apt-get download lava-server=2016.12-1

It is best to specify the exact version to ensure the correct file is
downloaded. The version string can be obtained from the running system during
the backup by using ``dpkg-query``:

.. code-block:: none

 $ dpkg-query -W -f '${version}\n' 'lava-server'

Remember that if the package comes from
``backports``, it will have a ``~bpo`` suffix in the version name and ``apt``
will need to be told to use ``backports``:

.. code-block:: none

 # apt-get download -t jessie-backports lava-server=2016.12-1~bpo8+1

More information is available using the Debian Package Tracker, e.g. for
``lava-server``: https://tracker.debian.org/pkg/lava-server

Packages installed directly from a Debian mirror will be available via
http://snapshot.debian.org/.

Some data loss is inevitable for the period between the time of failure and the
time of the most recent backup. (Admins may choose to start every maintenance
window with a backup for this reason.) However, restoring an older backup has
significant issues, beyond simply the larger amount of data which will be lost.

.. danger:: If the database and the ``lava-server`` package do not
   **precisely** match in your backups, **complete data loss is possible**
   during restoration, depending on exactly what migrations are applied or not
   yet applied. At best, this will mean restarting the restoration process,
   possibly with an even older backup. If problems appear with database
   migrations during a restore, **stop immediately** to avoid making things
   worse. At all costs, avoid running commands which activate or execute any
   further migration operation, especially ``lava-server manage migrate`` and
   ``lava-server manage makemigrations``. Remember that reinstalling the
   ``lava-server`` package without fixing the database will **not** fix
   anything as it will attempt to run more migrations. Even if you find third
   party advice to run such commands, **do not do so** without :ref:`talking to
   the LAVA software team <getting_support>`.

Migrations are applied using the ``python-django`` package and the version of
``python-django`` installed can also affect whether a database restoration will
be successful. Other dependencies (like ``python-django-common`` and
``python-django-tables2``) may affect whether the service is operational even
with a working database restoration.

Some of the critical packages to monitor include:

* ``postgresql`` - and associated packages, e.g. ``postgresql-13``, according
  to the base suite of the system and the ``postgresql-client-13`` and
  ``postgresql-common`` packages associated with the postgresql server package.

* ``lava-server`` (and ``lava-server-doc``)

* ``lava-dispatcher``

* ``python3-django``

* ``python3-django-tables2``

Check the `LAVA Announce mailing list archives
<https://lists.lavasoftware.org/mailman3/lists/lava-announce.lists.lavasoftware.org/>`_ for additional notices
about new packages to install alongside particular versions of ``lava-server``
and ``lava-dispatcher``. (Admins might choose to download the compressed
archive for the month in which the backup is made and add that to the backup.)

.. _admin_base_suite_issues:

Issues with the base suite
==========================

Ensure that the base system also matches the suite from which the
backup was made. It is **not safe** to restore a backup of a system
which was running with packages from ``buster-backports`` onto a
buster system without those same packages being updated from
``buster-backports`` prior to restoration.

.. _admin_configuration_management:

What to include in your configuration management
************************************************

.. caution:: This list is **not exhaustive**. Some of the files to be included
   in your backups are not specifically LAVA files and each instance will have
   changes to files not listed in this section. This section exists to remind
   admins about files that might not be included in a default backup of a
   running service.

* **Debian configuration**

  It is **essential** that configuration management prepares the target system
  correctly before attempting to restore the data for the service. All updates
  need to be correctly applied, including packages selected from ``backports``
  and other repositories.

  Keep the list of ``apt`` sources in configuration management and restore the
  appropriate sources for the backup being restored or base system being
  created.

  Ensure that all packages are up to date with the appropriate sources.

  .. seealso:: :ref:`admin_backup_dependencies` and
    :ref:`admin_base_suite_issues`

* **Device configuration and health checks**

  * ``/etc/lava-server/dispatcher-config/device-types/``
  * ``/etc/lava-server/dispatcher-config/health-checks/``

* **Service configuration**

  * ``/etc/ser2net.yaml`` or equivalent
  * ``/etc/udev/rules.d/*`` - any rules you might have defined for particular devices or services
  * ``/etc/lava-server/*`` - the rest of the files not already included as
    device configuration.
  * ``/etc/default/`` - specifically, ``lxc``, ``tftpd-hpa``, ``ser2net``
  * ``/etc/lava-dispatcher/lava-worker``
  * ``/etc/lava-coordinator/lava-coordinator.conf``
  * ``/etc/apache2/sites-available/lava-server.conf`` (on the master)
  * ``/etc/apache2/sites-available/lava-dispatcher.conf`` (on a worker)

What to include in your master backups
**************************************

.. caution:: This list is **not exhaustive**. Some of the files to be included
   in your backups are not specifically LAVA files and each instance will have
   changes to files not listed in this section. This section exists to remind
   admins about files that might not be included in a default backup of a
   running service.

If you are not using configuration management, all the files mentioned in
:ref:`admin_configuration_management` need to be included in all your backups.

* **Database** - Use the standard postgres backup support. Remember that
  backing up a running database does add load to the master and can take an
  appreciable amount of time and space on the backup storage media.

  .. seealso:: `Backup and Restore - Postgres Guide
     <http://postgresguide.com/utilities/backup-restore.html>`_

* **Version information and packages**

* **Test job log files and data** located in ``/var/lib/lava-server/default/media/job-output/``

* **Service log files and configuration**

What to include in your worker backups
**************************************

A V2 worker is designed not to need configuration, except that required to
contact the relevant master:

* ``/etc/lava-dispatcher/lava-worker``.

Other files may be required by specific labs and may already be handled by
configuration management, e.g.:

* ``/etc/ser2net.yaml``
* Local PDU scripts.
* ``/etc/udev/rules.d/*`` - any rules you might have defined for particular devices or services

.. index:: backup restore, restore backup

.. _admin_restore_backup:

Restoring a master from a backup
################################

.. warning:: These steps **must** be done in order or data loss is likely,
   at which point the whole restoration process may have to start again.
   However, each lab will differ and some steps can be achieved using more
   than one method. The important objectives are:

   * A maintenance window needs to be declared for this instance as
     soon as possible and needs to remain in place until admins are
     fully satisfied that the restore has completed successfully.

   * No users (other than the admins directly involved in the restore)
     should have any access to the LAVA UI of the affected instance. This
     explicitly includes automated submission services in the rest of your
     CI system like Jenkins. It is imperative that no new test jobs are
     submitted during the maintenance window.

   * Admins need to consider the state of the instance as it will be once
     restored. It is likely that a queue of test jobs will exist within
     the restored database and the state of various devices in the
     database will typically need adjustment to set maintenance mode.

#. Disable access to the system while restoring. For example, set up routing to
   prevent a newly installed apache service from responding on the expected IP
   address and virtual host details to avoid confusing users. Place a holding
   page elsewhere until the restoration is fully complete and tested.

   .. caution:: Users must **not** be allowed to access the instance during the
      restore. There must be **no** database accesses outside the explicit
      control of the admin performing the restore.

   Some admins may already have alternative apache configuration which
   can replace the LAVA interface with a maintenance page whilst still
   allowing admins to access the LAVA interface, e.g. on a different
   hostname or IP address, to do some of the steps below. Such
   arrangements can be very useful but are outside the scope of the
   LAVA documentation, so command line operations are shown instead.
   The goal is the same in each case - cancel test jobs already running
   and in the queue and set all devices to Maintenance. Make sure that
   the instance is in full maintenance before re-enabling the LAVA UI.

#. If you are restoring multiple machines, start with the master and only start
   to restore workers when the master is fully restored but whilst the master
   **remains invisible to users**.

#. Prepare the base system and ensure all packages installed at this stage are
   up to date with the Debian mirrors.

#. If using backports, add the backports apt source and run ``apt update`` to
   populate the apt lists.

#. Install ``lava-server`` as per the documentation. Select a version which is
   slightly earlier or the same as the one installed when the backup was made.
   Avoid installing any version of ``lava-server`` **newer** than the one which
   was running when the backup was created. This installation will use an
   **empty** database and this is expected.

#.  Make sure that this instance actually works. On the command line,
    you can use:

    .. code-block:: none

     $ sudo lava-server manage check --deploy

#. **Stop all LAVA services** - the new installation will have
   automatically started all services using the empty database but
   until the database state can be updated, there must be no attempt to
   reserve devices for jobs in the queue or add test jobs to the queue.

   * ``service lava-server-gunicorn stop``

     * If your local configuration permits only admins to see the LAVA UI,
       then this one LAVA service can be left running.

   * ``service lava-scheduler stop``

   * ``service lava-worker stop``

   * ``service lava-publisher stop``

#. Dump the (empty) initial database and restore the database from the backup.

   .. seealso:: :ref:`migrating_postgresql_versions` for how to drop the
      initial cluster and replace with the cluster from the backup.

#. Using the command line, change the ``health`` of **all** devices
   which are not ``Retired`` to ``Maintenance``.

   Device health can be changed by looping over each device:

   .. code-block:: none

    $ sudo lava-server manage devices update --health MAINTENANCE --hostname ${HOSTNAME}

   or, with 2018.12 and newer, you can use the updated maintenance
   helper:

   .. code-block:: none

    $ sudo lava-server manage maintenance --force

   Check the status of all devices. There should be no devices in the
   following listings:

   .. code-block:: none

    $ sudo lava-server manage devices list --health GOOD
    $ sudo lava-server manage devices list --health LOOPING
    $ sudo lava-server manage devices list --health UNKNOWN

#. Restore the other configuration on the master:

   * Any template changes from the packaged defaults
   * Device dictionaries
   * Per-dispatcher configuration
   * Test job log files from your backup
   * Other elements, as required.

#. Start all LAVA services

   * ``service lava-scheduler start``

   * ``service lava-worker start``

   * ``service lava-publisher start``

   * ``service lava-server-gunicorn restart``

     * If your local configuration cannot restrict the LAVA UI to only
       admins, then take note that this will restore visibility to
       users. **Before** restarting ``lava-server-gunicorn``:

       * Check that the other services are all running correctly

       * Check that the ``health`` for all devices is set to
         ``MAINTENANCE`` or ``RETIRED``.

       * Fail any running test jobs:

         .. code-block:: none

          $ lava-server manage jobs fail <job_id>

#. Check the logs to ensure that all services are running without errors.

#. If there are any devices on the master, put some of those devices online and
   run some health checks. If not, do as much of a check as possible on the
   master and then move to restoring the workers, if that is necessary.

#. Once all workers are restored and all devices are both online and have
   passed a health check, the restoration is complete. If a holding
   page was used, it can be taken down and the normal access to the
   instance restored to users.

Restoring a worker from backups
###############################

This is a much simpler process than a master (or a V1 worker which is
arguably more complex to restore than a master). Workers should only be
restored **after** the master has been restored and whilst all devices
are still in maintenance.

The only critical LAVA element for a worker to be restored from backup is the worker token:
``/var/lib/lava/dispatcher/worker/token``.

Other files may be required by specific labs and may already be handled by
configuration management, e.g.:

* ``/etc/ser2net.conf``.
* Local PDU scripts.
* ``udev`` rules for particular devices or services.

Once the base system has been restored and ``lava-dispatcher`` has been
installed at the same version as previously, the worker token can simply
be put back into place and ``lava-worker`` restarted.

.. code-block:: none

 $ sudo service lava-worker restart

The worker will now be able to respond to test job messages sent by the master.
