.. index:: debian, installation, install

.. _debian_installation:

Installing on a Debian system
*****************************

.. seealso:: :ref:`archiving_v1`

These instructions cover installation on Debian. The supported versions are:

+---------------+------------------------+--------+----------------------+
| Distribution  | Codename               | Number | Support              |
+===============+========================+========+======================+
| Debian        | experimental           | n/a    | Yes [#f1]_           |
+---------------+------------------------+--------+----------------------+
| Debian        | Sid (unstable)         | n/a    | Yes                  |
+---------------+------------------------+--------+----------------------+
| Debian        | Buster (testing)       | n/a    | Yes [#f4]_           |
+---------------+------------------------+--------+----------------------+
| Debian        | Stretch (stable)       | 9.0    | Yes [#f2]_           |
+---------------+------------------------+--------+----------------------+
| Debian        | Jessie (oldstable)     | 8.0    | Deprecated [#f3]_    |
+---------------+------------------------+--------+----------------------+

Debian uses codenames for releases (buster, stretch, jessie, wheezy,
squeeze) and names for `suites`_ (unstable, testing, stable &
oldstable). When a new Debian major release is made, the packages in
"testing" are frozen and become the new "stable". A new codename is
chosen for the new "testing" suite, and that will be the name for the
next major release in the cycle.

To allow the table to refer to the same package versions consistently over
time, codenames are used here. When a Debian release is made, a new codename is
applied to the testing suite and LAVA releases after that point will include
that codename in the table.

.. note:: LAVA used to be supported on Ubuntu directly, but is not any more due
   to lack of resources to maintain and test that support. Support may be
   re-instated if more effort becomes available in the future. The last version
   of LAVA supported in Ubuntu was **2015.9.post1**.

.. _suites: http://en.wikipedia.org/wiki/Debian#Branches

.. [#f1] `experimental`_ allows updates to be selected on top of unstable (or
         the current testing) during times when testing is frozen ahead of a
         release of Debian stable. Experimental will typically have no LAVA
         packages outside of a Debian release freeze.

.. [#f2] `stretch` was released on 17th June 2017. All updates to LAVA
         packages for Stretch will be made using
         `stretch-backports`_. Systems using Debian Stretch are
         recommended to enable stretch-backports. LAVA packages and
         dependencies which are installed using stretch-backports are
         **fully supported** by upstream and are the same codebase as
         the relevant production release available from the
         :ref:`lava_repositories`.

.. [#f3] Jessie was released on April 25th, 2015 and security support for
         Jessie is expected to terminate in June 2018. All instances using
         Jessie are recommended to upgrade to Debian Stretch as soon as
         possible. Remaining updates to LAVA packages for Jessie will be made
         using `jessie-backports`_.

.. [#f4] `buster` is the name of the next Debian release after Stretch, which
         is supported automatically via uploads to Sid (unstable).

.. _experimental: https://wiki.debian.org/DebianExperimental

.. _jessie-backports: http://backports.debian.org/

.. _stretch-backports: http://backports.debian.org/

You can track the versions of LAVA packages in the various Debian suites by
following links from the Debian package trackers for `lava-dispatcher
<https://tracker.debian.org/pkg/lava-dispatcher>`_ and `lava-server
<https://tracker.debian.org/pkg/lava-server>`_.

.. index:: lava repository, staging-repo, production-repo

.. _lava_repositories:

LAVA repositories
=================

As well as being uploaded to Debian, :ref:`production_releases` of LAVA are
uploaded to a Linaro `production-repo`_ repository which uses the
:ref:`lava_archive_signing_key` - a copy of the key is available in the
repository.

.. _production-repo: https://images.validation.linaro.org/production-repo/

In times when the current production release has not made it into either
``stretch-backports`` or  ``jessie-backports`` (e.g. due to a migration issue
or a pre-release package freeze in Debian), this repository can be used
instead.

The :file:`services-trace.txt` file in the repository shows the latest update
timestamp and is accompanied by a GnuPG signature of the trace file, signed
using the :ref:`lava_archive_signing_key`.

Interim builds (including release candidates) are available in the staging
repository, using the same suites::

 deb https://images.validation.linaro.org/staging-repo stretch-backports main

 deb https://images.validation.linaro.org/staging-repo jessie-backports main

This repository uses the same key as the production repository.

There are differences in how the packages are built between
``jessie-backports`` and ``stretch-backports`` but the contents are otherwise
the same for the same upstream version.

Stretch users
-------------

.. note:: The recommended base for LAVA is Debian Stretch, as of 2018.1.

::

 deb https://images.validation.linaro.org/production-repo stretch-backports main

Jessie users
-------------

.. caution:: Deprecated - please upgrade Jessie systems to Stretch.

::

 deb https://images.validation.linaro.org/production-repo jessie-backports main

.. note:: The packages formerly in the ``sid`` suite in the repository are
   not being updated after 2017.6.

.. _archive_repository:

Archive repository
------------------

The recommended time to create an :ref:`archive <archiving_v1>` for V1
test data is after the upgrade to 2017.10 but before the upgrade to
2017.11.

It is possible to create an archive retrospectively, but **only** if a
usable backup of the postgresql database exists from the period
**between** the upgrade to 2017.10 and the upgrade to 2017.11.

.. important:: Once an instance has been upgraded to 2017.11, some of
   the internal data links in the V1 test data **will have been
   deleted** and the database will not be able to function correctly
   as an archive of V1 test data. Once an instance has been upgraded
   to 2017.12 or beyond, **all** V1 test data will have been
   permanently and deliberately deleted from the database.

For the sake of users needing this archive functionality, packages of
the 2017.10 LAVA release will also remain available in a dedicated
LAVA repository. The archive machine will need to be configured
**not** to use the default apt sources for either stretch or jessie
above. The archive **must instead use** the archive repository, for
stretch or jessie respectively::

 deb https://images.validation.linaro.org/v1-archive-repo stretch-backports main

or::

 deb https://images.validation.linaro.org/v1-archive-repo jessie-backports main

.. index:: lava archive signing key

.. _lava_archive_signing_key:

LAVA Archive signing key
------------------------

::

 pub  2048R/C77102A9 2014-06-06 LAVA build daemon (Staging) <lava-lab@linaro.org>
      Key fingerprint = 45AD 50DC 41AE D421 FF5B  33D4 ECF3 C05C C771 02A9
 uid                  LAVA build daemon (Staging) <lava-lab@linaro.org>

Each of the support archives on ``images.validation.linaro.org`` is
signed using the same key, 0x33D4ECF3C05CC77102A9, which can be downloaded_ and added to
apt::

 $ wget https://images.validation.linaro.org/staging-repo/staging-repo.key.asc
 $ sudo apt-key add staging-repo.key.asc
 OK

Then update to locate the required dependencies::

 $ sudo apt update

.. note:: The above repositories use `https` hence install the package
          `apt-transport-https` if it is not already installed.

.. _downloaded: https://images.validation.linaro.org/staging-repo/staging-repo.key.asc

.. index:: production release

.. _production_releases:

Production releases
===================

.. seealso:: :ref:`setting_up_pipeline_instance` and :ref:`archiving_v1`.

LAVA is currently packaged for Debian unstable using Django1.8 and Postgresql.
LAVA packages are now available from official Debian mirrors for Debian
unstable. e.g. to install the master, use::

 $ sudo apt install postgresql
 $ sudo apt install lava-server

If the default Apache configuration from LAVA is suitable, you can enable it
immediately::

 $ sudo a2dissite 000-default
 $ sudo a2enmod proxy
 $ sudo a2enmod proxy_http
 $ sudo a2ensite lava-server.conf
 $ sudo service apache2 restart

Edits to the ``/etc/apache2/sites-available/lava-server.conf`` file will not be
overwritten by package upgrades unless the admin explicitly asks ``dpkg`` to do
so.

If you later choose to remove ``lava-server``, the apache modules enabled above
can be disabled using::

 $ sudo a2dismod proxy
 $ sudo a2dismod proxy_http

.. _installation_configuration:

Configuring the installation
============================

If the installation uses ``http://localhost``, the remaining configuration is to
disable some of the Django security checks which expect ``https``.

.. seealso:: :ref:`check_instance`

If the installation uses a remote slave, then :ref:`zmq_curve` should be enabled.

The configuration defaults of ``lava-master``, ``lava-logs`` and ``lava-slave``
should also be checked. On the master, these files can often be the same content:

* ``/etc/default/lava-master`` or ``/etc/lava-server/lava-master``
* ``/etc/default/lava-logs`` or ``/etc/lava-server/lava-logs``

Each master has a local ``lava-slave`` even if that slave has no devices configured.

* ``/etc/default/lava-slave`` or ``/etc/lava-server/lava-slave``.

.. index:: tftpd-hpa

.. _tftp_support:

TFTP support requirement
========================

LAVA uses :term:`tftp` to serve files to a variety of device types.

The LAVA V1 dispatcher **relies** on TFTP downloads, NFS share directories and
master image downloads to **all** be made from a single directory:
:file:`/var/lib/lava/dispatcher/tmp`. To do this, the configuration file for
:command:`tftpd-hpa` needs to be modified to use the LAVA directory instead of
the default, ``/srv/tftp``.

.. note:: The TFTP support in LAVA has had to be changed from the **2015.8
   release** onwards to stop LAVA enforcing a configuration change on the
   ``tftpd-hpa`` package without explicit configuration by the admin.
   Previously, installation may have prompted about changes in
   :file:`/etc/default/tftpd-hpa`; now this change needs to be made manually as
   the configuration of the ``tftpd-hpa`` package should not have been up to
   LAVA to impose. If you are already running a version of LAVA installed prior
   to the **2015.8 release** (and have working TFTP support), then the
   configuration change will have been imposed by LAVA and then maintained by
   ``dpkg`` and ``tftpd-hpa``. Check that your ``/etc/default/tftpd-hpa`` file
   references :file:`/var/lib/lava/dispatcher/tmp` and continue as before.

Admins can either manually change the :file:`/etc/default/tftpd-hpa` to set the
``TFTP_DIRECTORY`` to :file:`/var/lib/lava/dispatcher/tmp` or copy the file
packaged by ``lava-dispatcher``::

 $ sudo cp /usr/share/lava-dispatcher/tftpd-hpa /etc/default/tftpd-hpa

If you are planning to support V1 devices, this change will be required in
whichever Debian-based distribution you use as your base install, including
Ubuntu.

In LAVA V2, behaviour has changed here. In whatever base directory is
configured for ``tftpd-hpa``, LAVA will use temporary subdirectories for all
TFTP operations; other LAVA operations will use the
:file:`/var/lib/lava/dispatcher/tmp` directory. If **all** of your devices are
:term:`exclusive`, to V2 (:term:`pipeline`), then the ``tftpd-hpa``
configuration can be set to the tftpd original value (``/srv/tftp``), the LAVA
historical value (``/var/lib/lava/dispatcher/tmp``) or any other directory
specified by the admin.

Extra dependencies
------------------

The ``lava`` metapackage brings in extra dependencies which may be
useful on some instances.

.. index:: stretch, install on stretch

.. _install_debian_stretch:

Installing on Debian Stretch
============================

Debian Stretch was released on June 17th, 2017, containing a full set
of packages to install LAVA at version 2016.12. Debian stable releases
of LAVA do not receive updates to LAVA directly, so a simple install
on Stretch will only get you ``2016.12``. All admins of LAVA instances
are **strongly** advised to update all software on the instance on a
regular basis to receive security updates to the base system.

For packages which need larger changes, the official Debian method is
to provide those updates using ``backports``. Backports **do not
install automatically** even after the apt source is added - this is
because backports are rebuilt from the current ``testing`` suite, so
automatic upgrades would move the base system to testing as
well. Instead, the admin selects which backported packages to add to
the base stable system. Only those packages (and dependencies, if not
available in stable already) will then be installed from backports.

The ``lava-server`` backports and dependencies are **fully supported**
by the LAVA software team and admins of **all** LAVA instances need to
update the base ``2016.12`` to the version available in current
backports. Subscribe to the :ref:`lava_announce` mailing list for
details of when new releases are made. Backports will be available
about a week after the initial release.

Updates for LAVA on Debian Stretch will be uploaded to `stretch-backports
<http://backports.debian.org/>`_ once this becomes available.

Create an apt source for backports, either by editing ``/etc/apt/sources.list``
or adding a file with a ``.list`` suffix into ``/etc/apt/sources.list.d/``.
Create a line like the one below (using your preferred Debian mirror)::

 deb http://deb.debian.org/debian stretch-backports main

Remember to update your apt cache whenever add a new apt source::

 $ sudo apt update

Then install ``lava-server`` from ``stretch-backports`` using the ``-t`` option::

 $ sudo apt -t stretch-backports install lava-server
 $ sudo a2dissite 000-default
 $ sudo a2enmod proxy
 $ sudo a2enmod proxy_http
 $ sudo a2ensite lava-server.conf
 $ sudo service apache2 restart

Once backports are enabled, the packages which the admin has selected from
backports (using the ``-t`` switch) will continue to upgrade using backports.
Other packages will only be added from backports if the existing backports
require updates from backports.

.. index:: backports, jessie-backports, install using backports

.. _install_debian_jessie:

Installing on Debian Jessie
===========================

.. caution:: Deprecated - new LAVA instances should no longer use Debian
   Jessie.

Debian Jessie was released on April 25th, 2015, containing a full set of
packages to install LAVA at version 2014.9. Debian stable releases of LAVA do
not receive updates to LAVA directly, so a simple install on Jessie will only
get you ``2014.9``. All admins of LAVA instances are **strongly** advised to
update all software on the instance on a regular basis to receive security
updates to the base system.

For packages which need larger changes, the official Debian method is to
provide those updates using ``backports``. Backports **do not install
automatically** even after the apt source is added - this is because backports
are rebuilt from the current ``testing`` suite, so automatic upgrades would
move the base system to testing as well. Instead, the admin selects which
backported packages to add to the base stable system. Only those packages (and
dependencies, if not available in stable already) will then be installed from
backports.

The ``lava-server`` backports and dependencies are **fully supported** by the
LAVA software team and admins of **all** LAVA instances need to update the base
``2014.9`` to the version available in current backports. Subscribe to the
:ref:`lava_announce` mailing list for details of when new releases are made.
Backports will be available about a week after the initial release.

Updates for LAVA on Debian Jessie are uploaded to `jessie-backports
<http://backports.debian.org/>`_

Create an apt source for backports, either by editing ``/etc/apt/sources.list``
or adding a file with a ``.list`` suffix into ``/etc/apt/sources.list.d/``.
Create a line like the one below (using your preferred Debian mirror)::

 deb http://deb.debian.org/debian jessie-backports main

Remember to update your apt cache whenever add a new apt source::

 $ sudo apt update

Then install ``lava-server`` from ``jessie-backports`` using the ``-t`` option::

 $ sudo apt -t jessie-backports install lava-server
 $ sudo a2dissite 000-default
 $ sudo a2enmod proxy
 $ sudo a2enmod proxy_http
 $ sudo a2ensite lava-server.conf
 $ sudo service apache2 restart

Once backports are enabled, the packages which the admin has selected from
backports (using the ``-t`` switch) will continue to upgrade using backports.
Other packages will only be added from backports if the existing backports
require updates from backports. For example, when ``lava-server 2016.8`` moved
to requiring Django1.8, new installations and updates to ``2016.8`` using
backports automatically bring in Django1.8 and associated support, also from
backports.

Installing just lava-server
===========================

The ``lava-server`` package is the main LAVA scheduler and frontend.

.. seealso:: :ref:`setting_up_pipeline_instance`.

To install just the lava-server from the current packages, use::

 $ sudo apt install lava-server
 $ sudo a2dissite 000-default
 $ sudo a2enmod proxy
 $ sudo a2enmod proxy_http
 $ sudo a2ensite lava-server.conf
 $ sudo service apache2 restart

This will install lava-dispatcher and lava-server.

Other packages to consider:

* ``lavapdu-client`` to control a :term:`PDU` to allow LAVA to automatically
  power cycle a device.

* ``lavapdu-daemon`` - only one daemon is required to run multiple PDUs.

* ``ntp`` - some actions within LAVA can be time-sensitive, so ensuring that
  devices within your lab keep time correctly can be important.

.. note:: There is no support in V2 for ``linaro-media-create`` to manipulate
   hardware packs from Linaro, so this package can be removed once there are no
   V1 devices on the worker.

Installing the full lava set
============================

Production installs of LAVA will rarely use the full ``lava`` set as it
includes tools more commonly used by developers and test labs. These tools mean
that the ``lava`` package brings more dependencies than when installing
``lava-server`` to run a production LAVA instance.

The ``lava`` package installs support for:

* ``lava-dev`` - scripts to build developer packages based on your current git
  tree of ``lava-server`` or ``lava-dispatcher``, including any local changes.

* ``vmdebootstrap`` for building your own Debian based KVM images.

* ``lavapdu-client`` to control a :term:`PDU` to allow LAVA to automatically
  power cycle a device.

* ``lavapdu-daemon`` is recommended or you can use a single daemon for multiple
  PDUs.

* ``ntp`` - some actions within LAVA can be time-sensitive, so ensuring that
  devices within your lab keep time correctly can be important.

.. note:: There is no support in V2 for ``linaro-media-create`` to manipulate
   hardware packs from Linaro, so this package can be removed once there are no
   V1 devices on the worker.

All of these packages can be installed separately alongside the main
``lava-server`` package, the ``lava`` package merely collects them into one
set. ::

 $ sudo apt install postgresql
 $ sudo apt -t stretch-backports install lava
 $ sudo a2dissite 000-default
 $ sudo a2enmod proxy
 $ sudo a2enmod proxy_http
 $ sudo a2ensite lava-server.conf
 $ sudo service apache2 restart

.. seealso:: :ref:`Creating a superuser <create_superuser>`, :ref:`logging_in`,
   :ref:`authentication_tokens` and the :ref:`first job definition
   <first_job_definition>`.

.. index:: python3

.. _lava_python3:

LAVA and Python3
================

Python2 has been `marked as end of life
<http://legacy.python.org/dev/peps/pep-0373/>`_ and distributions are in the
process of removing packages which depend on Python2. Django has had Python3
support for some time and will be dropping Python2 support in the next LTS.
(The current non-LTS release of django, version 2.0, has already dropped
support for Python2.)

LAVA has been moving towards Python3 support as an integral part of the
migration to V2 and with the completion of the migration and the removal of the
V1 codebase, `the announcement has been made
<https://lists.linaro.org/pipermail/lava-announce/2017-June/000032.html>`_ that
all LAVA packages will move exclusively to Python3 support.

Supporting LAVA with Python3 on Debian Jessie is awkward and as Jessie is now
deprecated and will have security support dropped in 2018, the decision has
been taken to **not** support Python3 in Jessie for LAVA packages. The move to
Python3 will therefore happen with the move to Stretch.

Setting up a reverse proxy
==========================

In order to use lava-server behind a reverse proxy, configure lava-server as
usual and then setup a reverse proxy. The following simple Apache configuration
snippet will work for most setups::

 ProxyPass / http://lava_server_dns:port/
 ProxyPassReverse / http://lava_server_dns:port/
 ProxyPreserveHost On
 RequestHeader set X-Forwarded-Proto "https" env=HTTPS

This configuration will work when proxifying::

  http://example.com/ => http://lava.example.com/

If you want the application to answer on a specific base URL, configure
lava-server to answer on this base URL and then configure the reverse proxy to
proxify the same base URL. For instance you can have::

  http://example.com/lava => http://lava.example.com/lava

Having two different base URLs is more awkward to setup. In this case you will
have to also setup Apache modules like `Substitute` to alter the HTML content
on the fly. This is not a recommended setup.

Depending on your setup, you should also have a look at
`ProxyPassReverseCookieDomain
<https://httpd.apache.org/docs/2.4/mod/mod_proxy.html#proxypassreversecookiedomain>`_
and `ProxyPassReverseCookiePath
<https://httpd.apache.org/docs/2.4/mod/mod_proxy.html#proxypassreversecookiepath>`_
to set the cookie domain and path correctly.

.. index:: superuser, create superuser

.. _create_superuser:

Superuser
=========

.. seealso:: :ref:`admin_adding_users`

LDAP
----

In LAVA instances that use LDAP for external authentication, log in once with
the user account that will be granted superuser privileges in the LAVA web UI.
Then use the following command to make this user a superuser::

  $ sudo lava-server manage authorize_superuser --username {username}

.. note:: `{username}` is the username of LDAP user.

Alternatively, the `addldapuser` command can be used to populate a user from
LDAP and also grant superuser privilege as follows::

  $ sudo lava-server manage addldapuser --username {username} --superuser

.. note:: `{username}` is the username of LDAP user.

.. seealso:: :ref:`admin_adding_users`

Local Django Accounts
---------------------

After initial package installation, you might wish to create a local superuser
account::

 $ sudo lava-server manage createsuperuser --username $USERNAME --email=$EMAIL

If you do not specify the username and email address here, this
command will prompt for them.

An existing local Django superuser account can also be converted to an LDAP
user account without losing data, using the `mergeldapuser` command, provided
the LDAP username does not already exist in the LAVA instance::

  $ sudo lava-server manage mergeldapuser --lava-user <lava_user> --ldap-user <ldap_user>

Debugging the Installation
==========================

After your LAVA instance is successfully installed, if you face any problem
consult :ref:`debugging_v2`

.. _django_localhost:

Using localhost or non HTTPS instance URL
-----------------------------------------

Newer versions of django include improved security features which can affect
how LAVA is used as ``http://localhost``. By default, django enforces
behaviour to ensure safe use of ``https://`` which can prevent attempts to
sign in to a LAVA instance using ``http://localhost/``.

To enable localhost, you may need to disable at least these security
defaults by adding the following options to ``/etc/lava-server/settings.conf``::

  "CSRF_COOKIE_SECURE": false,
  "SESSION_COOKIE_SECURE": false

.. note:: This is the reason, if you see issues regarding CSRF token while
          trying to login with an username. The common error message reported
          is ``CSRF verification failed. Request aborted.``

Any changes made to ``/etc/lava-server/settings.conf`` will require a restart
of `lava-server-gunicorn` service for the changes to get applied::

  $ sudo service lava-server-gunicorn restart

.. seealso:: :ref:`check_instance`
