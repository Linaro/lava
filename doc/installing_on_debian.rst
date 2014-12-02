.. _debian_installation:

Debian-based distributions
##########################

Production releases
===================

LAVA is currently packaged for Debian unstable using Django1.6 and
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

Debian Jessie is currently unreleased and is therefore a rolling suite
called ``testing``. This means that some dependencies of LAVA may be
temporarily removed from Jessie to assist in the development of the
final release.

The ``jessie`` suite of the ``people.linaro.org`` repository contains
copies of all the dependencies, so add this apt source to allow LAVA
to install on a system running Debian Jessie::

 deb http://people.linaro.org/~neil.williams/lava jessie main

.. _lava_archive_signing_key:

LAVA Archive signing key
^^^^^^^^^^^^^^^^^^^^^^^^

This archive is signed using key 0x7C751B3F which can be
downloaded_ and added to apt::

 $ wget http://people.linaro.org/~neil.williams/lava/0x7C751B3F.asc
 $ sudo apt-key add 0x7C751B3F.asc
 OK

Then update to locate the required dependencies::

 $ sudo apt-get update

.. _downloaded: http://people.linaro.org/~neil.williams/lava/0x7C751B3F.asc

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

Upgrading after the Jessie release
----------------------------------

Debian Jessie is due to go into a release freeze in November 2014. At this
point, it will not be possible to update the version of lava packages
in the Jessie release. (A separate repository will be made available at that
time.) Once Jessie is released, future updates of LAVA packages can be
backported to Jessie.

Interim builds
==============

See also :ref:`lava_archive_signing_key`

Interim packages can also be installed from ``people.linaro.org``::

 $ sudo apt-get update

Add the ``people.linaro.org`` LAVA source. Usually, you can just create
a file called ``lava.list`` in ``/etc/apt/sources.list.d/``
containing::

 deb http://people.linaro.org/~neil.williams/lava sid main

Update your apt sources to find the LAVA packages::

 $ sudo apt-get update

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

Installing on Ubuntu Utopic Unicorn
-----------------------------------

Ubuntu Unicorn (which is due to be released as 14.10) has received
updates from Debian up to the 2014.07 release. Future production
releases of LAVA will migrate into the next Ubuntu codename after
Unicorn. Installing on Unicorn is the same as :ref:`install_debian_jessie`.
The full set of architectures are supported, just as with Debian Jessie.

See also :ref:`lava_on_debian` for information on building LAVA packages
of your own as LAVA will not be making backports to Unicorn.

Installing on Ubuntu Trusty Tahr 14.04 LTS
------------------------------------------

.. note:: Only 64bit installations are supported for Ubuntu Trusty
          and not all production hot fixes may actually get uploaded
          to the repository.

Various package dependencies are needed on Trusty. These can be installed
from people.linaro.org but newer versions also exist in Ubuntu Unicorn.

::

 deb http://people.linaro.org/~neil.williams/lava jessie main

This repository contains an old version of LAVA but once this version
is installed, updated versions of lava-server and lava-dispatcher can
be obtained from::

 deb [arch=amd64] http://images.validation.linaro.org/trusty-repo trusty main

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
