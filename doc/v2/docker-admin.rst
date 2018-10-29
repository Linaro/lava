.. index:: docker - admin

.. _docker_admin:

Administering LAVA using Docker
###############################

.. _docker_prerequisites:

Prerequisites
*************

#. For buster or later, use docker.io from Debian
   https://tracker.debian.org/pkg/docker.io

#. For stretch, use docker-ce from Docker.
   https://docs.docker.com/install/linux/docker-ce/debian/

#. add yourself to the docker group to avoid the need for ``sudo``.

#. Ensure that your docker installation has created a suitable
   network bridge (often called ``docker0``).

#. Not all docker images are available for all architectures. LAVA
   has support for amd64 and arm64 docker images.

   .. seealso:: :ref:`docker_networking`


https://docs.docker.com/engine/reference/commandline/run/

.. index:: docker - network configuration

.. _docker_networking:

Docker Networking
=================

https://docs.docker.com/engine/reference/commandline/network_create/

LAVA typically uses network connections not just for the communication
between master and worker but also to control the :term:`DUT`. It is
important to have reliable networking for the docker components.

If you have not done so already, create a new network for docker to
use, based on the ``docker0`` bridge which should already have been
created by docker. The subnet you choose is up to you.

.. code-block:: none

 $ docker network create --subnet=172.18.0.0/16 dockernet
 f9ca89ac46ab97e5d905a0858a03f8983941e8f4583b71e1996bbaa0d57d3138

When you start containers, you can specify that network name and then
provide a static IPv4 address for the container. This is particularly
important if you want to start a ``lava-server`` container and then
connect a worker. The worker can be another docker container or it can
use ``lava-dispatcher`` installed directly on this or another system.
You will need to make sure that the docker network is accessible to any
worker you want to attach to the new container. Depending on local
configuration, you may also need to configure the ZMQ ports on your
``lava-server`` container. See the docker documentation for how to
forward ports to different numbers outside the container.

.. code-block:: none

 $ docker run --net dockernet --ip 172.18.0.5 -it hub.lavasoftware.org/lava/lava/lava-dispatcher:2018.10

This IP address (or a hostname if you configure local DNS
appropriately) can then be used in commands to docker run to start a
``lava-dispatcher`` container by updating the MASTER_URL and LOGGER_URL
variables.

.. code-block:: none

    ...
    -e "LOGGER_URL=tcp://172.18.0.5:5555" \
    -e "MASTER_URL=tcp://172.18.0.5:5556" \
    ...

Official LAVA Software Docker images
####################################

Official LAVA Software Docker images are available via
``hub.lavasoftware.org`` and ``hub.docker.com``. In each case, two
images are built at the same version: ``lava-dispatcher`` and
``lava-server``.

Daily builds
*************

``hub.lavasoftware.org`` hosts CI images regularly built from the
``master`` branch of ``lava``. Images are listed in GitLab:

https://git.lavasoftware.org/lava/lava/container_registry

.. _official_docker_releases:

Official LAVA Releases using Docker
***********************************

The ``lavasoftware`` organisation on ``hub.docker.com`` hosts releases
of LAVA. https://hub.docker.com/u/lavasoftware/

lava-dispatcher
===============

https://hub.docker.com/r/lavasoftware/lava-dispatcher/

.. code-block:: none

 docker pull lavasoftware/lava-dispatcher:2018.10

or

.. code-block:: none

 docker pull hub.lavasoftware.org/lava/lava/lava-dispatcher:2018.10

lava-server
===========

https://hub.docker.com/r/lavasoftware/lava-server/

.. code-block:: none

 docker pull lavasoftware/lava-server:2018.10

or

.. code-block:: none

 docker pull hub.lavasoftware.org/lava/lava/lava-server:2018.10

Command lines
*************

Command lines get long, so use wrapper scripts, e.g.:

.. code-block:: none

 #!/bin/sh
 set -e
 set -x

 docker run \
 -e "DISPATCHER_HOSTNAME=--hostname=calvin-2018.7-88" \
 -e "LOGGER_URL=tcp://calvin:5555" \
 -e "MASTER_URL=tcp://calvin:5556" \
 --name calvin-docker-88-3 \
 hub.lavasoftware.org/lava/lava/lava-dispatcher/master:2018.7-88-ga7b7939dd

Supporting encryption
*********************

Always use encryption to any master outside your local network. Create
a docker volume to act as a fileshare, mounting the specified directory
from the host machine inside the docker container at the specified
location to exchange files from the host to the container and vice
versa:

.. code-block:: none

 -v $PWD/my-certificates.d:/etc/lava-dispatcher/certificates.d/

Then use these certificates in the commands:

.. code-block:: none

 -e ENCRYPT="--encrypt" \
 -e MASTER_CERT='/etc/lava-dispatcher/certificates.d/master.key' \
 -e SLAVE_CERT='/etc/lava-dispatcher/certificates.d/docker-slave-1.key_secret'

.. seealso:: `lava-dispatcher docker images - part 2
   <https://www.stylesen.org/lavadispatcher_docker_images_part_2>`_
   - note that the options changed since this content was written.

.. _modifying_docker_dispatcher:

lava-dispatcher in docker
*************************

The official LAVA Software docker images for ``lava-dispatcher`` do not
include details like ``ser2net`` configuration or ``pduclient`` or
other remote power control scripts. These will need to be added
according to your local lab configuration. Depending on the size of
your lab, you may choose to use a docker volume or ``docker build`` to
create one or more customised docker images based on the official
images.

.. seealso:: `Docker documentation on volumes
   <https://docs.docker.com/storage/volumes/>`_ and `Docker
   documentation on building
   <https://docs.docker.com/engine/reference/commandline/build/>`_
   images.

.. _docker_master:

lava-server in docker
*********************

The official LAVA Software docker images for ``lava-server`` currently
include PostgreSQL. Work is planned to use an external PostgreSQL.

.. seealso:: :ref:`docker_superusers`

LAVA Coordinator
****************

``lava-coordinator`` is neither installed nor configured in any
official LAVA Software docker image.  Therefore, a worker running from
one of these images will not have the configuration file
``/etc/lava-coordinator/lava-coordinator.conf`` to use
``lava-coordinator``, so cannot run :ref:`multinode` test jobs. The
configuration file would need to be provided (configured for an
external coordinator installed using packages), either using a docker
volume used as a fileshare or by a modification to the docker image for
lava-dispatcher.

Work is planned to refactor ``lava-coordinator`` to not require
external configuration or packaging.

CI images
*********

``lava/lava/lava-dispatcher/master`` on ``hub.lavasoftware.org``
contains images like 2018.7-101-g5987db8b5

.. seealso:: :ref:`official_docker_releases`

lava-dispatcher
***************

This example runs a new worker for an existing master which can be:

* on the same machine but installed from packages, not docker
* on a different machine and accessible through DNS

In either case, the machine running ``lava-server`` is accessible on
the network as ``calvin``. (Replace this hostname with your local
machine hostname.)

To run both master and worker on a single machine, both using docker,
see :ref:`two_dockers_together`.

.. code-block:: none

    DISPATCHER_HOSTNAME=--hostname=calvin-2018.7-88

    /usr/bin/lava-slave --level $LOGLEVEL --log-file $LOGFILE --master $MASTER_URL --socket-addr $LOGGER_URL $IPV6 $ENCRYPT $MASTER_CERT $SLAVE_CERT $DISPATCHER_HOSTNAME

    $ docker run -e "DISPATCHER_HOSTNAME=--hostname=calvin-2018.7-88" -e "LOGGER_URL=tcp://calvin:5555" -e "MASTER_URL=tcp://calvin:5556"  --name calvin-docker-88-4  hub.lavasoftware.org/lava/lava/lava-dispatcher/master:2018.7-88-ga7b7939dd
    2018-10-03 15:08:32,852    INFO [INIT] LAVA slave has started.
    2018-10-03 15:08:32,852    INFO [INIT] Using protocol version 3
    2018-10-03 15:08:32,853   DEBUG [INIT] Connection is not encrypted
    2018-10-03 15:08:32,965    INFO [BTSP] Connecting to master [tcp://calvin:5556] as <calvin-2018.7-88>
    2018-10-03 15:08:32,965    INFO [BTSP] Greeting the master [tcp://calvin:5556] => 'HELLO'
    2018-10-03 15:08:32,966    INFO [BTSP] Connection with master [tcp://calvin:5556] established
    2018-10-03 15:08:32,966    INFO Master is ONLINE
    2018-10-03 15:08:37,971   DEBUG PING => master (last message 5s ago)
    2018-10-03 15:08:37,973   DEBUG master => PONG(20)

If you make mistakes, set the worker to Retired in the Django admin
interface and use ``docker rm <name>`` to allow you to re-use the same
container with different arguments next time.

lava-server
***********

.. code-block:: none

 $ docker run --net dockernet --ip 172.18.0.5 -it hub.lavasoftware.org/lava/lava/lava-server/master:2018.7-88-ga7b7939dd

.. note:: the ``dockernet`` docker network needs to already exist and
   is just an example name - choose your own name according to your own
   preferences. See https://docs.docker.com/network/bridge/#differences-between-user-defined-bridges-and-the-default-bridge

.. seealso:: :ref:`docker_networking`

.. _docker_superusers:

Superusers
==========

There is no superuser in the `lava-server` docker container, admins
need to login to the container and create an initial superuser:

.. code-block:: none

 $ docker exec -it a936cc14b913 lava-server manage users add --staff --superuser --email <EMAIL> --passwd <PASSWORD> <USERNAME>

Then this user can :ref:`login through the normal UI <logging_in>` and
create :ref:`authentication_tokens`.

.. seealso:: :ref:`modifying_docker_dispatcher` and :ref:`using
   lava-server from docker <docker_master>`

.. _two_dockers_together:

Running lava-server & lava-dispatcher together
**********************************************

The worker **must** be on the same **docker network** as the master
because docker only exposes the master ports to that network.

 Containers connected to the same user-defined bridge network
 automatically expose all ports to each other, and no ports to the
 outside world. This allows containerized applications to communicate
 with each other easily, without accidentally opening access to the
 outside world.

So to run a worker in docker to work with a master in docker on the
same machine, the worker must be given the ``--net dockernet`` option.

Depending on the tasks, you should also assign an IP address to the
worker, on the same docker network.

.. code-block:: none

 $ docker run --net dockernet --ip 172.18.0.6 ....

(This is why docker start up scripts are going to be so useful.)

.. seealso:: :ref:`docker_networking`
