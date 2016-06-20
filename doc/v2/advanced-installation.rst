.. _advanced_installation:

Advanced Installation Topics
****************************

The basic :ref:`installation` guide should be a good start for most users
installing LAVA. For more advanced users, here is much more
information and recommendations for administrators.

Requirements to Consider Before Installing LAVA
###############################################

Architecture
============

.. include:: architecture-v2.rsti

.. _more_installation_types:

Recommended Installation Types
##############################

FIXME - need content

A note on wsgi buffers
======================

When submitting a large amount of data to the django application,
it is possible to get an HTTP 500 internal server error. This problem
can be fixed by appending ``buffer-size = 65535`` to
``/etc/lava-server/uwsgi.ini``

.. _automated_installation:

Automated installation
======================

Using debconf pre-seeding with Debian packages
----------------------------------------------

Debconf can be easily automated with a text file which contains the
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

Insert the preseed information into the debconf database::

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

.. _branding:

LAVA server branding support
============================

The icon, link and alt text of the LAVA link on each page can be changed in the
settings ``/etc/lava-server/settings.conf`` (JSON syntax)::

   "BRANDING_URL": "http://www.example.org",
   "BRANDING_ALT": "Example site",
   "BRANDING_ICON": "https://www.example.org/logo/logo.png",
   "BRANDING_HEIGHT": 26,
   "BRANDING_WIDTH": 32

If the icon is available under the django static files location, this location
can be specified instead of a URL::

   "BRANDING_ICON": "path/to/image.png",

There are limits to the size of the image, approximately 32x32 pixels, to avoid
overlap.

The ``favicon`` is configurable via the Apache configuration::

 Alias /favicon.ico /usr/share/lava-server/static/lava-server/images/linaro-sprinkles.png

LAVA Dispatcher network configuration
=====================================

``/etc/lava-dispatcher/lava-dispatcher.conf`` supports overriding the
``LAVA_SERVER_IP`` with the currently active IP address using a list of
network interfaces specified in the ``LAVA_NETWORK_IFACE`` instead of a
fixed IP address, e.g. for LAVA installations on laptops and other devices
which change network configuration between jobs. The interfaces in the
list should include the interface which a remote worker can use to
serve files to all devices connected to this worker.

