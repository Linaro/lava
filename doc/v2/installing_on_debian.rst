.. _debian_installation:

Debian-based distributions
##########################

These instructions cover installation on Debian. The supported
versions are:

+---------------+------------------------+--------+----------------------+
| Distribution  | Codename               | Number | Support              |
+===============+========================+========+======================+
| Debian        | experimental           | n/a    | Yes [#f1]_           |
+---------------+------------------------+--------+----------------------+
| Debian        | Sid (unstable)         | n/a    | Yes                  |
+---------------+------------------------+--------+----------------------+
| Debian        | Stretch (testing)      | n/a    | [#f2]_               |
+---------------+------------------------+--------+----------------------+
| Debian        | Jessie (stable)        | 8.0    | Yes [#f3]_           |
+---------------+------------------------+--------+----------------------+

Debian uses codenames for releases (Jessie, wheezy, squeeze) and names
for `suites`_ (unstable, testing, stable & oldstable). When a new
Debian major release is made, the packages in "testing" are frozen and
become the new "stable". A new codename is chosen for the new
"testing" suite, and that will be the name for the next major release
in the cycle.

To allow the table to refer to the same package versions consistently
over time, codenames are used here. When a Debian release is made, a
new codename is applied to the testing suite and LAVA releases after
that point will include that codename in the table.

.. note:: LAVA used to be supported on Ubuntu directly, but is not any
          more due to lack of resources to maintain and test that
          support. Support may be re-instated if more effort becomes
          available in the future. The last version of LAVA supported
          in Ubuntu was **2015.9.post1**.

.. _suites: http://en.wikipedia.org/wiki/Debian#Branches

.. [#f1] `experimental`_ allows updates to be selected on top of
         unstable (or the current testing) during times when testing
         is frozen ahead of a release of Debian stable. Experimental
         will typically have no LAVA packages outside of a Debian
         release freeze.
.. [#f2] `stretch` is the name of the next Debian release after Jessie,
         which is supported automatically via uploads to Sid (unstable).
.. [#f3] Jessie was released on April 25th, 2015. All updates to LAVA packages
         for Jessie will be made using `jessie-backports`_. Systems using
         Debian Jessie are recommended to enable jessie-backports. LAVA packages
         and dependencies which are installed using jessie-backports are
         **fully supported** by upstream and are the same codebase as the
         relevant production release available from the :ref:`lava_repositories`.

.. _experimental: https://wiki.debian.org/DebianExperimental

.. _jessie-backports: http://backports.debian.org/

You can track the versions of LAVA packages in the various Debian
suites by following links from the Debian package trackers for
`lava-dispatcher <https://tracker.debian.org/pkg/lava-dispatcher>`_
and `lava-server <https://tracker.debian.org/pkg/lava-server>`_.

.. _lava_repositories:

LAVA repositories
=================

As well as being uploaded to Debian, :ref:`production_releases` of LAVA
are uploaded to a Linaro `production-repo`_ repository which uses the
:ref:`lava_archive_signing_key` - a copy of the key is available in
the repository.

.. _production-repo: https://images.validation.linaro.org/production-repo/

In times when the current production release has not made it into
``jessie-backports`` (e.g. due to a migration issue or a pre-release
package freeze in Debian), this repository can be used instead. The
**only** apt source to use with Debian Jessie, Stretch or Sid is the
`production-repo`_ for ``sid`` because the same LAVA packages are used
on Jessie and Stretch as on Sid::

 deb https://images.validation.linaro.org/production-repo sid main

.. note:: There are no packages currently in the repository
   except in ``sid``.

The codename ``sid`` is used simply as that is the codename for
``unstable`` which is where all Debian uploads arrive. To allow the
production repo to include precisely the same upload as was made to
Debian, we use ``sid``. It makes no difference to how the packages are
installed on Jessie, Stretch or Sid.

The :file:`services-trace.txt` file in the repository shows the latest
update timestamp and is accompanied by a GnuPG signature of the trace
file, signed using the :ref:`lava_archive_signing_key`.

Interim builds (including release candidates) are available in the
staging repository::

 deb https://images.validation.linaro.org/staging-repo sid main

This repository uses the same key as the production repository and
uses ``sid`` in the same way.

.. _production_releases:

Production releases
===================

.. seealso:: :ref:`setting_up_pipeline_instance`.

LAVA is currently packaged for Debian unstable using Django1.7 and
Postgresql. LAVA packages are now available from official Debian
mirrors for Debian unstable. e.g. to install the master, use::

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

The LAVA V1 dispatcher **relies** on TFTP downloads, NFS share
directories and master image downloads to **all** be made from a
single directory: :file:`/var/lib/lava/dispatcher/tmp`. To do this,
the configuration file for :command:`tftpd-hpa` needs to be modified
to use the LAVA directory instead of the default, ``/srv/tftp``.

.. note:: The TFTP support in LAVA has had to be changed from the
   **2015.8 release** onwards to stop LAVA enforcing a configuration
   change on the ``tftpd-hpa`` package without explicit configuration
   by the admin. Previously, installation may have prompted about
   changes in :file:`/etc/default/tftpd-hpa`; now this change needs
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

If you are planning to support V1 devices, this change will be
required in whichever Debian-based distribution you use as your base
install, including Ubuntu.

In LAVA V2, behaviour has changed here. In whatever base directory is
configured for ``tftpd-hpa``, LAVA will use temporary subdirectories
for all TFTP operations; other LAVA operations will use the
:file:`/var/lib/lava/dispatcher/tmp` directory. If **all** of your
devices are :term:`exclusive`, to V2 (:term:`pipeline`), then the
``tftpd-hpa`` configuration can be set to the tftpd original value
(``/srv/tftp``), the LAVA historical value
(``/var/lib/lava/dispatcher/tmp``) or any other directory specified by
the admin.

Extra dependencies
------------------

The ``lava`` metapackage brings in extra dependencies which may be
useful on some instances.

.. _install_debian_jessie:

Installing on Debian Jessie
---------------------------

Debian Jessie was released on April 25th, 2015, containing a full set
of packages to install LAVA.

Updates are uploaded to `jessie-backports <http://backports.debian.org/>`_

Create an apt source for backports (use your preferred Debian mirror)::

 deb http://http.debian.net/debian jessie-backports main

Remember to update your apt cache whenever add a new apt source::

 $ sudo apt update

Then upgrade or install ``lava-server`` from ``jessie-backports`` using
the ``-t`` option::

 $ sudo apt -t jessie-backports install lava-server

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

 $ wget https://images.validation.linaro.org/staging-repo/staging-repo.key.asc
 $ sudo apt-key add staging-repo.key.asc
 OK

Then update to locate the required dependencies::

 $ sudo apt update

.. _downloaded: https://images.validation.linaro.org/staging-repo/staging-repo.key.asc

Installing just lava-server
===========================

The ``lava-server`` package is the main LAVA scheduler and frontend.

.. seealso:: :ref:`setting_up_pipeline_instance`.

To install just the lava-server from the current packages, use::

 $ sudo apt install lava-server
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

 $ sudo apt install postgresql
 $ sudo apt install lava
 $ sudo a2dissite 000-default
 $ sudo a2ensite lava-server.conf
 $ sudo service apache2 restart

Upgrading LAVA packages on Jessie
=================================

Updates are uploaded to `jessie-backports <http://backports.debian.org/>`_

::

 deb http://http.debian.net/debian jessie-backports main

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

If you want the application to answer on a specific base URL,
configure lava-server to answer on this base URL and then configure
the reverse proxy to proxify the same base URL. For instance you can
have::

  http://example.com/lava => http://lava.example.com/lava

Having two different base URLs is more awkward to setup. In this case
you will have to also setup Apache modules like `Substitute` to alter
the HTML content on the fly. This is not a recommended setup.

.. _create_superuser:

Superuser
=========

OpenID or LDAP
--------------

In LAVA instances that use external authentication mechanisms such as
OpenID or LDAP, log in once with the user account that will be granted
superuser privileges in the LAVA web UI. After logging in with OpenID
or LDAP successfully, make use of the following command to make this
user a superuser::

  $ sudo lava-server manage authorize_superuser --username {username}

.. note:: `{username}` is the username of OpenID or LDAP user.

LDAP
----

Alternatively, in LAVA instances that use LDAP as authentication
mechanism, the `addldapuser` command can be used to populate a user
from LDAP and also grant superuser privilege as follows::

  $ sudo lava-server manage addldapuser --username {username} --superuser

.. note:: `{username}` is the username of LDAP user.

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

