.. _setting_up_pipeline_instance:

Setting up a LAVA instance
##########################

The LAVA design designates the machine running Django and PostgreSQL as 
the ``lava-master`` and all other machines connected to that master 
which will actually be running the jobs are termed ``lava-slave`` 
machines.

.. _dependencies_recommends:

Dependencies and recommends
***************************

Debian has the concept of Dependencies which must be installed and 
Recommends which are optional but expected to be useful by most users 
of the package in question.  Opting out of installing Recommends is 
supported when installing packages, so if admins have concerns about 
extra packages being installed on the slaves (e.g. if using ARMv7 
slaves or simply to reduce the complexity of the install) then 
Recommends can be omitted for the installation of these dependencies,

The 2016.6 release added a dependency on ``python-guestfs``. The 
Recommends for GuestFS can be omitted from the installation, if admins 
desire, but this needs to be done ahead of the upgrade to 2016.6::

 $ sudo apt --no-install-recommends install python-guestfs

.. seealso:: `Debian Policy: What is meant by saying that a package 
   Depends, Recommends, Suggests, Conflicts, Replaces, Breaks or 
   Provides another package? 
   <https://www.debian.org/doc/manuals/debian-faq/ch-pkg_basics.en.html#s-depends>`_ 
   and `details of the lava package in Debian
   <https://packages.debian.org/sid/lava>`_

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

* ``lavapdu-client`` to control a :term:`PDU` to allow LAVA to 
  automatically power cycle a device.

* ``lavapdu-daemon`` - only one daemon is required to run multiple PDUs.

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

.. seealso:: :ref:`dependencies_recommends`

The ``lava`` package installs support for:

* ``lava-dev`` - scripts to build developer packages based on your 
  current git tree of ``lava-server`` or ``lava-dispatcher``, including 
  any local changes.
  
  .. note:: ``lava-dev`` includes **a lot** of packages which are not
     typically used on a production master or worker.

* ``vmdebootstrap`` for building your own Debian based KVM images.

* ``lavapdu-client`` to control a :term:`PDU` to allow LAVA to 
  automatically power cycle a device.

* ``lavapdu-daemon`` is recommended or you can use a single daemon for 
  multiple PDUs.

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
 $ sudo apt -t stretch-backports install lava
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
   ``/etc/lava-dispatcher/lava-slave`` to allow the init script for 
   ``lava-slave`` (``/etc/init.d/lava-slave``) to connect to the 
   relevant ``lava-master`` instead of ``localhost``. Change the port 
   numbers, if required, to match those in use on the ``lava-master``::

     /etc/lava-dispatcher/lava-slave

     # Configuration for lava-slave daemon

     # URL to the master and the logger
     # MASTER_URL="tcp://<lava-master-dns>:5556"
     # LOGGER_URL="tcp://<lava-master-dns>:5555"

     # Enable IPv6 to connect to the master and logger
     # IPV6="--ipv6"

     # Slave hostname
     # Should be set for host that have random hostname (containers, ...)
     # The hostname can be any unique string, except "lava-logs" which is reserved
     # for the lava-logs daemon.
     # HOSTNAME="--hostname <hostname.fqdn>"

     # Logging level should be uppercase (DEBUG, INFO, WARN, ERROR)
     # LOGLEVEL="DEBUG"

     # Encryption
     # If set, will activate encryption using the master public and the slave
     # private keys
     # ENCRYPT="--encrypt"
     # MASTER_CERT="--master-cert /etc/lava-dispatcher/certificates.d/<master.key>"
     # SLAVE_CERT="--slave-cert /etc/lava-dispatcher/certificates.d/<slave.key_secret>"

   .. seealso:: :ref:`zmq_master_encryption` and :ref:`zmq_slave_encryption`

#. Restart ``lava-slave`` once the changes are complete::

    $ sudo service lava-slave restart

#. The administrator of the master will then be able to allocate
   pipeline devices to this slave.

.. note:: For security reasons, the slave does not declare the devices 
   connected to it to the master. The LAVA configuration on the slave 
   actually needs no knowledge of what is connected or where as long as 
   services like ``ser2net`` are configured. All the LAVA configuration 
   data is stored solely in the database of the master. Once this data 
   is entered by the admin of the master, the slave then needs to 
   connect and the admin can then select that slave for the relevant 
   devices. Once selected, the slave can immediately start running 
   pipeline jobs on those devices.

The administrator of the master will require the following information 
about the devices attached to each slave:

#. Confirmation that a suitable template already exists, for each 
   device i.e. :ref:`adding_known_device`

#. A completed and tested :term:`device dictionary` for each device.

This information contains specific information about the local network 
setup of the slave and will be transmitted between the master and the 
slave in **clear text** over :term:`ZMQ`. Any encryption would need to 
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

.. seealso:: :ref:`disable_v1_worker`

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

.. note:: *lava-logs* is a reserved hostname. Any worker connecting with that
          hostname will be rejected by lava-master.

.. seealso:: :ref:`create_device_database`

.. index:: ZMQ authentication, master slave configuration

.. _zmq_curve:

Using ZMQ authentication and encryption
***************************************

``lava-master`` and ``lava-slave`` use ZMQ to pass control messages and 
log messages. When using a slave on the same machine as the master, 
this traffic does not need to be authenticated or encrypted. When the 
slave is remote to the master, it is **strongly** recommended that the 
slave authenticates with the master using ZMQ curve so that all traffic 
can then be encrypted and the master can refuse connections which 
cannot be authenticated against the credentials configured by the 
admin.

To enable authentication and encryption, you will need to restart the 
master and each of the slaves. Once the master is reconfigured, it will 
not be possible for the slaves to communicate with the master until 
each is configured correctly. It is recommended that this is done when 
there are no test jobs running on any of the slaves, so a maintenance 
window may be needed before the work can start. ZMQ is able to cope 
with short interruptions to the connection between master and slave, so 
depending on the particular layout of your instance, the changes can be 
made on each machine before the master is restarted, then the slaves 
can be restarted. Make sure you test this process on a temporary or 
testing instance if you are planning on doing this for a live instance 
without using a maintenance window.

Encryption is particularly important when using remote slaves as the 
control socket (which manages starting and ending testjobs) needs to be 
protected when it is visible across open networks. Authentication 
ensures that only known slaves are able to connect to the master. Once 
authenticated, all communication will be encrypted using the 
certificates.

Protection of the secret keys for the master and each of the slaves is 
the responsibility of the admin. If a slave is compromised, the admin 
can delete the certificate from 
``/etc/lava-dispatcher/certificates.d/`` and restart the master daemon 
to immediately block that slave.

.. index:: encrypt, ZMQ certificates

Create certificates
===================

Encryption is supported by default in ``lava-master`` and 
``lava-slave`` but needs to be enabled in the init scripts for each 
daemon. Start by generating a master certificate on the master::

 $ sudo /usr/share/lava-dispatcher/create_certificate.py master

Now generate a unique slave certificate on each slave. The default name 
for any slave certificate is just ``slave`` but this is only relevant 
for testing. Use a name which relates to the hostname or location or 
other unique aspect of each slave. The admin will need to be able to 
relate each certificate to a specific slave machine::

 $ sudo /usr/share/lava-dispatcher/create_certificate.py foo_slave_1

Distribute public certificates
==============================

Copy the public component of the master certificate to each slave. By 
default, the master public key will be 
``/etc/lava-dispatcher/certificates.d/master.key`` and needs to be 
copied to the same directory on each slave.

Copy the public component of each slave certificate to the master. By 
default, the slave public key will be 
``/etc/lava-dispatcher/certificates.d/slave.key``.

Admins need to maintain the set of slave certificates in 
``/etc/lava-dispatcher/certificates.d`` - only certificates declared by 
active slaves will be used but having obsolete or possibly compromised 
certificates available to the master is a security risk.

.. _preparing_for_zmq_auth:

Preparation
===========

Once enabled, the master will refuse connections from any slave which 
are either not encrypted or lack a certificate in 
``/etc/lava-dispatcher/certificates.d/``. So before restarting the 
master, stop each of the slaves::

 $ sudo service lava-slave stop

.. _zmq_master_encryption:

Enable master encryption
========================

The master will only authenticate the slave certificates if the master 
is configured with the ``--encrypt`` option. Edit 
``/etc/lava-server/lava-master`` to enable encryption::

 # Encryption
 # If set, will activate encryption using the master public and the slave
 # private keys
 ENCRYPT="--encrypt"

Also edit ``/etc/lava-server/lava-logs`` to enable encryption::

 # Encryption
 # If set, will activate encryption using the master public and the slave
 # private keys
 ENCRYPT="--encrypt"

If you have changed the name or location of the master certificate or 
the location of the slave certificates, specify those locations and 
names explicitly, in each file::

 # MASTER_CERT="--master-cert /etc/lava-dispatcher/certificates.d/<master.key_secret>"
 # SLAVES_CERTS="--slaves-certs /etc/lava-dispatcher/certificates.d"

.. note:: Each master needs to find the **secret** key for that master 
   and the **directory** containing all of the  **public** slave keys 
   copied onto that master by the admin.

.. seealso:: :ref:`preparing_for_zmq_auth`

.. _zmq_slave_encryption:

Enable slave encryption
=======================

.. seealso:: :ref:`preparing_for_zmq_auth`

Edit ``/etc/lava-dispatcher/lava-slave`` to enable encryption by adding 
the enabling the ``--encrypt`` argument::

 # Encryption
 # If set, will activate encryption using the master public and the slave
 # private keys
 ENCRYPT="--encrypt"

If you have changed the name or location of the master certificate or 
the location of the slave certificates, specify those locations and 
names in ``/etc/lava-dispatcher/lava-slave`` explicitly::

 # MASTER_CERT="--master-cert /etc/lava-dispatcher/certificates.d/<master.key>"
 # SLAVE_CERT="--slave-cert /etc/lava-dispatcher/certificates.d/<slave.key_secret>"

.. note:: Each slave refers to the **secret** key for that slave and 
   the **public** master key copied onto that slave by the admin.

Restarting master and slaves
============================

For minimal disruption, the master and each slave can be prepared for 
encryption and authentication without restarting any of the daemons. 
Only upon restarting the master will the slaves need to authenticate.

Once all the slaves are configured restart the master and check the 
logs for a message showing that encryption has been enabled on the 
master. e.g.

.. code-block:: none

 2018-02-05 11:33:55,933    INFO [INIT] Marking all workers as offline
 2018-02-05 11:33:55,983    INFO [INIT] Starting encryption
 2018-02-05 11:33:55,984   DEBUG [INIT] Opening master certificate: /etc/lava-dispatcher/certificates.d/master.key_secret
 2018-02-05 11:33:55,985   DEBUG [INIT] Using slaves certificates from: /etc/lava-dispatcher/certificates.d/
 2018-02-05 11:33:55,986    INFO [INIT] LAVA master has started.
 2018-02-05 11:33:55,986    INFO [INIT] Using protocol version 2

Now restart each slave in turn and watch for equivalent messages in the 
logs:

.. code-block:: none

 2018-02-05 11:34:42,035    INFO [INIT] LAVA slave has started.
 2018-02-05 11:34:42,036    INFO [INIT] Using protocol version 2
 2018-02-05 11:34:42,037    INFO [INIT] Starting encryption
 2018-02-05 11:34:42,037   DEBUG Opening slave certificate: /etc/lava-dispatcher/certificates.d/codehelp.key_secret
 2018-02-05 11:34:42,038   DEBUG Opening master certificate: /etc/lava-dispatcher/certificates.d/master.key
 2018-02-05 11:34:42,038    INFO [INIT] Connecting to master as <codehelp>
 2018-02-05 11:34:42,038    INFO [INIT] Greeting the master => 'HELLO'
 2018-02-05 11:34:42,050    INFO [INIT] Connection with master established
 2018-02-05 11:34:42,050    INFO Master is ONLINE
 2018-02-05 11:34:42,053    INFO Waiting for instructions

.. _adding_pipeline_devices_to_worker:

Adding devices to a worker
**************************

Admins use the Django admin interface to add devices to workers using 
the worker drop-down in the device detail page.

.. note:: A worker may have a description but does not have a record of 
   the IP address, uptime or architecture in the Worker object.
