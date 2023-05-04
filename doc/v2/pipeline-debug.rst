.. index:: administrator debugging, debugging V2 instance

.. _debugging_v2:

Administrator debugging
#######################

Debugging a LAVA instance
*************************

.. _debugging_components:

Components
==========

Each of these components has a service which may need to be restarted when
making changes. Each of these services are restarted when the relevant packages
are installed.

* **lava-server** - the frontend UI and admin interface. If using apache
  use ``apache2ctl restart`` when changing any of the django files, device type
  templates or lava-server settings::

   $ sudo apache2ctl restart

* **worker** - each dispatcher worker connects to the server using HTTP and
  follows the instructions of the server, using configuration specified by the
  server. Restart is rarely needed, usually only when changing the dispatcher
  code related to HTTP or the loghandler::

   $ sudo service lava-worker restart

The worker have dedicated singleton processe which should be put
into loglevel ``DEBUG`` when investigating problems.
Restart the service after editing the service file.

* **worker** ``/etc/init.d/lava-worker`` currently defaults to DEBUG.

.. debugging_log_files:

Log files
=========

All log files use ``logrotate``, so the information you need may be in a
``log.1`` or ``log.2.gz`` file - typically up to ``log.9.gz``. Use ``zless`` or
``zgrep`` for older log files.

* **apache** - ``/var/log/apache2/lava-server.log``

* **django** - by default ``/var/log/lava-server/django.log`` contains
  errors and warnings from django.

* **scheduler** - ``/var/log/lava-server/lava-scheduler.log``

* **worker** - ``/var/log/lava-dispatcher/lava-worker.log``.

* **test jobs** - ``/var/lib/lava-server/default/media/job-output/``
  individual files are in a directory named after the start time of the
  corresponding job ``<year>/<month>/<day/$ID``, e.g. ``2018/08/10/1234``.
  The directory includes the validation output ``description.yaml`` and the
  full log file ``output.yaml``.

.. _debugging_cli:

Command line debugging
======================

* **lava-server** - ``sudo lava-server manage shell``.

  .. seealso:: :ref:`developer_access_to_django_shell`

* **lava-dispatcher** - The actions of ``lava-worker`` can be replicated
  on the command line. The relevant device configuration can be obtained using
  ``lavacli``, e.g.::

   $ lavacli devices dict get --render DEVICE_HOSTNAME

  This config can then be passed to ``lava-run``, in this example in a
  file named ``device.yaml``::

   $ sudo lava-run --device device.yaml --output-dir /tmp/debug/ job.yaml

  Every job is validated before starting and the validate check can be run
  directly by adding the ``--validate`` option::

   $ sudo lava-run --job-id 0 --device device.yaml --validate --output-dir /tmp/debug/ job.yaml

  The job will not start when ``--validate`` is used - if validation passes,
  the complete pipeline will be described. If errors are found, these will be
  output.

.. _debugging_configuration:

Configuration files
===================

* **lava-server** - ``/etc/lava-server/settings.conf`` - restart ``apache``
  and ``lava-server`` if this is changed. Holds details for django settings
  including the authentication methods and site customization settings.

* **jinja2 templates** - ``/etc/lava-server/dispatcher-config/device-types``
  These files are updated from ``lava_scheduler_app/tests/device-types``
  in the codebase. The syntax is YAML with jinja2 markup. Restart the
  ``lava-master`` after changing the templates.

  * to validate changes to the templates, use::

    $ /usr/share/lava-server/validate_devices.py --instance localhost

  * to validate the combination of the template with the device
    dictionary content, use::

     $ lavacli devices dict get --render DEVICE_HOSTNAME

* **device dictionaries** - ``/etc/lava-server/dispatcher-config/devices``
  These files are specific to each instance and need to be named according to
  the ``hostname``.jinja2 of the device as configured on the same instance.

.. _check_instance:

Check LAVA instance
===================

Once a LAVA instance is installed admins can check for errors and warnings on the
deployed instance using::

  $ sudo lava-server manage check --deploy

The ``check --deploy`` command uses the Django system check framework which is a
set of static checks to detect common problems and provide hints for how to fix
them.

.. seealso:: https://docs.djangoproject.com/en/3.2/ref/checks/ to know more
             about Django system check framework.

If the JSON syntax of ``/etc/lava-server/settings.conf`` is invalid,
this check will display a warning: ``settings.conf is not a valid json
file``.

LAVA sets the following values by default::

  SECURE_CONTENT_TYPE_NOSNIFF = True
  SECURE_BROWSER_XSS_FILTER = True
  SESSION_COOKIE_SECURE = True
  CSRF_COOKIE_SECURE = True
  CSRF_COOKIE_HTTPONLY = True
  X_FRAME_OPTIONS = 'DENY'

These values can be overridden in ``/etc/lava-server/settings.conf``

The following checks are silenced and does not show any errors or warnings:

* SECURE_HSTS_SECONDS i.e., security.W004 which is documented in https://docs.djangoproject.com/en/3.2/ref/settings/#secure-hsts-seconds
* SECURE_SSL_REDIRECT i.e., 'security.W008' which is documented in https://docs.djangoproject.com/en/3.2/ref/settings/#secure-ssl-redirect

.. note:: Admins should consult the respective Django documentation before changing these
   values to suit the requirements of each LAVA instance.

.. seealso:: :ref:`django_localhost`

.. _diff_settings:

Displaying current settings
===========================

The django developer shell can be used to check the value which is
currently set:

.. code-block:: none

  $ sudo lava-server manage shell
  Python 3.6.7 (default, Oct 21 2018, 08:08:16)
  [GCC 8.2.0] on linux
  Type "help", "copyright", "credits" or "license" for more information.
  (InteractiveConsole)

.. code-block:: python

  >>> from django.conf import settings
  >>> settings.CSRF_COOKIE_HTTPONLY
  False

.. seealso:: :ref:`developer_access_to_django_shell`

.. caution:: Avoid making changes to the defaults inside the LAVA code.
   These will be replaced when you upgrade to future versions of the
   lava-server package. If you need to make changes, instead edit
   ``/etc/lava-server/settings.conf`` where they will be preserved.
   Whenever you make changes, be sure to restart the LAVA daemons
   before checking for the effects of the change::

    $ sudo service lava-server-gunicorn restart

   In some situations, you may also need to restart ``lava-scheduler``,
   ``lava-server-gunucorn`` and ``lava-publisher`` in the same way.

   .. seealso:: Installing a new release or a set of :ref:`Developer
      packages <testing_packaging>` will also restart all LAVA daemons.

Django support in 1.11
----------------------

If your local instance is using ``python3-django`` from ``buster``, the new
support in 1.11 and later can be used to display the settings as well::

 $ sudo lava-server manage diffsettings --all

.. seealso:: https://docs.djangoproject.com/en/3.2/ref/django-admin/#diffsettings

Settings that don’t appear in the defaults are followed by "###",
e.g.::

 BRANDING_MESSAGE = 'Master branch instance on Debian Buster.'  ###

.. danger:: Access to ``lava-server manage`` needs to be restricted
   in the same way as read permissions on
   ``/etc/lava-server/settings.conf`` as the current settings will
   include the **database secret_key**, authentication passwords for
   services like LDAP and other sensitive information.
