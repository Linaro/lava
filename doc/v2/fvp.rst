.. index:: fvp, fixed virtual platform

FVP
###

The FVP device-type in LAVA refers to running `Fixed Virtual Platforms <https://developer.arm.com/tools-and-software/simulation-models/fixed-virtual-platforms>`_.

LAVA FVP Dispatcher Setup
*************************

LAVA executes FVP devices inside Docker containers.
Therefore, like any other LAVA dispatcher that can run `docker` device types,
Docker needs to be
`installed <https://docs.docker.com/install/linux/docker-ce/debian/>`_.

FVP Binaries
************

LAVA does not handle the download of FVP binaries: these are assumed to be in
the Docker image defined in the LAVA job.

FVP binaries are not available in any public Docker images and must be download
at `developer.arm.com <https://developer.arm.com/tools-and-software/simulation-models/fixed-virtual-platforms>`_.
Therefore, custom Docker images must be created for this purpose. Either these
images should be built on the dispatcher to use a local image, or they can be
pushed to a **private** registry: FVP binaries must not be redistributed.

Building FVP Docker Images
**************************

Once FVP binaries have been obtained from `developer.arm.com <https://developer.arm.com/tools-and-software/simulation-models/fixed-virtual-platforms>`_,
these must be built into a Docker image.

There are few dependencies:
 - FVP Binaries
 - ``telnet`` command. This is used to connect to a UART.

For these basics, here is a sample `Dockerfile <examples/source/fvp/Dockerfile>`_ to create a Docker image for
running FVPs in LAVA, which can be built with a ``docker build`` command.
