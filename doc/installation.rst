.. _installation:

Installation
============

Prerequisites
^^^^^^^^^^^^^

The following debian packages are needed to use LAVA Dispatcher:

* cu - for serial port control
* conmux - for console management
* python >= 2.6
* python-testrepository - for running unit tests
* python-sphinx - for building documentation

The following python module are needed to use LAVA Dispatcher:

* pexpect

A SD/MMC card containing a 'master image'.

Creating a SD/MMC card with master image
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

You will need to have a card containing a 'master image' for your board.  The
process of creating a master image is outlined on
https://wiki.linaro.org/Platform/Validation/Specs/MasterBootImage.

The master image is a stable, default image the system can boot into for
deployment and recovery. It's a simple modification of an existing stable
image, and does not take long to create. Once you've created one for your
board, you may want to consider making a dd image of it for future use. We do
not provide dd images for this already. Due to differences in size of SD cards,
it's likely that doing so would either waste a lot of space if you have a
larger card, or be competely useless if you have a smaller sd card. 

Setup the image and test partitions
-----------------------------------

* Start with a stable Linaro image from the current, or previous cycle. For
  instance, the nano, or headless images make a good starting place. Using
  linaro-media-create, create an sdcard with this image, and the hardware pack
  for your board. (minimum 8GB sd card is recommended, but 4GB can work also).
* Using parted (or gparted, etc), shrink the root partition so that only
  1-1.5GB or so is used (Make sure to leave at least 2G free on the card).
* Create an additional primary partition (should normally be partition 3), of
  about 70MB. Format it as vfat and give it the label testboot.
* Create partition 4 as an Extended partition, using the remainder of the space
  on the card.
* Create partition 5 (logical partition) using 2GB. Format it as ext3, and give
  it the label testrootfs 
* Finally, create one more logical partition using the remainder of the space.
  It should be vfat formatted, and have the label sdcard (NB: This is only
  needed if you want to test android images. If you don't wish to test android,
  this can be skipped) 

Prepare the master image
------------------------

* Boot the image created above on your test board, and attach to the serial
  console
* Ensure that networking is set up so that the default network interface is
  automatically started. Generally you will want to use dhcp for this. For
  example, if your network interface is eth0, make sure that
  /etc/network/interfaces contains something like this::

    auto usb0
    iface usb0 inet dhcp

* Edit /etc/hostname and /etc/hosts to change the hostname to "master". This
  will allow easy detection of which image we are booted into.
* Install the following packages:
    * wget
    * dosfstools
* If you want to test your own build kernel by a deb package(see following
  example  job file for detail), you need to add linaro-media-tools support in
  master image::

    # apt-get install bzr python-distutils-extra python-testtools python-parted command-not-found python-yaml python-beautifulsoup python-wxgtk2.6
    # bzr branch lp:linaro-media-tools
    # cd linaro-media-tools
    # ./setup.py install

Setting up serial access
^^^^^^^^^^^^^^^^^^^^^^^^

To talk to the target test systems, the dispatcher uses a tool called conmux.
If you are running Ubuntu 11.04 or later, conmux is in the archives and can be
easily installed [TODO: point to ppa for conmux installation -lt 11.04].

Configuring cu and conmux
-------------------------

For LAVA development and testing using only locally attached resources, you
should be able to make use of most features, even without the use of special
equipment such as a console server.

First install conmux and cu::

    sudo add-apt-repository ppa:linaro-maintainers/tools
    sudo apt-get update
    sudo apt-get install conmux cu

Configuring cu
--------------

You should be able to type commands and interact with the shell inside
conmux-console.  If you cannot, run "sudo stop conmux" and try running
'sg dialout "cu -l ttyUSB0 -s 115200"'.  If that doesn't work, you
probably need to add some files to /etc/uucp.  Add ::

    port ttyUSB0
    type direct
    device /dev/ttyUSB0
    hardflow false
    speed 115200

to /etc/uucp/port and append ::

    system  panda01
    port    ttyUSB0
    time    any

to /etc/uucp/sys.

Configuring conmux
------------------

Connect a development board to a local serial device (e.g. ttyUSB0). You may
have permission problem with cu running as root under conmux.

Configuration files for conmux are stored under /etc/conmux. It can be
configured for either local connections (via serial or usb), or remote
configurations such as console servers. Configurations for each board you wish
to connect to should be stored in it's own .cf file under /etc/conmux. 

Create a configuration file for your board under /etc/conmux which should look
something like this::

    listener panda01
    application console 'panda01 console' 'cu -l /dev/ttyUSB0 -s 115200'

Make sure to give the file a '.cf' extension (e.g. panda01.cf).

If you see this permission problem when running cu, you can try
adjusting your .cf file to call cu using sg, and the group name owning
the device.  For example::

    sg dialout "cu -l ttyUSB0 -s 115200"

Finally restart conmux::

    sudo stop conmux
    sudo start conmux

You can test the connection using::

    conmux-console panda01
    (use ~$quit to exit)

Another example config, a remote console server on 10.1.1.1 port 7777 attached
to a board we will call beagle01::

    listener beagle01 
    socket console 'beagle01 console' '10.1.1.1:7777'

.. seealso::

    If you are using a snowball with serial USB, then you'll need to follow
    `this guide <https://wiki.linaro.org/Platform/Validation/LAVA/Documentation/GettingSnowballWorking>`_

Installation Options
^^^^^^^^^^^^^^^^^^^^

There are several installation options available:

Using pip
---------

To install from pip::

    pip install lava-dispatcher

To upgrade from pip::

    pip install --upgrade lava-dispatcher

Using lava-deployment-tool
--------------------------

To install from lava-deployment-tool, first checkout lava-deployment-tool::

    bzr branch lp:lava-deployment-tool

Refer to README in lava-deployment-tool, make sure in "./lava-deployment-tool
bundle" commands, requirements.txt includes lava-dispatcher.

lava-dispatcher can be found in /srv/lava/instances/$LAVA_INSTANCE/bin.

To use lava-dispatcher, activate virtualenv::

    cd /srv/lava/instances/$LAVA_INSTANCE
    . bin/activate

Using source tarball
--------------------

To install from source you must first obtain a source tarball from bazzar
branch or from `Launchpad <https://launchpad.net/lava-dispatcher/+download>`_::

    bzr branch lp:lava-dispatcher

To install the package unpack the tarball and run::

    sudo python setup.py install


Using Ubuntu PPAs
-----------------

For Ubuntu 10.04 onward there is a stable PPA (personal package archive):

* ppa:linaro-validation/ppa

To add a ppa to an Ubuntu system use the add-apt-repository command::

    sudo add-apt-repository ppa:linaro-validation/ppa

After you add the PPA you need to update your package cache::

    sudo apt-get update

Finally you can install the package, it is called `lava-dispatcher`::

    sudo apt-get install lava-dispatcher
