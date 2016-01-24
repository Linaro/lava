.. _migrating_from_deployment_tool:

Migrating from lava-deployment-tool to packages
***********************************************

Please read the section on :ref:`packaging_components` for details of
how the LAVA packaging is organised. In particular, note the section
on :ref:`packaging_daemon_renaming`.

Only Debian Jessie is supported for new migrations.

#. Replacing precise with Debian Jessie

Either involves moving the (possibly large) amount of files in
the LAVA log directories, so a backup of those files would be
useful.

.. warning:: A backup of the entire server is also recommended as there is
             **no support for downgrading** from packaging back to
             lava-deployment-tool.

The best method for any one installation will depend on the local admins.
A fresh install is often faster than an upgrade from one LTS to another,
as long as the database export process is reliable. If there is a lot of
data on the machine besides LAVA content, there will need to be some
consideration of how a kernel and OS upgrade will affect those other
services.

Due to limitations within ``lava-deployment-tool`` and ``lava-manifest``,
there is no way to migrate to the packaging based on django1.6 using
the tools already installed within the existing LAVA instance.

.. note:: A default LAVA install from packages supports ``http://``, not
          ``https://`` in the Apache configuration. If your existing
          instance uses ``https://``, ensure you have a copy of the
          apache configuration and remember to port those changes to
          apache2.4 in ``/etc/apache2/sites-available/lava-server.conf``.

.. _postgres_export:

Exporting the postgres database
###############################

Most admins will have custom ways to get a dump of the postgres
database and any script which can dump the data and import it
successfully into a fresh, upgraded, install will be suitable.

``lava-deployment-tool`` would have read variables from the
``instance.conf`` and used a call based on::

   $ pg_dump \
        --no-owner \
        --format=custom \
        --host=$dbserver \
        --port=$dbport \
        --username=$dbuser \
        --no-password $dbname \
        --schema=public \
        > "$destdir/database.dump"

A new install will need the database user created::

    sudo -u postgres createuser \
        --no-createdb --encrypted \
        --login --no-superuser \
        --no-createrole --no-password \
        --port $dbport $dbuser
    sudo -u postgres psql --port 5432 \
        --command="ALTER USER \"lavaserver\" WITH PASSWORD '$dbpass';"


``lava-deployment-tool`` would attempt a restore from this dump by
using the variables from ``instance.conf`` and calls based on::

    sudo -u postgres dropdb \
        --port $dbport \
        $dbname || true
    sudo -u postgres createdb \
        --encoding=UTF-8 \
        --locale=en_US.UTF-8 \
        --template=template0 \
        --owner=$dbuser \
        --port $dbport \
        --no-password \
        $dbname
    sudo -u postgres createlang \
        --port $dbport \
        plpgsql \
        $dbname || true
    sudo -u postgres pg_restore \
        --exit-on-error --no-owner \
        --port $dbport \
        --role $dbuser \
        --dbname $dbname \
        "${1}" > /dev/null

.. tip:: If your database is very large, consider adding the ``--jobs``
         option to ``pg_restore`` to parallelise the postgresql workload.
         See the postgresql documentation (``man 1 pg_restore``) for the
         best value to pass as the number of concurrent jobs to use.

Whatever method is chosen, verify that the dump from ``postgresql-9.1``
can be successfully imported into ``postgresql-9.3`` then check the
migration by connecting to the new database using the username, database
name and password specified in ``instance.conf`` and check for the
relevant tables. e.g.::

 sudo su postgres lavaserver
 psql
  psql (9.3.4)
  ...
 postgres=# \l
  lava-production | lava-production | UTF8     | en_US.UTF-8 | en_US.UTF-8 |
  ...
 postgres=# \dt
   ...
    public | dashboard_app_attachment                   | table | lavaserver
   ...
 postgres=# \q

.. _assumptions:

Assumptions
###########

#. LAVA is already installed using ``lava-deployment-tool`` on
   Ubuntu Precise Pangolin 12.04LTS in ``/srv/lava/instances/``
#. postgresql9.1 is installed and running on port 5432::

    ls -a /var/run/postgresql/

#. there are idle devices or possibly running test jobs

#. any local buildouts are either removed or merged back to
   master and updated. (This is a precaution to ensure that
   there are no development changes like database migrations which
   exist only in the buildout and not in master.)

.. _requirements:

Requirements
############

To copy the test job log files to the new location, it can be useful
to have ``rsync`` installed on each machine, it is not always part
of a LAVA install.

The only parts of the existing LAVA instance which will be retained are:

* The test job log output, bundles and attachments::

   /srv/lava/instances/<INSTANCE>/var/lib/lava-server/media/

* The database (master instance only) See :ref:`postgres_export`.

* The device configuration files::

   /srv/lava/instances/<INSTANCE>/etc/lava-dispatcher/devices/
   /srv/lava/instances/<INSTANCE>/etc/lava-dispatcher/device-types/

* The lava-server instance.conf file::

   /srv/lava/instances/<INSTANCE>/etc/lava-server/instance.conf

Other configuration files are ported or generated by the packaging.

Preparing for the upgrade
#########################

#. Declare a maintenance window for scheduled downtime.
#. Take all devices offline using the Django admin interface. Wait for
   any devices in status ``GoingOffline`` to complete the test job or
   cancel the test job if necessary.
#. Ensure suitable backups exist for the database, device configuration,
   test job output files and the ``instance.conf``.
#. Ensure the machine has enough free space for a large set of package
   downloads. Ensure that the master instance also has enough free space
   for a copy of the test job output directories.
#. Incorporate into the plan for the upgrade that the master will need
   to be upgraded but then work will need to concentrate on all the
   remote_worker_upgrade tasks before restarting the ``lava-server``
   service on the master instance or putting any devices back online.
#. Exit out of all shells currently using the ``/srv/lava/instances/<INSTANCE>/bin/activate``
   virtual environment settings.
#. Ensure that any local buildouts are either removed or merged back to
   master and updated. (This is a precaution to ensure that
   there are no development changes like database migrations which
   exist only in the buildout and not in master.)

Select the upgrade path:
========================

Only Debian Jessie is supported as the upgrade path for LAVA releases
after 2015.9

.. _debian_jessie:

Upgrading LAVA to Debian Jessie
###############################

See :ref:`install_debian_jessie`.

The recommended method to upgrade LAVA to Debian is to backup critical
data on the Ubuntu Precise machine and then install a fresh Debian
install. See :ref:`requirements`.

It is possible to upgrade from Ubuntu to Debian but it is not recommended
as it may end up with a mix of package setups and an unexpected final
configuration.

Most of the steps are similar to the Ubuntu upgrade steps and these
instructions also cover if you choose to make a fresh install of
Ubuntu Trusty Tahr 14.04LTS.

The data needed off the old Precise instance will be:

#. The test job data::

    /srv/lava/instances/<INSTANCE>/var/lib/lava-server/media/*

#. The database (except for remote workers) See :ref:`postgres_export`.

   * The device configuration files::

     /srv/lava/instances/<INSTANCE>/etc/lava-dispatcher/devices/
     /srv/lava/instances/<INSTANCE>/etc/lava-dispatcher/device-types/

#. The instance configuration::

    /srv/lava/instances/<INSTANCE>/etc/lava-server/instance.conf

To switch the OS, it may be best to retire the old machine / VM and
put it onto a different network address and hostname. Then dump the
postgres database and create a backup of the test job data.

The choice between using Jessie and Sid is entirely down to you.
There is no particular reason to upgrade to jessie as a route to
unstable, you can just go from wheezy to unstable, especially with
a server-based install without a graphical user interface.

.. _install_lava_master_debian:

Installing a LAVA master instance on Debian
===========================================

The process does not differ greatly from the standard installation
instructions for :ref:`debian_installation`. The extra stages occur
between installation of the base system and installation of the LAVA
packages.

#. Download an ISO for Debian 7.5 Wheezy from http://www.debian.org/

#. Install on required machine - no need for a desktop environment and
   the database installation is best left until after the upgrade to
   Jessie. ``openssh-server`` would be useful.

#. Edit the apt sources list to point at jessie instead of wheezy::

   $ sudo vim /etc/apt/sources.list

#. update, upgrade and then dist-upgrade::

    sudo apt-get update
    sudo apt-get upgrade
    sudo apt-get dist-upgrade
    sudo apt-get autoclean

   Avoid making manual changes between the ``upgrade`` and
   ``dist-upgrade`` steps - glibc will be upgraded and some daemons will
   need to be restared, this is best done automatically when prompted
   by debconf.

   The upgrade will bring in a new kernel, so a reboot is recommended
   at this point.

   .. tip:: ``apt`` has migrated to version 1.0 in Jessie, which means
            that some commands can now be run as just ``apt`` as well as
            the previous ``apt-get``. See man 1 apt after the upgrade.

#. Clean-up after the upgrade.

   Apache has been upgraded to 2.4, so apache2.2 is one of many
   packages which can be safely removed::

    sudo apt-get --purge autoremove

#. Add the LAVA packaging repository.

   All packages are in the Jessie release, this step is no longer
   required.

#. Migrate the instance configuration to the packaging location.

   The packages will respect an existing LAVA configuration, if the relevant
   files are in the correct location ``/etc/lava-server/instance.conf``.
   Copy the ``instance.conf`` from the precise box to the new Debian
   machine and put into place. e.g.::

    sudo mkdir -p /etc/lava-server/
    sudo cp /tmp/instance.conf /etc/lava-server/instance.conf

   Convert the LAVA_PREFIX in `/etc/lava-server/instance.conf`
   to the `FHS`_ (Filesystem Hierarchy Standard) compliant path::

    LAVA_PREFIX="/var/lib/lava-server/"

   Some settings are no longer used by the packaging but these will simply
   be ignored by the packaging.

#. Migrate the instance logfiles to the packaging location.

   The permissions on these files will be fixed once ``lava-server`` is
   installed. Depending on how the files were copied from the Ubuntu
   machine, the files can be decompressed directly into the new
   location.

#. Import the postgres database dump.

   Use the values in the ``/etc/lava-server/instance.conf`` to import
   the postgres data with the correct username, password and database
   access.

#. Install LAVA from packages::

    sudo apt update
    sudo apt install lava-server

   The install will prompt for the instance name, you can specify the
   same instance name as the original lava-deployment-tool instance but
   this no longer affects where files are actually installed, nor does
   it affect the database name or database user. The instance name
   becomes a simple label with the packaging upgrade.

#. Enable the lava-server apache configuration::

    sudo a2dissite 000-default
    sudo a2ensite lava-server
    sudo service apache2 restart

#. Check your :term:`tftp` support - see :ref:`tftp_support`.

#. Restart daemons affected by the installation::

    sudo service tftpd-hpa restart

#. Ensure all devices remain offline.

#. Configure the master to work with a remote worker.

See :ref:`remote_database` and :ref:`example_postgres`. Remember to
use the ``LAVA_DB_USER`` and ``LAVA_DB_NAME`` from the ``instance.conf``
on the master. e.g.::

 host    lava-playground    lava-playground    0.0.0.0/0    md5

#. Pause to :ref:`remote_worker_debian`.

#. Run forced healthchecks on devices.

#. Return devices to ``Online`` status.

#. Complete scheduler maintenance.

.. _fhs: http://www.pathname.com/fhs/

.. _remote_worker_debian:

Install a LAVA remote worker using Debian
==========================================

The process does not differ greatly from the standard installation
instructions for :ref:`debian_installation`. The extra stages occur
between installation of the base system and installation of the LAVA
packages.

#. Download an ISO for Debian 7.5 Wheezy from http://www.debian.org/

#. Install on required machine - no need for a desktop environment,
   ``openssh-server`` would be useful.

#. Change apt sources to point at jessie instead of wheezy::

    /etc/apt/sources.list

#. update, upgrade and then dist-upgrade::

    sudo apt-get update
    sudo apt-get upgrade
    sudo apt-get dist-upgrade
    sudo apt-get autoclean

   Avoid making manual changes between the ``upgrade`` and
   ``dist-upgrade`` steps - glibc will be upgraded and some daemons will
   need to be restared, this is best done automatically when prompted
   by debconf.

   The upgrade will bring in a new kernel, so a reboot is recommended
   at this point.

   .. tip:: ``apt`` has migrated to version 1.0 in Jessie, which means
            that some commands can now be run as just ``apt`` as well as
            the previous ``apt-get``. See man 1 apt after the upgrade.

#. Clean-up after the upgrade.

   Apache has been upgraded to 2.4, so apache2.2 is one of many
   packages which can be safely removed::

    sudo apt-get --purge autoremove

#. Add the LAVA packaging repository.

   All packages are in the Jessie release, this step is no longer
   required.

#. Migrate the instance configuration to the packaging location.

   The packages will respect an existing LAVA configuration but still ask
   the questions, so keep a terminal window open with the values.
   Copy the ``instance.conf`` from the precise box to the new Debian
   machine and put into place. e.g.::

    sudo mkdir -p /etc/lava-server/
    sudo cp /tmp/instance.conf /etc/lava-server/instance.conf

   Convert the LAVA_PREFIX in `/etc/lava-server/instance.conf`
   to the `FHS`_ (Filesystem Hierarchy Standard) compliant path::

    LAVA_PREFIX="/var/lib/lava-server/"

   Some settings are no longer used by the packaging but these will simply
   be ignored by the packaging.

#. **Do not migrate the instance logfiles** to the packaging location.

   There is no ``rsync`` operation on a remote worker - the files are
   on an sshfs from the master. Ensure that ``/var/lib/lava-server/default/media``
   is empty and that there is no current sshfs mount.

#. Install LAVA from packages::

    sudo apt update
    sudo apt install lava-server

   The install will prompt for the instance name, you can specify the
   same instance name as the original lava-deployment-tool instance but
   this no longer affects where files are actually installed, nor does
   it affect the database name or database user. The instance name
   becomes a simple label with the packaging upgrade.

#. Configure the remote worker

   See :ref:`configuring_remote_worker` to setup the SSH key, the ``fuse``
   configuration and ``lava-coordinator``.

   Restart the ``lava-server`` daemon once done and check that the SSHFS
   mount operations has worked. See :ref:`check_sshfs_mount`.

#. Enable apache on the remote worker.

   This is used to serve modified files to the devices::

    sudo a2dissite 000-default
    sudo a2ensite lava-server
    sudo service apache2 restart

#. Check your :term:`tftp` support - see :ref:`tftp_support`.

#. Restart daemons affected by the installation::

    sudo service tftpd-hpa restart

#. Return to :ref:`install_lava_master_debian`.
