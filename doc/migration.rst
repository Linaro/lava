Migrating from lava-deployment-tool to packages
***********************************************

There are two main migrations methods:

#. Upgrading Ubuntu from precise to trusty
#. Replacing precise with Debian testing

Either involves moving the (possibly large) amount of files in
the LAVA log directories, so a backup of those files would be
useful.

.. warning:: A backup of the entire server is also recommended as there is
             **no support for downgrading** from packaging back to
             lava-deployment-tool.

Upgrading Ubuntu to Trusty Tahr 14.04LTS
########################################

Once migrated to Trusty and using packages, the OS can be further
upgraded to Utopic Unicorn and subsequent releases in much the same way
(currently, there is no postgresql change between Trusty and Utopic).
Utopic will synchronise the LAVA packages directly with Debian, so there
will be no need to use a separate repository.

Assumptions
===========

#. LAVA is already installed using ``lava-deployment-tool`` on
   Ubuntu Precise Pangolin 12.04LTS in ``/srv/lava/instances/``
#. postgresql9.1 is installed and running on port 5432::

    ls -a /var/run/postgresql/

#. there are idle devices or possibly running test jobs

Requirements
============

To copy the test job log files to the new location, it can be useful
to have ``rsync`` installed on each machine, it is not normally part
of a LAVA install.

The only parts of the existing LAVA instance which will be retained are:

* The test job log output, bundles and attachments::

   /srv/lava/instances/<INSTANCE>/var/lib/lava-server/media/

* The database (master instance only)

Preparing for the upgrade
=========================

#. Declare a maintenance window for scheduled downtime.
#. Take all devices offline using the Django admin interface.
#. Complete all :ref:`remote_worker_upgrade` tasks before restarting
   LAVA on the master instance.

.. _master_instance_upgrade:

Master instance upgrade
=======================

#. Stop lava::

    sudo service lava stop

#. Stop apache::

    sudo service apache2 stop

   .. tip:: Alternatively, re-enable the default apache configuration
            to continue serving pages and put up a "maintenance page".
            Apache will restart during the upgrade but this will be
            only for a brief period.

#. Remove postgresql-9.1 without dropping the cluster::

    sudo service postgresql stop

   This allows the upgrade to install postgresql-9.3, use port 5432
   for 9.3 and automatically migrate the 9.1 cluster to 9.3.

#. Change apt sources. Other references to precise and precise-updates
   may also need to change - the principle change is to trusty or
   utopic. Ensure that the universe component is selected::

    deb http://archive.ubuntu.com/ubuntu trusty main universe

   Alternatively, change all the references in the current file
   from ``precise`` to ``utopic``. Remember to check for any other
   apt sources in ``/etc/apt/sources.list.d/``, e.g.::

    /etc/apt/sources.list.d/linaro-maintainers-tools-precise.list

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

   .. tip:: ``apt`` has migrated to version 1.0 in Trusty, which means
            that some commands can now be run as just ``apt`` as well as
            the previous ``apt-get``. See man 1 apt after the upgrade.

#. Remove ``lava-deployment-tool`` - this may seem premature but
   deployment-tool is unusable on Trusty or later and would undo some
   of the changes implemented via the packaging if it was run by mistake.

#. Migrate to Postgresql9.3

   Do not remove postgresql-9.1 until the cluster has been migrated.
   To migrate the cluster, both versions need to be installed - 9.1
   can be removed after the migration (9.1 will not be able to use the
   9.3 cluster). With 9.1 installed, apt will automatically install 9.3::

    sudo service postgresql stop
    sudo pg_dropcluster --stop 9.3 main
    sudo pg_upgradecluster 9.1 main

   You can check the new cluster using ``psql``::

    sudo su postgres
    psql
     psql (9.3.4)
     ...
    postgres=# \l
     lava-production | lava-production | UTF8     | en_US.UTF-8 | en_US.UTF-8 |
     ...
    postgres=# \q
    exit

   Now drop the 9.1 cluster and remove 9.1::

    sudo pg_dropcluster 9.1 main
    sudo apt-get remove postgresql-9.1 postgresql-client-9.1

   Ubuntu Precise has a buggy postgresql-client-9.1 package which does
   not remove cleanly::

    sudo dpkg -P postgresql-contrib-9.1

   Check that the default postgresql port is 5432::

    grep port /etc/postgresql/9.3/main/postgresql.conf

   You can check the migration using ``psql``::

    sudo su postgres
    psql
     psql (9.3.4)
     ...
    postgres=# \l
     lava-production | lava-production | UTF8     | en_US.UTF-8 | en_US.UTF-8 |
     ...
    postgres=# \q
    exit

#. Clean-up after the upgrade.

   Apache has been upgraded to 2.4, so apache2.2 can be safely removed::

    sudo apt-get --purge autoremove

#. Add the LAVA packaging repository.

   This will remain necessary on Trusty (although the path and keyring
   may change to an official repository) but on Ubuntu Utopic Unicorn
   and later releases, the necessary packages will migrate automatically
   from Debian::

    sudo apt install emdebian-archive-keyring
    sudo vim /etc/apt/sources.list.d/lava.list

   The repository is at::

    deb http://people.linaro.org/~neil.williams/ubuntu trusty main

#. Migrate the instance configuration to the packaging location.

   The packages will respect an existing LAVA configuration, if the relevant
   files are in the correct location ``/etc/lava-server/instance.conf``::

    sudo mkdir -p /etc/lava-server/
    sudo cp /srv/lava/instances/<INSTANCE>/etc/lava-server/instance.conf /etc/lava-server/instance.conf

   Convert the LAVA_PREFIX to the FHS compliant path::

    LAVA_PREFIX="/var/lib/lava-server/"

   Some settings are no longer used by the packaging but these will simply
   be ignored by the packaging.

#. Migrate the instance logfiles to the packaging location.

   The permissions on these files will be fixed once ``lava-server`` is
   installed. Depending on the amount of files, the simplest way to
   migrate the files may be to use rsync::

    sudo rsync -vaz /srv/lava/instances/<INSTANCE>/var/lib/lava-server/media/* /var/lib/lava-server/default/media/

#. Install LAVA from packages::

    sudo apt update
    sudo apt install lava-server

   The install will prompt for the instance name, you can specify the
   same instance name as the original lava-deployment-tool instance but
   this no longer affects where files are actually installed, nor does
   it affect the database name or database user. The instance name
   becomes a simple label with the packaging upgrade.

#. Pause while completing the :ref:`remote_worker_upgrade`, if relevant.

#. Run forced healthchecks on devices

#. Return devices to Online

#. Complete scheduled maintenance.


.. _remote_worker_upgrade:

Remote worker upgrade
=====================

This is essentially the same as a :ref:`master_instance_upgrade`
without any database work.

#. Stop lava::

    sudo service lava stop

#. Stop apache::

    sudo service apache2 stop

#. Change apt sources. Other references to precise and precise-updates
   may also need to change - the principle change is to trusty or
   utopic. Ensure that the universe component is selected::

    deb http://archive.ubuntu.com/ubuntu trusty main universe

   Alternatively, change all the references in the current file
   from ``precise`` to ``utopic``. Remember to check for any other
   apt sources in ``/etc/apt/sources.list.d/``, e.g.::

    /etc/apt/sources.list.d/linaro-maintainers-tools-precise.list

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

   .. tip:: ``apt`` has migrated to version 1.0 in Trusty, which means
            that some commands can now be run as just ``apt`` as well as
            the previous ``apt-get``. See man 1 apt after the upgrade.

#. Remove ``lava-deployment-tool`` - this may seem premature but
   deployment-tool is unusable on Trusty or later and would undo some
   of the changes implemented via the packaging if it was run by mistake.

#. Clean-up after the upgrade.

   Apache has been upgraded to 2.4, so apache2.2 can be safely removed::

    sudo apt-get --purge autoremove

#. Add the LAVA packaging repository.

   This will remain necessary on Trusty (although the path and keyring
   may change to an official repository) but on Ubuntu Utopic Unicorn
   and later releases, the necessary packages will migrate automatically
   from Debian::

    sudo apt install emdebian-archive-keyring
    sudo vim /etc/apt/sources.list.d/lava.list

   The repository is at::

    deb http://people.linaro.org/~neil.williams/ubuntu trusty main

#. Migrate the instance configuration to the packaging location.

   The packages will respect an existing LAVA configuration, if the relevant
   files are in the correct location ``/etc/lava-server/instance.conf``::

    sudo mkdir -p /etc/lava-server/
    sudo cp /srv/lava/instances/<INSTANCE>/etc/lava-server/instance.conf /etc/lava-server/instance.conf

   Convert the LAVA_PREFIX to the FHS compliant path::

    LAVA_PREFIX="/var/lib/lava-server/"

   Some settings are no longer used by the packaging but these will simply
   be ignored by the packaging.

#. Migrate the instance logfiles to the packaging location.

   The permissions on these files will be fixed once ``lava-server`` is
   installed. Depending on the amount of files, the simplest way to
   migrate the files may be to use rsync::

    sudo rsync -vaz /srv/lava/instances/<INSTANCE>/var/lib/lava-server/media/* /var/lib/lava-server/default/media/

#. Install LAVA from packages::

    sudo apt update
    sudo apt install lava-server

    Ensure you specify that this is not a single master instance when
    prompted by debconf.

   The install will prompt for the instance name, you can specify the
   same instance name as the original lava-deployment-tool instance but
   this no longer affects where files are actually installed, nor does
   it affect the database name or database user. The instance name
   becomes a simple label with the packaging upgrade.

   The other details which will be needed during installation are available
   in the ``instance.conf`` of the original worker. Enter the details
   when prompted. See :ref:`distributed_deployment`.

Upgrading Ubuntu to Debian Jessie (testing)
###########################################

It is possible to upgrade from Ubuntu to Debian but it is not recommended
as it may end up with a mix of package setups and an unexpected final
configuration. Most of the steps are similar to the Ubuntu upgrade
steps and these instructions also cover if you choose to make a
fresh install of Ubuntu Trusty Tahr 14.04LTS.

The data needed off the old Precise instance will be:

#. The test job data::

    /srv/lava/instances/<INSTANCE>/var/lib/lava-server/media/*

#. The database (exceot for remote workers)

#. The instance configuration::

    /srv/lava/instances/<INSTANCE>/etc/lava-server/instance.conf

To switch the OS, it may be best to retire the old machine / VM and
put it onto a different network address and hostname. Then dump the
postgres database and create a backup of the test job data.

The choice between using Jessie and Sid is entirely down to you.
There is no particular reason to upgrade to jessie as a route to
unstable, you can just go from wheezy to unstable, especially with
a server-based install without a graphical user interface.

Installing LAVA on Debian
=========================

The process does not differ greatly from the standard installation
instructions for :ref:`debian_installation`. The extra stages occur
between installation of the base system and installation of the LAVA
packages.

#. Download an ISO for Debian 7.0 Wheezy from http://www.debian.org/

#. Install on required machine

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

   .. tip:: ``apt`` has migrated to version 1.0 in Trusty, which means
            that some commands can now be run as just ``apt`` as well as
            the previous ``apt-get``. See man 1 apt after the upgrade.

#. Clean-up after the upgrade.

   Apache has been upgraded to 2.4, so apache2.2 can be safely removed::

    sudo apt-get --purge autoremove

#. Add the LAVA packaging repository.

   This will remain necessary on Trusty (although the path and keyring
   may change to an official repository) but on Ubuntu Utopic Unicorn
   and later releases, the necessary packages will migrate automatically
   from Debian::

    sudo apt install emdebian-archive-keyring
    sudo vim /etc/apt/sources.list.d/lava.list

   The repository is at::

    deb http://people.linaro.org/~neil.williams/lava jessie main

#. Migrate the instance configuration to the packaging location.

   The packages will respect an existing LAVA configuration, if the relevant
   files are in the correct location ``/etc/lava-server/instance.conf``.
   Copy the ``instance.conf`` from the precise box to the new Debian
   machine and put into place::

    sudo mkdir -p /etc/lava-server/
    sudo cp /tmp/instance.conf /etc/lava-server/instance.conf

   Convert the LAVA_PREFIX to the FHS compliant path::

    LAVA_PREFIX="/var/lib/lava-server/"

   Some settings are no longer used by the packaging but these will simply
   be ignored by the packaging.

#. Migrate the instance logfiles to the packaging location.

   The permissions on these files will be fixed once ``lava-server`` is
   installed. Depending on how the files were copied from the Ubuntu
   machine, the files can be decompressed directly into the new
   location.

#. Install LAVA from packages::

    sudo apt update
    sudo apt install lava-server

   The install will prompt for the instance name, you can specify the
   same instance name as the original lava-deployment-tool instance but
   this no longer affects where files are actually installed, nor does
   it affect the database name or database user. The instance name
   becomes a simple label with the packaging upgrade.
