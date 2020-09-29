.. index:: docker - admin

.. _docker_admin:

Administering LAVA using Docker
###############################

.. _docker_prerequisites:

Prerequisites
*************

#. For buster or later, use docker.io from Debian
   https://tracker.debian.org/pkg/docker.io

#. add yourself to the docker group to avoid the need for ``sudo``.

#. Ensure that your docker installation has created a suitable
   network bridge (often called ``docker0``).

   .. seealso:: :ref:`docker_networking`

#. Not all docker images are available for all architectures. LAVA
   has support for amd64 and arm64 docker images.

Using LAVA with Docker is also a regular topic of discussion on the
:ref:`lava_devel` mailing list.

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
worker you want to attach to the new container.

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

.. _lava_docker_images:

Official LAVA Software Docker images
####################################

Official LAVA Software Docker images are available via
``hub.lavasoftware.org`` and ``hub.docker.com``. In each case, two
images are built at the same version: ``lava-dispatcher`` and
``lava-server``, each image is built for two architectures, ``amd64``
and ``aarch64``.

Daily builds
*************

``hub.lavasoftware.org`` hosts CI images regularly built from the
``master`` branch of ``lava``. Images are listed in GitLab:

https://git.lavasoftware.org/lava/lava/container_registry

.. _official_docker_releases:

Official LAVA Releases using Docker
***********************************

The ``lavasoftware`` organization on ``hub.docker.com`` hosts releases
of LAVA (https://hub.docker.com/u/lavasoftware/) by retagging images
from hub.lavasoftware.org and pushing to hub.docker.com . Users are
free to use either hub.

.. note:: Due to naming conventions on hub.docker.com, the architecture
   is included in the image name ``amd64-lava-server`` when tagged for
   hub.docker.com.

lava-dispatcher
===============

https://hub.docker.com/r/lavasoftware/lava-dispatcher

.. code-block:: none

 docker pull lavasoftware/lava-dispatcher:2019.01

or

.. code-block:: none

 docker pull hub.lavasoftware.org/lava/lava/lava-dispatcher:2019.01

lava-server
===========

https://hub.docker.com/r/lavasoftware/lava-server/

.. code-block:: none

 docker pull lavasoftware/lava-server:2019.01

or

.. code-block:: none

 docker pull hub.lavasoftware.org/lava/lava/lava-server:2019.01

Command lines
*************

The use of docker with LAVA is an active area of development, including
how to configure containers for a variety of situations and how to
manage a LAVA lab where docker is in use. If you are doing work in
this area, please subscribe to the :ref:`lava_devel` mailing list and
ask for advice on how to use LAVA and docker for your use case.

POSIX shell
===========

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

Python
======

If you are using docker for more than a few test containers, you will
probably find the Python docker SDK library very useful.

* Debian ``apt install python3-docker``
  https://packages.debian.org/unstable/python3-docker - If you install
  the full ``lava`` set on Debian Buster or newer, ``python3-docker``
  and ``docker.io`` will be installed by the ``lava`` metapackage.

* GitHub https://github.com/docker/docker-py

* Documentation: https://docker-py.readthedocs.io/en/stable/

The Python Docker SDK lets you do anything the docker command does,
but from within Python apps – run containers, manage containers, manage
Swarms, etc.

.. code-block:: python

  import docker
  client = docker.from_env()
  container_id = client.containers.run("debian", detach=True)

.. _modifying_docker_dispatcher:

lava-dispatcher in docker
*************************

The official LAVA Software docker images for ``lava-dispatcher`` do not
include details like ``ser2net`` configuration or ``pdudaemon`` or
other remote power control scripts. These will need to be added
according to your local lab configuration. Depending on the size of
your lab, you may choose to use a docker volume or ``docker build`` to
create one or more customized docker images based on the official
images.

.. seealso:: `Docker documentation on volumes
   <https://docs.docker.com/storage/volumes/>`_ and `Docker
   documentation on building
   <https://docs.docker.com/engine/reference/commandline/build/>`_
   images.

.. index:: lava_lxc_mocker

.. _lava_lxc_mocker:

Mocking up LXC inside docker
============================

LXC cannot be installed/used inside a Docker container and the Docker
container can replace the need for the LXC. This has the useful
advantages that specialized tools which need to be isolated inside an
LXC can be pre-installed in a docker container instead of needing to be
installed or compiled within the LXC.

However, there are also disadvantages:

*  **The Docker is persistent** - currently, ``lava-worker`` and
   ``lava-run`` need to be inside the container, so the next test job
   for that worker picks up the changes to the docker from this test
   job.

* The test job would need modification to not call LXC.

Work is underway to solve the persistence problem. In the meantime, it
is possible to run test jobs using Docker if the persistence is handled
correctly but this is usually only practical for single-user developer
instances.

``lava-lxc-mocker`` exists to solve the second problem. By mocking up
the calls to ``lxc-*`` utilities, ``lava-lxc-mocker`` allows the same
test job to be run on a device managed by a ``lava-worker`` in Docker
as on a device managed by a ``lava-worker`` running on bare metal.

``lava-lxc-mocker`` is pre-installed in all :ref:`lava_docker_images`.

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

    DISPATCHER_HOSTNAME=--name=calvin-2018.7-88

    /usr/bin/lava-worker --level $LOGLEVEL --log-file $LOGFILE --url $SERVER_URL $DISPATCHER_HOSTNAME

    $ docker run -e "DISPATCHER_HOSTNAME=--name=calvin-2018.7-88" -e "URL=http://calvin/" --name calvin-docker-88-4  hub.lavasoftware.org/lava/lava/lava-dispatcher/master:2018.7-88-ga7b7939dd
    2018-10-03 15:08:32,852    INFO [INIT] LAVA worker has started.
    2018-10-03 15:08:32,852    INFO [INIT] Using protocol version 3

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

.. _docker_microservices:

Separate services in separate Docker containers
***********************************************

Work is beginning to extend the :ref:`Docker support <docker_admin>` to
have different parts of LAVA in different containers. Some parts of
this are easier to implement than others, so the support will arrive in
stages.

.. seealso:: :ref:`configuring_ui`
