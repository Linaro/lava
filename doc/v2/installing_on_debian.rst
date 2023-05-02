.. index:: debian, installation, install

.. _debian_installation:

Installing on a Debian system
*****************************

These instructions cover installation on Debian. The supported versions
are:

+---------------+------------------------+--------+----------------------+
| Distribution  | Codename               | Number | Support              |
+===============+========================+========+======================+
| Debian        | experimental           | n/a    | No [#f1]_            |
+---------------+------------------------+--------+----------------------+
| Debian        | Sid (unstable)         | n/a    | Yes [#f2]_           |
+---------------+------------------------+--------+----------------------+
| Debian        | Bullseye (testing)     | 11.*   | Yes [#f3]_           |
+---------------+------------------------+--------+----------------------+
| Debian        | Buster (stable)        | 10.*   | Yes [#f4]_           |
+---------------+------------------------+--------+----------------------+

Debian uses codenames for releases (bullseye, buster, stretch) and names for
`suites`_ (unstable, testing, stable & oldstable). When a new Debian major
release is made, the packages in "testing" are frozen and become the new
"stable". A new codename is chosen for the new "testing" suite, and that will
be the name for the next major release in the cycle.

To allow the table to refer to the same package versions consistently
over time, codenames are used here. When a Debian release is made, a
new codename is applied to the testing suite and LAVA releases after
that point will include that codename in the table.

.. note:: LAVA used to be supported on Ubuntu directly, but is not any
   more due to lack of resources to maintain and test that support.
   Support may be re-instated if more effort becomes available in the
   future. The last version of LAVA supported in Ubuntu was
   **2015.9.post1**.

.. _suites: https://en.wikipedia.org/wiki/Debian#Branches

.. [#f1] `experimental`_ allows updates to be selected on top of
         unstable (or the current testing) during times when testing is
         frozen ahead of a release of Debian stable. Experimental will
         typically have no LAVA packages outside of a Debian release
         freeze.

.. [#f2] `sid` is the name of the unstable suite which never gets
         released but acts as a feed for ``testing``. As the name
         suggests, ``unstable`` can be broken without warning and
         installation of complex packages like LAVA can often fail.
         Unstable is **never** recommended for production instances
         of any software, including LAVA.

.. [#f3] `bullseye` is the name of the next Debian release after Buster,
         which is supported automatically via uploads to Sid
         (unstable). Bullseye is not recommended for production
         instances of LAVA.

         When bullseye is released as Debian 11, it will use the suite
         name ``stable``, testing will get the codename of the next
         Debian stable release, and Buster will become
         ``oldstable``.

.. [#f4] `buster` is the name of the stable version of Debian. LAVA is fully
         supported on this Debian version. It's recommended to use Buster for
         production instances.

.. _experimental: https://wiki.debian.org/DebianExperimental

You can track the versions of LAVA packages in the various Debian
suites by following links from the Debian package tracker for
`lava <https://tracker.debian.org/pkg/lava>`_.

.. index:: debian - architectures

.. _recommended_debian_architectures:

Recommended Debian architectures
================================

LAVA is intended to provide a CI system which is capable of handling
dozens or hundreds of simultaneous test jobs across dozens of devices.

Whilst it is possible to install and operate LAVA on 32 bit
architectures like ``i386`` and ``armhf``, this is not recommended for
any production instance. The memory requirements for the master will
increase with the number of users and if your instance is publicly
visible on the internet, limited access to RAM is known to cause
problems. The memory, CPU and I/O requirements of lava-dispatcher
depend on the number and type of devices as well as the number of test
jobs which can run simultaneously. For example, experience has shown
that any test job using ``fastboot`` requires a single CPU core (not
hyperthread) per attached device, as well as at least one core for the
base OS. ``armhf`` in particular can struggle to provide enough
processing power (CPU or I/O or RAM) for such devices. Each QEMU device
can require more RAM than would be available on most 32bit systems.

LAVA is routinely used on ``amd64`` and ``arm64`` architectures.
Packages for other 64bit architectures like ppc64, ppc64el and s390x
are available from Debian.

Each lab will be different and there are no definitive guidelines on
what hardware specifications to choose. Start slowly and :ref:`grow
your lab one step at a time <growing_your_lab>`. If in doubt,
:ref:`talk to us <getting_support>`.

.. seealso:: :ref:`lab_scaling`

.. index:: lava repository, staging-repo, production-repo

.. _lava_repositories:

LAVA repositories
=================

As well as being uploaded to Debian, :ref:`production_releases` of
LAVA are also uploaded to the LAVA Software Community Project
repository at https://apt.lavasoftware.org/ . This uses the
:ref:`lava_archive_signing_key` - a copy of the key is available in
the repository and on key servers.

Update apt to find the new packages::

 $ sudo apt update

.. seealso:: :ref:`dependency_requirements`.

Releases
--------

.. code-block:: none

 deb https://apt.lavasoftware.org/release buster main

.. note:: The LAVA repositories only provide packages for ``amd64`` and
   ``arm64``. See :ref:`recommended_debian_architectures`.

In times when the current production release has not made it into
either ``bullseye`` or ``testing`` (e.g. due to a migration
issue or a pre-release package freeze in Debian), this repository
should be used instead.

Daily builds
------------

Interim builds (including release candidates) are available from the
daily builds repository, using the same suites:

.. code-block:: none

 deb https://apt.lavasoftware.org/daily buster main

Snapshots
---------

When a build is updated in the repositories, a copy of the same build
is created in the snapshot folder:

.. code-block:: none

 https://apt.lavasoftware.org/snapshot/

Entries are created according to the suite for which it was built and
the year, month and day of the build.

Buster users
-------------

.. note:: The recommended base for LAVA is Debian Stretch, as of 2018.1.

.. code-block:: none

 deb https://apt.lavasoftware.org/release buster main

.. index:: lava archive signing key, lava repository,
	   apt.lavasoftware.org, fingerprint

.. _lava_archive_signing_key:

LAVA Archive signing keys
-------------------------

The LAVA Software Community Project uses two keys for the repositories.

The daily builds are signed using:

.. code-block:: none

 pub  2048R/C77102A9 2014-06-06 LAVA build daemon (Staging) <lava-lab@linaro.org>
      Key fingerprint = 45AD 50DC 41AE D421 FF5B  33D4 ECF3 C05C C771 02A9
 uid                  LAVA build daemon (Staging) <lava-lab@linaro.org>

Production releases are signed using:

.. code-block:: none

 pub   rsa4096/A791358F2E49B100 2018-10-02 [SC]
      Key fingerprint = C87D 63FD 9355 35CF B0CA  F5C2 A791 358F 2E49 B100
 uid                 [ultimate] LAVA Software release key <release@lavasoftware.org>
 sub   rsa4096/42124FB9C30943EC 2018-10-02 [E]

Both keys can be downloaded and added to apt easily::

 $ wget https://apt.lavasoftware.org/lavasoftware.key.asc
 $ sudo apt-key add lavasoftware.key.asc
 OK

After that step, run apt update again to locate the required dependencies::

 $ sudo apt update

.. index:: production release

.. _production_releases:

Production releases
===================

.. seealso:: :ref:`setting_up_pipeline_instance`.

LAVA is currently packaged for Debian unstable using Django1.10 and
Postgresql. LAVA packages are now available from official Debian
mirrors for Debian unstable. e.g. to install the master, use::

 $ sudo apt install postgresql
 $ sudo apt install lava-server

If the default Apache configuration from LAVA is suitable, you can
enable it immediately::

 $ sudo a2dissite 000-default
 $ sudo a2enmod proxy
 $ sudo a2enmod proxy_http
 $ sudo a2ensite lava-server.conf
 $ sudo service apache2 restart

Edits to the ``/etc/apache2/sites-available/lava-server.conf`` file
will not be overwritten by package upgrades unless the admin explicitly
asks ``dpkg`` to do so.

If you later choose to remove ``lava-server``, the apache modules
enabled above can be disabled using::

 $ sudo a2dismod proxy
 $ sudo a2dismod proxy_http

.. _installation_configuration:

Configuring the installation
============================

If the installation uses ``http://localhost``, the remaining
configuration is to disable some of the Django security checks which
expect ``https``.

.. seealso:: :ref:`check_instance` and :ref:`django_localhost`

If the installation uses a remote slave, then HTTPS should
be used.

.. index:: python3

.. _lava_python3:

LAVA and Python3
================

Python2 has been `marked as end of life
<https://legacy.python.org/dev/peps/pep-0373/>`_ and distributions are
in the process of removing packages which depend on Python2. Django has
had Python3 support for some time and will be dropping Python2 support
in the next LTS. (The current non-LTS release of django, version 2.0,
has already dropped support for Python2.)

LAVA has moved to exclusive Python3 support.

.. _django_non_localhost:

Using a domain name other than localhost
========================================

While having LAVA run on localhost is a great point to start for doing the
first steps, a real deploy of LAVA will most probably end up on a domain
e.g. like `lava.example.net`. There are some more configuration to do
to achieve this:

* Set up Apache configuration to serve LAVA on your desired domain by
   editing Apache configuration and/or ``/etc/apache2/sites-available/lava-server.conf``
   to fit to your needs. Reload apache configuration by ``systemctl reload apache2``

* Append this line to ``/etc/lava-server/lava-server-gunicorn``::

   ALLOWED_HOSTS='lava.example.net'

and restart `lava-server-gunicorn` service for the changes to get applied::

   $ systemctl restart lava-server-gunicorn.service

* Remember to also modify ``/etc/lava-dispatcher/lava-worker`` and add
   domain name there too (and edit worker configuration in django). Don't
   forget to restart worker afterwards for the changes to get applied::

   $ systemctl restart lava-worker.service

Setting up a reverse proxy
==========================

In order to use lava-server behind a reverse proxy, configure
lava-server as usual and then setup a reverse proxy. The following
simple Apache configuration snippet will work for most setups::

 ProxyPass / http://lava_server_dns:port/
 ProxyPassReverse / http://lava_server_dns:port/
 ProxyPreserveHost On
 RequestHeader set X-Forwarded-Proto "https" env=HTTPS

Remember to also include ``ALLOWED_HOSTS`` as written above.

This configuration will work when proxifying::

  http://example.com/ => http://lava.example.com/

If you want the application to answer on a specific base URL, configure
lava-server to answer on this base URL and then configure the reverse
proxy to proxify the same base URL. For instance you can have::

  http://example.com/lava => http://lava.example.com/lava

In order to serve LAVA under ``/lava`` you should update the settings and add::

  "STATIC_URL": "/lava/static/",
  "MOUNT_POINT": "/lava",
  "LOGIN_URL": "/lava/accounts/login/",
  "LOGIN_REDIRECT_URL": "/lava/",

Having two different base URLs is more awkward to setup. In this case
you will have to also setup Apache modules like `Substitute` to alter
the HTML content on the fly. This is not a recommended setup.

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

In LAVA instances that use LDAP for external authentication, log in
once with the user account that will be granted superuser privileges in
the LAVA web UI. Then use the following command to make this user a
superuser::

  $ sudo lava-server manage authorize_superuser --username {username}

.. note:: `{username}` is the username of LDAP user.

Alternatively, the `addldapuser` command can be used to populate a user
from LDAP and also grant superuser privilege as follows::

  $ sudo lava-server manage addldapuser --username {username} --superuser

.. note:: `{username}` is the username of LDAP user.

.. seealso:: :ref:`admin_adding_users`

Local Django Accounts
---------------------

After initial package installation, you might wish to create a local
superuser account::

 $ sudo lava-server manage createsuperuser --username $USERNAME --email=$EMAIL

If you do not specify the username and email address here, this
command will prompt for them.

An existing local Django superuser account can also be converted to an
LDAP user account without losing data, using the `mergeldapuser`
command, provided the LDAP username does not already exist in the LAVA
instance::

  $ sudo lava-server manage mergeldapuser --lava-user <lava_user> --ldap-user <ldap_user>

Debugging the Installation
==========================

After your LAVA instance is successfully installed, if you face any
problem consult :ref:`debugging_v2`

.. _django_localhost:

Using localhost or non HTTPS instance URL
-----------------------------------------

Newer versions of django include improved security features which can
affect how LAVA is used as ``http://localhost``. By default, django
enforces behavior to ensure safe use of ``https://`` which can prevent
attempts to sign in to a LAVA instance using ``http://localhost/``.

To enable localhost, you may need to disable at least these security
defaults by adding the following options to LAVA settings file::

  "CSRF_COOKIE_SECURE": false,
  "SESSION_COOKIE_SECURE": false

.. note:: This is the reason, if you see issues regarding CSRF token
          while trying to login with an username. The common error
          message reported is ``CSRF verification failed. Request
          aborted.``

The LAVA settings are stored in yaml in:

* ``/etc/lava-server/settings.conf``
* ``/etc/lava-server/settings.yaml``
* ``/etc/lava-server/settings.d/*.yaml``

LAVA will load the files in this exact order.Files in the settings.d
directory will be alphabetically ordered.

If a variable is defined in two files, the value from the last file will
override the value from first one.
Any changes made in LAVA settings yaml file  will require a
restart of `lava-server-gunicorn` service for the changes to get
applied::

  $ sudo service lava-server-gunicorn restart

.. note:: From 2020.05 release the settings files will not be created by
          default on fresh installations. The settings file can be added in
          settings.d directory or settings.conf should be created.

.. seealso:: :ref:`check_instance`
