.. _setting_up_pipeline_instance:

Setting up a LAVA pipeline instance
###################################

.. _pipeline_install_considerations:

Initial considerations
======================

#. The default setup of the LAVA packages and codebase is for the current
   dispatcher and the V1 distributed deployment but this will change towards
   the end of 2016 before the old code is removed. Until then, installations
   will continue to provide both models.
#. A LAVA pipeline instance can have existing remote worker support
   alongside but uses a completely different mechanism to identify
   remote workers and run jobs on pipeline devices.
#. If both systems are enabled, devices can support both pipeline and
   current JSON submissions. It is not yet possible to disable JSON
   submissions. If there is no relevant configuration for a device
   other than pipeline support, a JSON submission would be accepted
   but would stay in Submitted state until cancelled. See
   :ref:`changing_existing_workers`.
#. The default setup provides both mechanisms, the only step required
   to allow pipeline submissions to devices connected to ``http://localhost``
   is to have pipeline devices available.
#. Distributed deployments need changes on each worker, see
   :ref:`changing_existing_workers` but this can be avoided if all
   devices on the instance are suitable for the pipeline.
#. Pipeline setup is a much simplified task for admins but still contains
   some manual steps. See :ref:`installing_pipeline_worker`.
#. If only pipeline devices are to be supported, the dispatchers
   running ``lava-slave`` do **not** need to have the ``lava-server``
   package installed. Each dispatcher does need to be able to connect
   to the ZMQ port specified in the ``lava-master`` configuration of the
   instance (which is then the only machine related to that instance which
   has ``lava-server`` installed). The ``lava-server`` package on the
   master should be installed as a single master instance of LAVA.
#. The :term:`ZMQ` protocol incorporates buffering at each end such that
   either the ``lava-master`` or the ``lava-slave`` service can be restarted
   at any time without affecting currently running jobs or requiring any
   changes or restarts at the other end of the connection. There are no
   other connections required between the slave and the master and the
   outgoing request from the slave is initiated by the slave, so it is
   possible for the slave to be behind a local firewall, as long as
   the relevant ports are open for outgoing traffic. i.e. the slave pulls
   from the master, the master cannot push to the slave. (This does then mean
   that a :term:`hacking session` would be restricted to those with access
   through such a firewall.)

.. _installing_pipeline_worker:

Detailed changes
================

The pipeline design designates the machine running Django and PostgreSQL
as the ``lava-master`` and all other machines connected to that master
which will actually be running the jobs are termed ``lava-slave``
machines.

If this slave has no devices which will be used by the current
dispatcher, only by the pipeline, i.e. :term:`exclusive` devices,
only ``lava-dispatcher`` needs to be installed, not ``lava-server``::

 $ sudo apt install lava-dispatcher

#. Change the init script for ``lava-slave`` (``/etc/init.d/lava-slave``)
   to point at the relevant ``lava-master`` instead of ``localhost``::

     MASTER="--master tcp://localhost:5556"
     LOG_SOCKET="--socket-addr tcp://localhost:5555"

#. Change the port numbers, if required, to match those in use on the
   ``lava-master``.
#. Restart ``lava-slave`` once the changes are complete::

    $ sudo service lava-slave restart

#. The administrator of the master will then be able to allocate
   pipeline devices to this slave.

.. note:: For security reasons, the slave does not declare the devices
   connected to it to the master. The LAVA configuration on the slave
   actually needs no knowledge of what is connected or where as long as
   services like ``ser2net`` are configured. All the LAVA configuration
   data is stored solely in the database of the master. Once this data
   is entered by the admin of the master, the slave then needs to connect
   and the admin can then select that slave for the relevant devices. Once
   selected, the slave can immediately start running pipeline jobs on those
   devices.

The administrator of the master will require the following information
about the devices attached to each slave:

#. Confirmation that a suitable template already exists, for each device
   i.e. :ref:`adding_known_device`
#. A completed and tested :term:`device dictionary` for each device.

This information contains specific information about the local network
setup of the slave and will be transmitted between the master and the
slave in **clear text** over :term:`ZMQ`. Any encryption would need to
be arranged separately between the slave and the master. Information
typically involves the hostname of the PDU, the port number of the
device on that PDU and the port number of the serial connection for that
device. The slave is responsible for ensuring that these ports are only
visible to that slave. There is no need for any connections to be visible
to the master.

.. _adding_pipeline_workers:

Adding pipeline workers to the master
=====================================

A worker which only has :term:`exclusive` pipeline devices attached can be installed as a
:ref:`pipeline worker <installing_pipeline_worker>`. These workers need to be manually
added to the master so that the admins of the master have the ability to assign devices
in the database and enable or disable the worker.

To add a new pipeline worker::

 $ sudo lava-server manage pipeline-worker --hostname <HOSTNAME>

To add a pipeline worker with a description::

 $ sudo lava-server manage pipeline-worker --hostname <HOSTNAME> --description <DESC>

To add a pipeline worker in a disabled state::

 $ sudo lava-server manage pipeline-worker --hostname <HOSTNAME> --disable

Pipeline workers are enabled or disabled in the Django admin interface by changing the
``display`` field of the worker. Jobs submitted to devices on that worker will fail, so
it is also recommended that the devices would be made offline at the same time. (The django
admin interface has support for selecting devices by worker and taking all selected devices
offline in a single action.)

Adding pipeline devices to a worker
===================================

Admins use the Django admin interface to add devices to workers using the worker drop-down in the
device detail page.

It is up to the admin to ensure that pipeline devices are assigned to pipeline workers and
devices which can run JSON jobs are assigned only to distributed deployment workers.

.. note:: A pipeline worker may have a description but does not have a record of the IP
   address, uptime or architecture in the Worker object.

.. _changing_existing_workers:

Changes for existing remote workers
===================================

On an existing remote worker, a ``lava-master`` daemon will already be
running on localhost (doing nothing). Once the migration to the
:term:`pipeline` is complete, the ``lava-server`` package can be removed
from all workers, so the above information relates to this endpoint. In
the meantime, remote workers should have ``lava-master`` disabled on
localhost once the slave has been directed at the real master as above.

Disabling lava-master on workers
--------------------------------

.. note:: A pipeline worker will only have ``lava-dispatcher`` installed, so there will be
   no ``lava-master`` daemon which is installed by ``lava-server``.

.. warning:: Only do this on the remote worker but make sure it is done
   on **all** remote workers before submitting pipeline jobs which would
   need the devices on those workers.

If a **new** worker does not **need** to run jobs using the current dispatcher,
i.e. if all devices on this worker are :term:`exclusive`, then
``lava-server`` does not need to be installed and there is no ``lava-master``
daemon to disable.

For existing workers, pipeline jobs will be likely be mixed with JSON
jobs. This leads to ``lava-server`` being installed on the workers (solely
to manage the JSON jobs). On such workers, ``lava-master`` should be
**disabled** once ``lava-slave`` has been reconfigured::

 $ sudo invoke-rc.d lava-master stop
 $ sudo update-rc.d lava-master remove
 $ sudo chmod a -x /etc/init.d/lava-master
 $ sudo service lava-master status
 lava-master: unrecognized service

Removing the executable bits stops the lava-master being re-enabled when
the packages are updated.
