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

Networking inside Models
************************

Optionally, if you require networking in the model, here is a way to enable this.
For this example the base OS is Ubuntu.

- Ensure ``libvirt-bin`` package is installed in the ``Dockerfile``.
- Add the following contents into ``/etc/libvirt/hooks/network``.

.. code-block:: bash

    #!/bin/bash

    # If the change occurs to the "default" libvirt managed network
    if [ "${1}" = "default" ] ; then
      # If the network is started
      if [ "${2}" = "started" ] ; then
        ip tuntap add mode tap tap01
        ip link set tap01 promisc on
        ip link set tap01 up
        brctl addif virbr0 tap01
      fi
    fi

- Create a custom entrypoint script that calls ``/usr/sbin/libvirtd &`` before the commands given: ``exec "$@"``.
- libvirt will create a ``virbr0`` bridge and then a tap interface ``tap01`` connected to it. ``tap01`` is what the model will use.
- Add the following arguments to your foundation model (other models will differ):

.. code-block:: yaml

    arguments:
    - ...
    - "--network=bridged"
    - "--network-bridge=tap01"

This will be required if you require the use of ``transfer_overlay``.
This could be useful in the event you want to pass binaries to the model that
contains the filesystem but stored in a way LAVA cannot currently put the overlay into.

.. code-block:: yaml

  transfer_overlay:
    # It may be required to suppress some kernel messages
    download_command: echo 3 > /proc/sys/kernel/printk ; wget
    unpack_command: tar -C / -xzf

Reading from all model consoles
*******************************

Sometimes models offer more than one console that produces useful output. LAVA can only write to one console at a time.
Reading can be done from multiple consoles. In some cases it's essential to read from all consoles to prevent
model from hanging. This happens when internal model buffer is not able to accept more output because previously
generated output is not consumed. FVP boot method allows to define additional regexes to match more than one console.
This is done with ``feedbacks`` keyword:

.. code-block:: yaml

    console_string: 'terminal_0: Listening for serial connection on port (?P<PORT>\d+)'
    feedbacks:
      - '(?P<NAME>terminal_1): Listening for serial connection on port (?P<PORT>\d+)'
      - '(?P<NAME>terminal_2): Listening for serial connection on port (?P<PORT>\d+)'
      - '(?P<NAME>terminal_3): Listening for serial connection on port (?P<PORT>\d+)'

Feedbacks will be read twice during boot process (before matching login prompt) and periodically during test-shell.
