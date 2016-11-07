.. index:: administrator debugging, debugging V2 instance

.. _debugging_v2:

Administrator debugging
#######################

Debugging a LAVA V2 instance
****************************

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

* **scheduler daemon** - from V1 but still used in V2 for the assignment
  of devices to testjobs. Restart when changing django files in
  ``lava_scheduler_app``::

   $ sudo service lava-server restart

* **master** - the dispatcher master, controlling the slaves using ZMQ. The
  master does the pipeline validation. Restart when changing the dispatcher
  code (as the master runs the validation check using the dispatcher code)::

   $ sudo service lava-master restart

* **slave** - each dispatcher slave connects to the master using ZMQ and
  follows the instructions of the master, using configuration specified by the
  master. Restart is rarely needed, usually only when changing the dispatcher
  code related to ZMQ or the loghandler::

   $ sudo service lava-slave restart

The scheduler daemon, master and slave all have dedicated singleton processes
which should be put into loglevel ``DEBUG`` when investigating problems.
Restart the service after editing the service file.

* **scheduler daemon** ``/etc/init.d/lava-server`` - enable debug::

   LOGLEVEL="--loglevel=debug"

* **master** ``/etc/init.d/lava-master`` currently defaults to DEBUG
  log level.

* **slave** ``/etc/init.d/lava-slave`` currently defaults to DEBUG.

.. debugging_log_files:

Log files
=========

All log files use ``logrotate``, so the information you need may be in a
``log.1`` or ``log.2.gz`` file - typically up to ``log.9.gz``. Use ``zless`` or
``zgrep`` for older log files.

* **apache** - ``/var/log/apache2/lava-server.log``

* **django** - by default ``/var/log/lava-server/django.log`` contains
  errors and warnings from django.

* **scheduler daemon** - ``/var/log/lava-server/lava-scheduler.log``

* **master** - ``/var/log/lava-server/lava-master.log``

* **slave** - ``/var/log/lava-dispatcher/lava-slave.log``.

* **test jobs** - ``/var/lib/lava-server/default/media/job-output/``
  individual files are in a directory named ``job-$ID``, e.g. ``job-1234``.
  Individual log files from each action in the pipeline are kept in the
  ``pipeline`` directory with directories for each top level of the pipeline.
  Other files include the validation output ``description.yaml`` and the full
  log file ``output.txt``. Unlike other logs, ``output.txt`` can include escape
  characters and other elements which can confuse some text editors which try
  to identify the encoding of the file when no encoding was used when the file
  was written.

.. _debugging_cli:

Command line debugging
======================

* **lava-server** - ``sudo lava-server manage shell``.

  .. seealso:: :ref:`developer_access_to_django_shell`

* **lava-dispatcher** - The actions of ``lava-slave`` can be replicated
  on the command line. The relevant device configuration can be obtained using
  ``lava-tool``, e.g.::

   $ lava-tool get-pipeline-device-config --stdout SERVER DEVICE_HOSTNAME

  This config can then be passed to ``lava-dispatch``, in this example in a
  file named ``device.yaml``::

   $ sudo lava-dispatch --target device.yaml --output-dir /tmp/debug/ job.yaml

  Every job is validated before starting and the validate check can be run
  directly by adding the ``--validate`` option::

   $ sudo lava-dispatch --target device.yaml --validate --output-dir /tmp/debug/ job.yaml

  The job will not start when ``--validate`` is used - if validation passes,
  the complete pipeline will be described. If errors are found, these will be
  output.

.. _debugging_configuration:

Configuration files
===================

* **lava-server** - ``/etc/lava-server/settings.conf`` - restart ``apache``
  and ``lava-server`` if this is changed. Holds details for django settings
  including the authentication methods and site customisation settings.

* **jinja2 templates** - ``/etc/lava-server/dispatcher-config/device-types``
  These files are updated from ``lava_scheduler_app/tests/device-types``
  in the codebase. The syntax is YAML with jinja2 markup. Restart the
  ``lava-master`` after changing the templates.

  * to validate changes to the templates, use::

    $ /usr/share/lava-server/validate_devices.py --instance localhost

  * to validate the combination of the template with the device
    dictionary content, use::

     $ lava-tool get-pipeline-device-config --stdout SERVER DEVICE_HOSTNAME
