.. _packaging_distribution:

Packaging lava-server for distributions
***************************************

.. warning:: This chapter discusses a model of deployment
   which is being superceded by the :term:`pipeline` model.
   See :ref:`setting_up_pipeline_instance`.

Apache distribution support
###########################

::

 /etc/apache2/sites-available/lava-server.conf

Aimed at apache2.4 with comments for apache2.2 usage. Edit where necessary
and then enable and restart apache to use.

.. _admin_helpers:

Instance name
#############

#. Only one instance can be running at any one time.
#. Instance templates share a common folder: /usr/share/lava-server/templates

Further information
###################

* http://wiki.debian.org/LAVA
* https://wiki.linaro.org/LAVA/LAVA_packaging
* https://github.com/Linaro

.. _packaging_components:

LAVA Components
###############

=============== =========================================
lava            meta-package for single instance setup
lava-server     apache and WSGI settings and HTML content
lava-dispatcher dispatches jobs to devices
=============== =========================================

Package dependencies
====================

Take note of the Debian dependencies - not all are available with
pypi and not all are necessarily available in your distribution. A
large part of packaging LAVA for a distribution is taking on the
maintenance of a variety of dependency modules and packages which do
not (yet) exist in the distribution.

Depending on how the distribution is organised, it may take a significant
amount of time to get the dependencies uploaded and available in the
appropriate suite, release or location. Many of these dependencies will
also depend on new packages, so the order of uploads will have to be
identified in advance.

.. _packaging_daemon_renaming:

Daemon renaming
===============

The main scheduler daemon is now explicitly named and only restarts
the scheduler daemon::

 $ sudo service lava-server restart

The web application itself is handled within apache, so to refresh
the code running behind the front end, use::

 $ sudo apache2ctl restart

The ``LAVA_SYS_USER`` has also been renamed from an instance-specific
name to ``lavaserver``. ``lava-server manage`` can also be run as a
normal user or by root. The system user is used just for the filesystem
permissions.

WSGI debugging help
===================

https://code.google.com/p/modwsgi/wiki/DebuggingTechniques

If you get a 502 bad gateway, the uwsgi is probably not setup.
