.. _debian_installation:

Debian-based distributions
##########################

These instructions cover Debian and all distributions based upon Debian,
including Ubuntu. The supported versions of Debian and Ubuntu are:

+---------------+------------------------+--------+---------------+
| Distribution  | Codename               | Number | Support       |
+===============+========================+========+===============+
| Debian        | experimental           | n/a    | Yes [#f1]_    |
+---------------+------------------------+--------+---------------+
| Debian        | sid                    | n/a    | Yes           |
+---------------+------------------------+--------+---------------+
| Debian        | stretch                | n/a    | [#f2]_        |
+---------------+------------------------+--------+---------------+
| Debian        | jessie                 | 8.0    | Yes [#f3]_    |
+---------------+------------------------+--------+---------------+
| Ubuntu        | vivid vervet (& later) | 15.04  | Yes [#f4]_    |
+---------------+------------------------+--------+---------------+
| Ubuntu        | utopic unicorn         | 14.10  | Yes [#f5]_    |
+---------------+------------------------+--------+---------------+
| Ubuntu        | trusty tahr LTS        | 14.04  | **No** [#f6]_ |
+---------------+------------------------+--------+---------------+

Debian uses names for `suites`_ (unstable, testing, stable & oldstable)
but the content of all suites except unstable will change codename once
a release of Debian stable is made. Once Jessie is released, the Debian
testing suite will gain the codename ``stretch`` and the oldstable suite
will have the codename ``wheezy`` (the name of the current stable suite),
so to prevent this table having to be updated every time there is a
Debian release, codenames are used.

`Ubuntu codenames`_ change with each 6 monthly release.
See :ref:`ubuntu_install`

.. _suites: http://en.wikipedia.org/wiki/Debian#Branches

.. _Ubuntu codenames: https://wiki.ubuntu.com/DevelopmentCodeNames

.. [#f1] `experimental`_ allows updates to be selected on top of
         unstable (or the current testing) during times when testing
         is frozen ahead of a release of Debian stable. Experimental
         will typically have no LAVA packages outside of a Debian
         release freeze.
.. [#f2] `stretch` is the name of the next Debian release after Jessie,
         which is supported automatically via uploads to sid (unstable).
.. [#f3] Jessie was released on April 25th, 2015. Uupdates to LAVA packages
         for jessie will be made using `jessie-backports`_.
.. [#f4] Ubuntu vivid vervet 15.04 was released on April
         23rd, 2015. LAVA packages automatically migrate from Debian
         into the current development release of Ubuntu. Once Ubuntu
         makes a release, the LAVA packages in that release do not
         receive updates.
.. [#f5] To install on Ubuntu, ensure the universe_ repository is enabled.

.. [#f6] Support for ``lava-server`` on Ubuntu Trusty 14.04LTS stopped at
         2015.9.post1. See :ref:`trusty_tahr_install`. Support for
         ``lava-dispatcher``on Ubuntu Trusty 14.04LTS stopped at 2015.9.

.. _experimental: https://wiki.debian.org/DebianExperimental

.. _universe: https://help.ubuntu.com/community/Repositories/CommandLine#Adding_the_Universe_and_Multiverse_Repositories

.. _jessie-backports: http://backports.debian.org/

You can track the versions of LAVA packages in the various Debian and
Ubuntu suites by following links from the Debian package trackers for
`lava-dispatcher <https://tracker.debian.org/pkg/lava-dispatcher>`_ and
`lava-server <https://tracker.debian.org/pkg/lava-server>`_.

.. _lava_repositories:

LAVA repositories
=================

As well as being uploaded to Debian, :ref:`production_releases` of LAVA
are uploaded to a Linaro `production-repo`_ repository which uses the
:ref:`lava_archive_signing_key` - a copy of the key is available in
the repository.

.. _production-repo: http://images.validation.linaro.org/production-repo/

In times when the current production release has not made it into
``jessie-backports`` (e.g. due to a migration issue in Debian), this
repository can be used instead. The **only** apt source to use with Debian
Jessie, Stretch or Sid is the `production-repo`_ for ``sid`` because the
same LAVA packages are used on Jessie and Stretch as on Sid::

 deb http://images.validation.linaro.org/production-repo sid main

.. note:: There are no packages currently in the repository
   except in ``sid``.

The codename ``sid`` is used simply as that is the codename for ``unstable``
which is where all Debian uploads arrive, so to allow the production repo
to include precisely the same upload as was made to Debian, we use
``sid``. It makes no difference to how the packages get installed on
Jessie, Stretch or Sid.

The :file:`services-trace.txt` file in the repository shows the latest
update timestamp and is accompanied by a GnuPG signature of the trace
file, signed using the :ref:`lava_archive_signing_key`.

.. _production_releases:

Production releases
===================

LAVA is currently packaged for Debian unstable using Django1.7 and
Postgresql. LAVA packages are now available from official Debian
mirrors for Debian unstable::

 $ sudo apt install postgresql
 $ sudo apt install lava-server

If the default Apache configuration from LAVA is suitable, you can
enable it immediately::

 $ sudo a2dissite 000-default
 $ sudo a2ensite lava-server.conf
 $ sudo service apache2 restart

Edits to the ``/etc/apache2/sites-available/lava-server.conf`` file
will not be overwritten by package upgrades unless the admin explicitly
asks ``dpkg`` to do so.

.. index:: tftpd-hpa

.. _tftp_support:

TFTP support requirement
------------------------

LAVA uses :term:`tftp` to serve files to a variety of device types.

The current dispatcher **relies** on TFTP downloads, NFS share directories
and master image downloads to **all** be made from a single directory:
:file:`/var/lib/lava/dispatcher/tmp`. To do this, the configuration file
for :command:`tftpd-hpa` needs to be modified to use the LAVA directory
instead of the default, ``/srv/tftp``.

.. note:: The TFTP support in LAVA has had to be changed from the
   **2015.8 release** onwards to stop LAVA enforcing a configuration
   change on the ``tftpd-hpa`` package without explicit configuration
   by the admin. Previously, installation may have prompted about
   changes in :file:`/etc/default/tftpd-hpa`, now this change needs
   to be made manually as the configuration of the ``tftpd-hpa`` package
   should not have been up to LAVA to impose. If you are already running
   a version of LAVA installed prior to the **2015.8 release** (and
   have working TFTP support), then the configuration change will have
   been imposed by LAVA and then maintained by ``dpkg`` and
   ``tftpd-hpa``. Check that your ``/etc/default/tftpd-hpa``
   file references :file:`/var/lib/lava/dispatcher/tmp` and continue
   as before.

Admins can either manually change the :file:`/etc/default/tftpd-hpa`
to set the ``TFTP_DIRECTORY`` to :file:`/var/lib/lava/dispatcher/tmp`
or copy the file packaged by ``lava-dispatcher``::

 $ sudo cp /usr/share/lava-dispatcher/tftpd-hpa /etc/default/tftpd-hpa

The change is required whichever Debian-based distribution you use as
your base install, including Ubuntu.

This behaviour has been fixed in the :term:`refactoring` such that
whatever location is configured for ``tftpd-hpa``, LAVA will use
temporary subdirectories in that location for all TFTP operations and
other LAVA operations will use the :file:`/var/lib/lava/dispatcher/tmp`
directory. The equivalent change was not practical to implement in the
current dispatcher. If **all** of your devices are :term:`exclusive`, to
the :term:`pipeline`, then the ``tftpd-hpa`` configuration can be set to
the tftpd original value (``/srv/tftp``), the LAVA historical value
(``/var/lib/lava/dispatcher/tmp``) or another directory specified by
the admin.

Extra dependencies
------------------

The ``lava`` package brings in extra dependencies which may be useful
on some instances.

.. note:: Some dependencies of the ``lava`` package require the addition
          of the Linaro Tools PPA. See https://launchpad.net/~linaro-maintainers/+archive/tools
          for more information - click on ``Technical details about this PPA``
          to get information on the apt sources required to use it.
          :ref:`linaro_tools_ppa`.


.. _install_debian_jessie:

Installing on Debian Jessie
---------------------------

Debian Jessie was released on April 25th, 2015, containing a full set
of packages to install LAVA.

Updates are uploaded to `jessie-backports <http://backports.debian.org/>`_

::

 deb http://http.debian.net/debian jessie-backports main

.. _lava_archive_signing_key:

LAVA Archive signing key
^^^^^^^^^^^^^^^^^^^^^^^^

::

 pub  2048R/C77102A9 2014-06-06 LAVA build daemon (Staging) <lava-lab@linaro.org>
      Key fingerprint = 45AD 50DC 41AE D421 FF5B  33D4 ECF3 C05C C771 02A9
 uid                  LAVA build daemon (Staging) <lava-lab@linaro.org>

Each of the support archives on ``images.validation.linaro.org`` is
signed using same key, 0xC77102A9, which can be downloaded_ and added to
apt::

 $ wget http://images.validation.linaro.org/staging-repo/staging-repo.key.asc
 $ sudo apt-key add staging-repo.key.asc
 OK

Then update to locate the required dependencies::

 $ sudo apt-get update

.. _downloaded: http://images.validation.linaro.org/staging-repo/staging-repo.key.asc

Installing just lava-server
===========================

The ``lava-server`` package is the main LAVA scheduler and frontend.

To install just the lava-server from the current packages, use::

 $ sudo apt-get install lava-server
 $ sudo a2dissite 000-default
 $ sudo a2ensite lava-server.conf
 $ sudo service apache2 restart

This will install lava-dispatcher and lava-server.

Other packages to consider:

* ``lavapdu-client`` to control a :term:`PDU` to allow LAVA to
  automatically power cycle a device.
* ``lavapdu-daemon`` - only one daemon is required to run multiple PDUs.
* ``ntp`` - some actions within LAVA can be time-sensitive, so ensuring
  that devices within your lab keep time correctly can be important.
* linaro-image-tools which provides ``linaro-media-create`` for tests
  which use hardware packs from Linaro

Installing the full lava set
============================

Production installs of LAVA will rarely use the full ``lava`` set as
it includes tools more commonly used by developers and test labs. These
tools mean that the ``lava`` package brings more dependencies than
when installing ``lava-server`` to run a production LAVA instance.

The ``lava`` package installs support for:

* ``lava-dev`` - scripts to build developer packages based on your current
  git tree of ``lava-server`` or ``lava-dispatcher``, including any local changes.
* linaro-image-tools which provides ``linaro-media-create`` for tests
  which use hardware packs from Linaro
* ``vmdebootstrap`` for building your own Debian based KVM images.
* ``lavapdu-client`` to control a :term:`PDU` to allow LAVA to
  automatically power cycle a device.
* ``lavapdu-daemon`` is recommended or you can use a single daemon
  for multiple PDUs.
* ``ntp`` - some actions within LAVA can be time-sensitive, so ensuring
  that devices within your lab keep time correctly can be important.

All of these packages can be installed separately alongside the main
``lava-server`` package, the ``lava`` package merely collects them into
one set.
::

 $ sudo apt-get install postgresql
 $ sudo apt-get install lava
 $ sudo a2dissite 000-default
 $ sudo a2ensite lava-server.conf
 $ sudo service apache2 restart

Upgrading LAVA packages on Jessie
---------------------------------

Updates are uploaded to `jessie-backports <http://backports.debian.org/>`_

::

 deb http://http.debian.net/debian jessie-backports main

.. _linaro_tools_ppa:

Adding the Linaro Tools PPA
---------------------------

To get updated versions of linaro-media-create and other
optional packages which come from the Linaro PPA, use the apt source::

 deb http://ppa.launchpad.net/linaro-maintainers/tools/ubuntu precise main

The PPA uses this signing key::

 http://keyserver.ubuntu.com:11371/pks/lookup?search=0x1DD749B890A6F66D050D985CF1FCBACA7BE1F97B&op=index

.. _ubuntu_install:

Installing on Ubuntu
====================

LAVA recommends the use of Debian - Ubuntu installs are possible but
may not receive updates of the LAVA packages. See :ref:`lava_on_debian`
for information on building LAVA packages of your own.

Always ensure that the Ubuntu universe_ repository is enabled on all
Ubuntu instances before installing LAVA.

.. _ubuntu_unicorn:

Installing on Ubuntu Utopic Unicorn and later
---------------------------------------------

Ubuntu Unicorn 14.10 includes all packages needed by LAVA
up to the 2014.07 release. Subsequent releases of Ubuntu will contain
newer versions of LAVA and LAVA dependencies.

Installing on Unicorn and Ubuntu releases newer than Unicorn 14.10
is the same as :ref:`install_debian_jessie`.

Future production releases of LAVA will be uploaded to Debian and then
migrate into the current Ubuntu development release. The full set of
architectures are supported, just as with Debian Jessie.

See also :ref:`lava_on_debian` for information on building updated LAVA
packages on your own, LAVA will not be making backports to Ubuntu.

.. _trusty_tahr_install:

Ubuntu Trusty Tahr 14.04 LTS
----------------------------

.. warning:: Support for Ubuntu Trusty 14.04LTS was **frozen** at
   2015.9.post1 for ``lava-server`` and 2015.9 for ``lava-dispatcher``.
   **No** further updates will be made for Trusty and no new installs
   (master or remote worker) should be made on Trusty.

Setting up a reverse proxy
==========================

In order to use lava-server behind a reverse proxy, configure lava-server as
usual and then setup a reverse proxy using Apache.
The folowing Apache configuration will work for most setup::

 ProxyPass / http://lava_server_dns:port/
 ProxyPassReverse / http://lava_server_dns:port/
 ProxyPreserveHost On
 RequestHeader set X-Forwarded-Proto "https" env=HTTPS

This configuration will work when proxifying::

  http://example.com/ => http://lava.example.com/

If you want the application to answer on a specific base URL, configure
lava-server to answer on this base URL and then configure the reverse proxy to
proxify the same base URL.
For instance you can have::

  http://example.com/lava => http://lava.example.com/lava

Having two differents base URLs is difficult to setup due to a limitation in
the Django framework. In this case you will have to also setup Apache modules,
like `Substitute` to alter the HTML content on the fly. This is obviously not a
recommended setup.

.. _create_superuser:

Superuser
=========

OpenID or LDAP
--------------
In LAVA instances that use external authentication mechanisms such as
OpenID or LDAP, login once with the user account that has to be
granted superuser privileges on LAVA web UI. After logging in with
OpenID or LDAP successfully, make use of the following command to make
this user a superuser::

  $ sudo lava-server manage authorize_superuser {username}

.. note:: `{username}` is the username of OpenID or LDAP user.

LDAP
----
In LAVA instances that use LDAP as authentication mechanism, the
`addldapuser` command can be used to populate a user from LDAP and
also grant superuser privilege as follows::

  $ sudo lava-server manage addldapuser {username} --superuser

.. note:: `{username}` is the username of LDAP user.

Local Django Account
--------------------
A default lavaserver superuser is setup during package installation with
a random password. The default superuser is not the same as the lavaserver
system user nor the postgres user (despite the name)::

 $ sudo lava-server manage createsuperuser --username default --email=$EMAIL

This will prompt for name, email address and password.

You can always delete this user later, but at least it gets
you a default [sic] admin user with a password you know.

To change the password of the dummy superuser, login as this new superuser
at ``http://localhost/admin`` and select Users in the administrator interface.
Selecting lavaserver brings up the details of the installation superuser
and below the password field is a link to change the password without
needing to know the random password.

To delete the dummy superuser, login as this new superuser at
``http://localhost/admin`` and select Users in the administrator interface.
Select lavaserver and click the `Delete` link at the bottom of the page.

.. note:: The above superuser created with `createsuperuser` command
          will be added as a local Django user account, in other words
          the user account lives on the LAVA instance's database, even
          if the LAVA instance uses external authentication mechanisms
          such as OpenID or LDAP.

An existing local Django superuser account can be upgraded to an LDAP
user account without losing data, using the `mergeldapuser` command,
provided the LDAP username does not already exist in the LAVA
instance::

  $ sudo lava-server manage mergeldapuser <lava_user> <ldap_user>

