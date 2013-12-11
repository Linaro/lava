.. _deploy_boards:

Deploying a board in LAVA
^^^^^^^^^^^^^^^^^^^^^^^^^

When adding a device to LAVA a number of steps are involved. First of all an
image needs to be created and put onto an SD card, then the sd card must be
partitioned in a particular way and various tools installed, along with
configuration of the network where required.

Once the master image has been created a number of files need to be added to
the lava instance so that it is aware of the new board, and finally the
scheduler must be informed of the new device.

Preparing a master image
************************

Builds submitted to LAVA can often be bad and not even bootable. This presents
a problem to LAVA since the dispatcher must always be able to work with target
devices. The solution used in LAVA is called a "master image". The master image
basically puts a known, reliable image onto an SD-card. The lava-dispatcher
can tell u-boot whether to boot to the "master image" or boot into the image
to be tested. This has drawbacks, namely no bootloader testing, but its the
best option available right now.

There are two ways you can obtain a master image. LAVA maintains a set
of `pre-built master images`_ that you can 'dd' to your sd card. The
following commands show how to set up a panda image::

    DEV=/dev/sdX #X should be something like b
    wget http://images.validation.linaro.org:8080/panda-master.img
    sudo dd bs=4M if=panda-master.img of=${DEV}

.. _pre-built master images: http://images.validation.linaro.org:8080/

Alternatively you can create your own master image, if you don't find a
suitable pre-built one. You will need a SD card with at least 4GB.
Creating master images can be done by using the
`lava-master-image-scripts`_ project:

.. _lava-master-image-scripts: http://staging.git.linaro.org/lava/lava-master-image-scripts.git/blob_plain/HEAD:/README

::

    bzr branch lp:lava-master-image-scripts
    cd lava-master-image-scripts
    ./lava-create-master <board>

When the master image is booted by the first time, it *needs* to have
network connectivity, so make sure an ethernet cable is plugged in and
connected to a network with a working DHCP server.

A note about U-boot timeouts
----------------------------

In order to switch between booting the master image and the test image,
LAVA has to be able to stop U-boot from booting automatically, and from
there issue some U-boot commands.

This happens at the well-konwn "Hit any key to stop autoboot" prompt,
and LAVA needs to have enough time to stop U-boot at that point. The
default, 1 second, is often not enough. It is recommended that you set
that timeout to 10 secods.

To do that, boot the board and stop U-boot manually by hitting any key
when you see the "Hit any key to stop autoboot" message, and enter the
following commands:

::

    $ setenv bootdelay 10
    $ saveenv
    $ boot

Adding a device to LAVA
***********************

LAVA needs to know about your particular device. However, before adding the
device to LAVA, you need to work out how you want connect to the device and
provide that command to the dispatcher. There are different ways to
connect to the device which are as follows:

*Method 1:* The easiest way to do this is, if you have a direct serial
connection to the device then you can use "cu". Here's an example
command (the following command assumes "cu" is already installed in
your machine):

::

    sg dialout "cu -l /dev/ttyUSB<X> -s 115200"

In some cases "cu" on Ubuntu has shown issues sending STDIN to the
target. In this case GNU screen is an alternative (the following
command assumes "screen" is already installed in your machine):

::

    sudo screen -t 'ttyUSB0 115200 8n1' /dev/ttyUSB0 115200,-ixoff,-ixon

*Method 2:* The next method to connect to the board is to use ser2net. It
provides a convenient way which allows you to 'telnet' into your board
over a serial link. After connecting your board, let us assume your
board appears as "/dev/ttyUSB0".

::

    sudo apt-get install ser2net

Edit /etc/ser2net.conf and add this line:

::

    2000:telnet:0:/dev/ttyUSB0:115200 8DATABITS NONE 1STOPBIT banner

Then restart so that ser2net sees your changes:

::

    sudo /etc/init.d/ser2net restart

You can now connect to the board with:

::

    telnet localhost 2000

The advantage of connecting with ser2net is that, your device/board is
available from the connected host machine IP to the entire network at
port 2000 or any port that is specified in the config file.

Once you have a good way of connecting to the device, you need to tell LAVA
about it in two places:

Adding to the dispatcher
------------------------
The lava-dispatcher needs to know about a device and how to connect to it.

Let us take as an example adding a pandaboard. You can
name the device anything you want, but it's usually good to indicate what
type of board it is. Let's call ours panda01. First create a file called

::

    /srv/lava/instances/<YOUR_INST>/etc/lava-dispatcher/devices/panda01.conf

In here you should put the following lines:

::

    device_type = panda
    hostname = panda01
    #NOTE: the ttyUSBX below needs to be updated to match your configuration
    connection_command = sg dialout "cu -l /dev/ttyUSBX -s 115200"

The "device_type" field above is critical. The dispatcher allows devices to
inherit from a base device type that includes most of the settings needed for
a given device type. You then only need to give the devices a "hostname".
The list of supported device types can be found here_.

.. _here: http://staging.git.linaro.org/lava/lava-dispatcher.git/tree/HEAD:/lava_dispatcher/default-config/lava-dispatcher/device-types

The critical piece that ties the dispatcher to the connection information
described above is the "connection_command" setting. Based on the
connection method you have chosen above your "connection_command" will vary.

Adding to the scheduler
-----------------------
The LAVA scheduler's web application also needs to know about available device
types and devices associated with them. Go into the admin panel from dashboard.
You'll need to add a device type and then add a device with that device type
selected. The name of the device must match the hostname you used in the
dispatcher configuration above.

Writing device information for a new board
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

:ref:`deploy_bootloader`


