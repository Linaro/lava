.. _setting_up_pipeline_instance:

Setting up a LAVA instance
##########################

The LAVA design designates the machine running Django and PostgreSQL as
the ``lava-server`` and all other machines connected to that server
which will actually be running the jobs are termed ``lava-worker``
machines.

Installing just lava-server
***************************

The ``lava-server`` package is the main LAVA scheduler and frontend.

To install just the lava-server from the current packages, use::

 $ sudo apt install lava-server
 $ sudo a2dissite 000-default
 $ sudo a2enmod proxy
 $ sudo a2enmod proxy_http
 $ sudo a2ensite lava-server.conf
 $ sudo service apache2 restart

This will install lava-dispatcher and lava-server.

Other packages to consider:

* ``ntp`` - some actions within LAVA can be time-sensitive, so ensuring
  that devices within your lab keep time correctly can be important.

.. note:: There is no support in V2 for ``linaro-media-create`` to
   manipulate hardware packs from Linaro, so this package can be
   removed once there are no V1 devices on the worker.

Installing the full lava set
****************************

Production installs of LAVA will rarely use the full ``lava`` set as it
includes tools more commonly used by developers and test labs. These
tools mean that the ``lava`` package brings more dependencies than when
installing ``lava-server`` to run a production LAVA instance.

.. note:: Debian has the concept of Dependencies which must be
   installed and Recommends which are optional but expected to be
   useful by most users of the package in question.  Opting out of
   installing Recommends is supported when installing packages, so if
   admins have concerns about extra packages being installed on the
   slaves (e.g. if using ARMv7 slaves or simply to reduce the
   complexity of the install) then Recommends can be omitted for the
   installation of these dependencies.

   .. seealso:: `Debian Policy: What is meant by saying that a package
      Depends, Recommends, Suggests, Conflicts, Replaces, Breaks or
      Provides another package?
      <https://www.debian.org/doc/manuals/debian-faq/ch-pkg_basics.en.html#s-depends>`_
      and `details of the lava package in Debian
      <https://packages.debian.org/sid/lava>`_

The ``lava`` package installs support for:

* ``lava-dev`` - scripts to build developer packages based on your
  current git tree of ``lava-server`` or ``lava-dispatcher``, including
  any local changes.

  .. note:: ``lava-dev`` includes **a lot** of packages which are not
     typically used on a production master or worker.

* ``vmdebootstrap`` for building your own Debian based KVM images.

* ``ntp`` - some actions within LAVA can be time-sensitive, so ensuring
  that devices within your lab keep time correctly can be important.

.. note:: There is no support in V2 for ``linaro-media-create`` to
   manipulate hardware packs from Linaro, so this package can be
   removed once there are no V1 devices on the worker.

All of these packages can be installed separately alongside the main
``lava-server`` package, the ``lava`` package merely collects them into
one set.

::

 $ sudo apt install postgresql
 $ sudo apt install lava
 $ sudo a2dissite 000-default
 $ sudo a2enmod proxy
 $ sudo a2enmod proxy_http
 $ sudo a2ensite lava-server.conf
 $ sudo service apache2 restart

.. seealso:: :ref:`Creating a superuser <create_superuser>`, :ref:`logging_in`,
   :ref:`authentication_tokens` and the :ref:`first job definition
   <first_job_definition>`.

.. _server_without_recommends:

Installing master without Recommends
************************************

The ``lava-common`` binary package is new in 2018.5 and allows admins
to choose not to install ``lava-dispatcher`` on the master if there are
to be no devices assigned to the machine running ``lava-master``. This
is common for installations where there are multiple workers and the
master is regularly busy. ``lava-server`` now _Recommends_
``lava-dispatcher`` which means that admins can choose not to install
it alongside ``lava-server``::

 $ sudo apt --no-install-recommends install lava-server lava-server-doc

Depending on the local configuration, some of the other recommended
packages may also be desirable:

* **lava-coordinator**
* **ntp**

``lava-server-doc`` can be omitted but this would be unusual -
instances would need to be configured to have some other Help option in
the menu using the ``CUSTOM_DOCS`` dictionary setting in
``/etc/lava-server/settings.conf`` and the ``Help`` links from pages
within the LAVA UI would cause a 404 error for users, unless the
Apache configuration was adjusted.

.. seealso:: `Debian Policy: What is meant by saying that a package
   Depends, Recommends, Suggests, Conflicts, Replaces, Breaks or
   Provides another package?
   <https://www.debian.org/doc/manuals/debian-faq/ch-pkg_basics.en.html#s-depends>`_

.. _configuring_lava_slave:

Installing lava-dispatcher
**************************

If this machine is only meant to be a dispatcher for connected devices,
then just install ``lava-dispatcher``. The ``lava-server`` package is
only needed on the master in each LAVA instance.

::

 $ sudo apt install lava-dispatcher

#. Change the dispatcher configuration in
   ``/etc/lava-dispatcher/lava-worker`` to allow ``lava-worker`` to connect to
   the relevant ``lava-server`` instead of ``localhost``::

     /etc/lava-dispatcher/lava-worker

     # Configuration for lava-worker daemon

     # worker name
     # Should be set for host that have random hostname (containers, ...)
     # The name can be any unique string.
     # WORKER_NAME="--name <hostname.fqdn>"

     # Logging level should be uppercase (DEBUG, INFO, WARN, ERROR)
     # LOGLEVEL="DEBUG"

     # Server connection
     # URL="http://localhost/"
     # TOKEN="--token <token>"
     # WS_URL="--ws-url http://localhost/ws/"

#. Restart ``lava-worker`` once the changes are complete::

    $ sudo service lava-worker restart

#. The administrator of the master will then be able to allocate
   pipeline devices to this slave.

.. note:: For security reasons, the slave does not declare the devices
   connected to it to the master. The LAVA configuration on the worker
   actually needs no knowledge of what is connected or where as long as
   services like ``ser2net`` are configured. All the LAVA configuration
   data is stored solely in the database of the master. Once this data
   is entered by the admin of the master, the worker then needs to
   connect and the admin can then select that slave for the relevant
   devices. Once selected, the worker can immediately start running
   pipeline jobs on those devices.

The administrator of the master will require the following information
about the devices attached to each slave:

#. Confirmation that a suitable template already exists, for each
   device i.e. :ref:`adding_known_device`

#. A completed and tested :term:`device dictionary` for each device.

This information contains specific information about the local network
setup of the slave and will be transmitted between the master and the
worker in **clear text** over HTTP. Any encryption would need to
be arranged separately between the slave and the master. Information
typically involves the hostname of the PDU, the port number of the
device on that PDU and the port number of the serial connection for
that device. The slave is responsible for ensuring that these ports are
only visible to that slave. There is no need for any connections to be
visible to the master.

.. index:: worker - apache config

.. _apache2_on_v2_only_worker:

Configuring apache2 on a worker
*******************************

Some test job deployments will require a working Apache2 server to
offer deployment files over the network to the device::

    $ sudo cp /usr/share/lava-dispatcher/apache2/lava-dispatcher.conf /etc/apache2/sites-available/
    $ sudo a2ensite lava-dispatcher
    $ sudo service apache2 restart
    $ wget http://localhost/tmp/
    $ rm index.html

You may also need to disable any existing apache2 configuration if this
is a default apache2 installation::

    $ sudo a2dissite 000-default
    $ sudo service apache2 restart

.. _adding_pipeline_workers:

Adding workers to the master
****************************

A new worker needs to be manually added to the master so that the
admins of the master have the ability to assign devices in the database
and enable or disable the worker.

To add a new worker::

 $ sudo lava-server manage workers add <HOSTNAME>

To add a worker with a description::

 $ sudo lava-server manage workers add --description <DESC> <HOSTNAME>

To add a worker in a disabled state::

 $ sudo lava-server manage workers add --description <DESC> --disabled <HOSTNAME>

Workers are enabled or disabled in the Django admin interface by
changing the ``display`` field of the worker. Jobs submitted to devices
on that worker will fail, so it is also recommended that the devices
would be made offline at the same time. (The django admin interface has
support for selecting devices by worker and taking all selected devices
offline in a single action.)

.. seealso:: :ref:`create_device_database`

.. _adding_pipeline_devices_to_worker:

Adding devices to a worker
**************************

Admins use the Django admin interface to add devices to workers using
the worker drop-down in the device detail page.

.. note:: A worker may have a description but does not have a record of
   the IP address, uptime or architecture in the Worker object.
