.. index:: debian, installation, install

.. _debian_installation:

Installing on a Debian system
*****************************

These instructions cover installation on Debian. The supported versions
are:

+---------------+------------------------+--------+----------------------+
| Distribution  | Codename               | Number | Support              |
+===============+========================+========+======================+
| Debian        | experimental           | n/a    | Yes [#f1]_           |
+---------------+------------------------+--------+----------------------+
| Debian        | Sid (unstable)         | n/a    | Yes [#f5]_           |
+---------------+------------------------+--------+----------------------+
| Debian        | Buster (testing)       | n/a    | Yes [#f4]_           |
+---------------+------------------------+--------+----------------------+
| Debian        | Stretch (stable)       | 9.*    | Yes [#f2]_           |
+---------------+------------------------+--------+----------------------+
| Debian        | Jessie (oldstable)     | 8.0    | **No** [#f3]_        |
+---------------+------------------------+--------+----------------------+

Debian uses codenames for releases (buster, stretch, jessie, wheezy,
squeeze) and names for `suites`_ (unstable, testing, stable &
oldstable). When a new Debian major release is made, the packages in
"testing" are frozen and become the new "stable". A new codename is
chosen for the new "testing" suite, and that will be the name for the
next major release in the cycle.

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

.. [#f2] `stretch` was released on 17th June 2017. All updates to LAVA
         packages for Stretch will be made using `stretch-backports`_.
         Systems using Debian Stretch are recommended to enable
         stretch-backports. LAVA packages and dependencies which are
         installed using stretch-backports are **fully supported** by
         upstream and are the same codebase as the relevant production
         release available from the :ref:`lava_repositories`. Stretch
         continues to receive point releases and LAVA remains supported
         for each point release of Debian.

.. [#f3] Jessie was released on April 25th, 2015 and security support
         for Jessie is expected to terminate in June 2018. LAVA
         software has removed support for building and installing in
         Jessie as part of the move to :ref:`Python3 <lava_python3>`.

.. [#f4] `buster` is the name of the next Debian release after Stretch,
         which is supported automatically via uploads to Sid
         (unstable). Buster is **not** recommended for production
         instances of LAVA at this time. The release process for buster
         is scheduled to start in Jan 2019.

         When buster is released as Debian 10, it will use the suite
         name ``stable``, testing will get the codename of the next
         Debian stable release, **bullseye**, and Stretch will become
         ``oldstable``.

.. [#f5] `sid` is the name of the unstable suite which never gets
         released but acts as a feed for ``testing``. As the name
         suggests, ``unstable`` can be broken without warning and
         installation of complex packages like LAVA can often fail.
         Unstable will **never** recommended for production instances
         of any software, including LAVA.

.. _experimental: https://wiki.debian.org/DebianExperimental

.. _stretch-backports: https://backports.debian.org/

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
processing power (CPU or I/O or RAM) for such devices. EAch QEMU device
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

As well as being uploaded to Debian, :ref:`production_releases` of LAVA
are uploaded to the LAVA Software Community Project repository which
uses the :ref:`lava_archive_signing_key` - a copy of the key is
available in the repository and on keyservers.

When using LAVA repositories on Stretch, make sure to enable
``stretch-backports`` from your regular Debian mirror as well as the
LAVA repository. Create an apt source based on your existing apt source
for Stretch::

 deb http://deb.debian.org/debian stretch-backports main

Update apt to find the new packages::

 $ sudo apt update

The list of packages to obtain from ``stretch-backports`` in the main
Debian archive is maintained using the
``/usr/share/lava-server/requires.py`` script in the ``lava-dev``
package::

 $ /usr/share/lava-server/requires.py -d debian -s stretch-backports -p lava-server -n
 python3-django-auth-ldap python3-django-tables2 python3-requests

::

 $ sudo apt -t stretch-backports install python3-django-auth-ldap python3-django-tables2 python3-requests

Workers also need support from `stretch-backports`::

 $ /usr/share/lava-server/requires.py -d debian -s stretch-backports -p lava-dispatcher -n
 python3-requests

::

 $ sudo apt -t stretch-backports install python3-requests

..seealso:: :ref:`install_debian_stretch` and
  :ref:`dependency_requirements`.

Releases
--------

.. code-block:: none

 deb https://apt.lavasoftware.org/release stretch-backports main
 deb https://apt.lavasoftware.org/release buster main

.. note:: The LAVA repositories only provide packages for ``amd64`` and
   ``arm64``. See :ref:`recommended_debian_architectures`.

In times when the current production release has not made it into
either ``stretch-backports`` or ``testing`` (e.g. due to a migration
issue or a pre-release package freeze in Debian), this repository can
be used instead.

Daily builds
------------

Interim builds (including release candidates) are available from the
daily builds repository, using the same suites:

.. code-block:: none

 deb https://apt.lavasoftware.org/daily stretch-backports main
 deb https://apt.lavasoftware.org/daily buster main

Snapshots 
---------

When a build is updated in the repositories, a copy of the same build
is created in the snapshot folder.
https://apt.lavasoftware.org/snapshot/

Entries are created according to the suite for which it was built and
the year, month and day of the build.

Stretch users
-------------

.. note:: The recommended base for LAVA is Debian Stretch, as of 2018.1.
   When using LAVA repositories on Stretch, make sure to enable
   `stretch-backports` from your regular Debian mirror as well as the
   LAVA repository. See :ref:`install_debian_stretch`.

.. code-block:: none

 deb https://apt.lavasoftware.org/release stretch-backports main

Buster users
-------------

.. note:: The recommended base for LAVA is Debian Stretch, as of 2018.1.

.. code-block:: none

 deb https://apt.lavasoftware.org/release buster main

.. index:: lava archive signing key

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

Both keys can be downloaded and added to apt::

 $ wget https://apt.lavasoftware.org/lavasoftware.key.asc
 $ sudo apt-key add lavasoftware.key.asc
 OK

Then update to locate the required dependencies::

 $ sudo apt update

.. note:: The above repositories use `https` hence install the package
          `apt-transport-https` if it is not already installed or
          change the apt source URL to `http://`

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

If the installation uses a remote slave, then :ref:`zmq_curve` should
be enabled.

The configuration defaults of ``lava-master``, ``lava-logs`` and
``lava-slave`` should also be checked. On the master, these files can
often be the same content:

* ``/etc/default/lava-master`` or ``/etc/lava-server/lava-master``
* ``/etc/default/lava-logs`` or ``/etc/lava-server/lava-logs``

Each master has a local ``lava-slave`` even if that slave has no
devices configured.

* ``/etc/default/lava-slave`` or ``/etc/lava-server/lava-slave``.

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

Updates for LAVA on Debian Stretch will be uploaded to `the
stretch-backports suite <http://backports.debian.org/>`_ once this
becomes available.

Create an apt source for backports, either by editing
``/etc/apt/sources.list`` or adding a file with a ``.list`` suffix into
``/etc/apt/sources.list.d/``. Create a line like the one below (using
your preferred Debian mirror)::

 deb http://deb.debian.org/debian stretch-backports main

Remember to update your apt cache whenever add a new apt source::

 $ sudo apt update

Then install ``lava-server`` from ``stretch-backports`` using the
``-t`` option::

 $ sudo apt -t stretch-backports install lava-server
 $ sudo a2dissite 000-default
 $ sudo a2enmod proxy
 $ sudo a2enmod proxy_http
 $ sudo a2ensite lava-server.conf
 $ sudo service apache2 restart

This will also bring in other dependencies from ``stretch-backports``.
The list of packages is maintained using the
``/usr/share/lava-server/requires.py`` script in the ``lava-dev``
package::

 $ /usr/share/lava-server/requires.py -d debian -s stretch-backports -p lava-server -n
 python3-django-auth-ldap python3-django-tables2 python3-requests

Workers also need support from `stretch-backports`::

 $ /usr/share/lava-server/requires.py -d debian -s stretch-backports -p lava-dispatcher -n
 python3-requests

Once backports are enabled, the packages which the admin has selected
from backports (using the ``-t`` switch) will continue to upgrade using
backports. Other packages will only be added from backports if the
existing backports require updates from backports.

.. seealso:: :ref:`setting_up_pipeline_instance` for information on
   installing just selected packages, the full package set and a
   master without a local worker.

.. index:: buster, install using buster

.. _install_debian_buster:

Installing on Debian Buster
---------------------------

.. note:: Buster is currently Debian testing, not yet released as
   stable and frequent updates may be required. Buster will soon be
   entering the release freeze, but some breakage is still possible as
   packages may be removed from buster. For example, if a dependency of
   a LAVA package has been removed due to a release-critical bug in
   buster then all LAVA packages would also be removed from Buster.
   This would also affect the ability to install developer builds
   unless all the relevant dependencies are either already installed or
   still present in Buster. Admins can choose to use buster for
   production instances, with these constraints in mind.

Buster brings in a number of updated dependencies, e.g. postgresql-10,
docker.io and QEMU 2.12 as well as a more recent kernel. The
installation process is similar to :ref:`installing on Stretch
<install_debian_stretch>` with two differences:

* There is no need for backports as buster has no backports until after
  release.

* QEMU supports installation without the dependencies required to run a
  GUI.

If you want a smaller installation, particularly for a worker, you can
choose to install ``qemu-system-x86`` (or ``qemu-system-arm`` if
running on ``armhf`` or ``arm64``) without the recommended packages::

 $ sudo apt --no-install-recommends install qemu-system-x86

.. index:: backports, jessie-backports, install using backports

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

Setting up a reverse proxy
==========================

In order to use lava-server behind a reverse proxy, configure
lava-server as usual and then setup a reverse proxy. The following
simple Apache configuration snippet will work for most setups::

 ProxyPass / http://lava_server_dns:port/
 ProxyPassReverse / http://lava_server_dns:port/
 ProxyPreserveHost On
 RequestHeader set X-Forwarded-Proto "https" env=HTTPS

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
enforces behaviour to ensure safe use of ``https://`` which can prevent
attempts to sign in to a LAVA instance using ``http://localhost/``.

To enable localhost, you may need to disable at least these security
defaults by adding the following options to
``/etc/lava-server/settings.conf``::

  "CSRF_COOKIE_SECURE": false,
  "SESSION_COOKIE_SECURE": false

.. note:: This is the reason, if you see issues regarding CSRF token
          while trying to login with an username. The common error
          message reported is ``CSRF verification failed. Request
          aborted.``

Any changes made to ``/etc/lava-server/settings.conf`` will require a
restart of `lava-server-gunicorn` service for the changes to get
applied::

  $ sudo service lava-server-gunicorn restart

.. seealso:: :ref:`check_instance`
