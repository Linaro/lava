.. _installation:

LAVA Installation
*****************

The default install provides an Apache2 config suitable for
a LAVA server at ``http://localhost/`` once enabled.

See :ref:`packaging_distribution` for more information or for
debugging.

.. _install_types:

Installation Types
##################

.. _single_instance:

Single Master Instance installation
===================================

A single instance runs the web frontend, the database, the scheduler
and the dispatcher on a single machine. If this machine is also running
tests, the device (or devices) under test (:term:`DUT`) will also need
to be connected to this machine, possibly over the network, using
USB or using serial cables.

A single master instance can also work with a :ref:`distributed_deployment`,
acting as the web frontend and database server for multiple remote
workers. Depending on load, the master can also have devices attached.

Remote Worker installation
===========================

``lava-server`` can be configured as a remote worker, see :ref:`distributed_deployment`.
Remote workers are useful when the master instance is on a public server
or external virtual host, the remote workers and the devices can be
hosted in a separate location.

Which release to install
########################

LAVA makes regular monthly releases called ``production releases`` which
match the packages installed onto http://validation.linaro.org/. These
releases are also uploaded to Debian (see :ref:`debian_installation`).
Packages uploaded to Debian typically migrate automatically into the
current Ubuntu development release - at time of writing that is
Ubuntu Utopic Unicorn, scheduled for release as 14.10. ``production``
releases are tracked in the ``release`` branch of the upstream git
repositories.

Interim releases remain available from ``people.linaro.org`` which also
includes builds for Ubuntu Trusty Tahr 14.04LTS.

During periods when the internal transitions within Debian require that
``lava-server`` is unable to migrate into the testing suite, users
running Debian Jessie (testing) can obtain the same release using the
``people.linaro.org`` repository to provide packages which are not
present in Debian Jessie.

The ``lava-dev`` package includes scripts to assist in local developer
builds directly from local git working copies which allows for builds
using unreleased code, development code and patches under review.

If in doubt, install the ``production`` release of ``lava-server``
from official distribution mirrors.

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

Then update to locate the required dependencies::

 $ sudo apt-get install emdebian-archive-keyring
 $ sudo apt-get update

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

 $ sudo apt-get install postgresql
 $ sudo apt-get install lava
 $ sudo a2dissite 000-default
 $ sudo a2ensite lava-server.conf
 $ sudo service apache2 restart

Interim builds
==============

Interim packages can also be installed from ``people.linaro.org``::

 $ sudo apt-get install emdebian-archive-keyring
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

Software Requirements
=====================

We currently recommend using `Debian`_ unstable. Work is ongoing to support
Debian Jessie, Ubuntu Trusty, Ubuntu Unicorn and other distributions.

Support for Debian Jessie needs migrations affecting `uwsgi`_ to complete.

Dependencies of LAVA are migrating automatically into Ubuntu Unicorn
but these will need backports to be used with Trusty. Adapting LAVA to
Ubuntu builds is not currently working.

.. _Debian: http://www.debian.org/

.. _uwsgi: http://packages.qa.debian.org/u/uwsgi.html

If you'd like to help us with other distributions feel free to contact
us at linaro-validation (at) lists (dot) linaro (dot) org.

Hardware Requirements
=====================

A small LAVA instance can be deployed on any modest hardware. We
recommend at least one 1GB of RAM for runtime activity (this is
shared, on a single host, among the database server, the application
server and the web server). For storage please reserve about 20GB for
application data, especially if you wish to mirror current public LAVA
instance used by Linaro.  LAVA uses append-only models so the storage
requirements will grow at about several GB a year.

A small LAVA instance can be deployed on reasonably modest hardware. [#f2]_
We recommend:

 * At least 1GB of RAM for runtime activity (this is shared, on a single
   host, among the database server, the application server and the web server)
 * At least 20GB of storage for application data, job log files etc. in
   addition to the space taken up by the operating system.

.. rubric:: Footnotes

.. [#f1] See the section :ref:`serial_connections` for details of
         configuring serial connections to devices
.. [#f2] If you are deploying many devices and expect to be running large
         numbers of jobs, you will obviously need more RAM and disk space

Device requirements
-------------------

Devices you wish to deploy in LAVA need to be:
 * Physically connected to the server via usb, usb-serial,
   or serial [#f1]_ or
 * connected over the network via a serial console server [#f1]_ or
 * a fastboot capable device accessible from the server or
 * an emulated virtual machines and/or simulators that allow a
   serial connection

Multi-Node hardware requirements
--------------------------------

If the instance is going to be sent any job submissions from third
parties or if your own job submissions are going to use Multi-Node,
there are additional considerations for hardware requirements.

Multi-Node is explicitly about synchronising test operations across
multiple boards and running Multi-Node jobs on a particular instance
will have implications for the workload of that instance. This can
become a particular problem if the instance is running on virtualised
hardware with shared I/O, a limited amount of RAM or a limited number
of available cores.

.. note:: Downloading, preparing and deploying test images can result
 in a lot of synchronous I/O and if this instance is running the server
 and the dispatcher, running synchronised Multi-Node jobs can cause the
 load on that machine to rise significantly, possibly causing the
 server to become unresponsive.

It is strongly recommended that Multi-Node instances use a separate
dispatcher running on non-virtualised hardware so that the (possibly
virtualised) server can continue to operate.

Also, consider the number of boards connected to any one dispatcher.
MultiNode jobs will commonly compress and decompress several test image
files of several hundred megabytes at precisely the same time. Even
with a powerful multi-core machine, this has been shown to cause
appreciable load. It is worth considering matching the number of boards
to the number of cores for parallel decompression and matching the
amount of available RAM to the number and size of test images which
are likely to be in use.

A note on Heartbeat
===================
The heartbeat data of the dispatcher node is sent to the database via
xmlrpc. For this feature to work correctly the ``rpc2_url`` parameter
should be set properly. Login as an admin user and go to
``http://localhost/admin/lava_scheduler_app/worker/``. Click on the
machine which is your master (in case of distributed deployment), or
the machine that is listed in the page (in case of single LAVA instance).
In the page that opens, set the "Master RPC2 URL:" with the correct
value, if it is not set properly, already. Do not touch any other
values in this page except the description, since all the other fields
except description is populated automatically. The following figure
illustrates this:

.. image:: ./images/lava-worker-rpc2-url.png

A note on wsgi buffers
======================

When submitting a large amount of data to the django application,
it is possible to get an HTTP 500 internal server error. This problem
can be fixed by appending ``buffer-size = 65535`` to
``/etc/lava-server/uwsgi.ini``

Automated installation
======================

Using debconf pre-seeding
-------------------------

debconf can be easily automated with a text file which contains the
answers for debconf questions - just keep the file up to date if the
questions change. For example, to preseed a worker install::

 # cat preseed.txt
 lava-server   lava-worker/db-port string 5432
 lava-server   lava-worker/db-user string lava-server
 lava-server   lava-server/master boolean false
 lava-server   lava-worker/master-instance-name string default
 lava-server   lava-worker/db-server string snagglepuss.codehelp
 lava-server   lava-worker/db-pass string werewolves
 lava-server   lava-worker/db-name string lava-server

Insert the seeds into the debconf database::

 debconf-set-selections < preseed.txt

::

 # debconf-show lava-server
 * lava-worker/master-instance-name: default
 * lava-server/master: false
 * lava-worker/db-pass: werewolves
 * lava-worker/db-port: 5432
 * lava-worker/db-name: lava-server
 * lava-worker/db-server: snagglepuss.codehelp
 * lava-worker/db-user: lava-server

The strings available for seeding are in the Debian packaging for the
relevant package, in the ``debian/<PACKAGE>.templates`` file.

* http://www.debian-administration.org/articles/394
* http://www.fifi.org/doc/debconf-doc/tutorial.html

User authentication
===================

LAVA frontend is developed using Django_ web application framework
and user authentication and authorization is based on standard `Django
auth subsystems`_. This means that it is fairly easy to integrate authentication
against any source for which Django backend exists. Discussed below are
tested and supported authentication methods for LAVA.

.. _Django: https://www.djangoproject.com/
.. _`Django auth subsystems`: https://docs.djangoproject.com/en/dev/topics/auth/

Using OpenID (registration is free) allows for quick start with LAVA
bring-up and testing.

Local Django user accounts are also supported. When using local Django
user accounts, new user accounts need to be created by Django admin prior
to use.

Support for `OAuth2`_ is under investigation in LAVA.

.. _OAuth2: http://oauth.net/2/

Using Launchpad OpenID
----------------------

LAVA server by default is preconfigured to authenticate using
Launchpad OpenID service. (Launchpad has migrated from the problematic
CACert.)

Your chosen OpenID server is configured using the ``OPENID_SSO_SERVER_URL``
in ``/etc/lava-server/settings.conf`` (JSON syntax).

To use Launchpad even if the LAVA default changes, use::

 "OPENID_SSO_SERVER_URL": "https://login.ubuntu.com/",

Restart ``lava-server`` and ``apache2`` services if this is changed.

Using Google+ OpenID
--------------------

To switch from Launchpad to Google+ OpenID, change the setting for the
``OPENID_SSO_SERVER_URL`` in ``/etc/lava-server/settings.conf``
(JSON syntax)::

 "OPENID_SSO_SERVER_URL": "https://www.google.com/accounts/o8/id",

The Google+ service is already deprecated and is due to be deactivated
in September 2014 in preference for OAuth2.

Restart ``lava-server`` and ``apache2`` services for the change to
take effect.

LAVA Dispatcher network configuration
=====================================

``/etc/lava-dispatcher/lava-dispatcher.conf`` supports overriding the
``LAVA_SERVER_IP`` with the currently active IP address using a list of
network interfaces specified in the ``LAVA_NETWORK_IFACE`` instead of a
fixed IP address, e.g. for LAVA installations on laptops and other devices
which change network configuration between jobs. The interfaces in the
list should include the interface which a remote worker can use to
serve files to all devices connected to this worker.

.. _serial_connections:

Setting Up Serial Connections to LAVA Devices
=============================================

.. _ser2net:

Ser2net daemon
--------------

ser2net provides a way for a user to connect from a network connection
to a serial port, usually over telnet.

http://ser2net.sourceforge.net/

``ser2net`` is a dependency of ``lava-dispatcher``, so will be
installed automatically.

Example config (in /etc/ser2net.conf)::

 #port:connectiontype:idle_timeout:serial_device:baudrate databit parity stopbit
 7001:telnet:36000:/dev/serial_port1:115200 8DATABITS NONE 1STOPBIT

StarTech rackmount usb
----------------------

W.I.P

* udev rules::

   SUBSYSTEM=="tty", ATTRS{idVendor}=="0403", ATTRS{idProduct}=="6001", ATTRS{serial}=="ST167570", SYMLINK+="rack-usb02"
   SUBSYSTEM=="tty", ATTRS{idVendor}=="0403", ATTRS{idProduct}=="6001", ATTRS{serial}=="ST167569", SYMLINK+="rack-usb01"
   SUBSYSTEM=="tty", ATTRS{idVendor}=="0403", ATTRS{idProduct}=="6001", ATTRS{serial}=="ST167572", SYMLINK+="rack-usb04"
   SUBSYSTEM=="tty", ATTRS{idVendor}=="0403", ATTRS{idProduct}=="6001", ATTRS{serial}=="ST167571", SYMLINK+="rack-usb03"

This will create a symlink in /dev called rack-usb01 etc. which can then be addressed in the :ref:`ser2net` config file.

Contact and bug reports
========================

Please report bugs using bugzilla:
https://bugs.linaro.org/enter_bug.cgi?product=LAVA%20Framework

You can also report bugs using ``reportbug`` and the
Debian Bug Tracking System: https://bugs.debian.org/cgi-bin/pkgreport.cgi?pkg=lava-server

Feel free to contact us at validation (at) linaro (dot) org and on
the ``#linaro-lava`` channel on OFTC.

Distributed deployment
######################

.. toctree::
   :maxdepth: 2

   distributed-deployment.rst

Migrating existing LAVA instances
#################################

.. toctree::
   :maxdepth: 2

   migration.rst
