
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

A SD/MMC card containing a 'master image'

Configuring cu and conmux
^^^^^^^^^^^^^^^^^^^^^^^^^

Configuring conmux
------------------

You will need to have a card containing a 'master image' for your
board.  The process of creating a master image is outlined on
https://wiki.linaro.org/Platform/Validation/Specs/MasterBootImage.

For LAVA development and testing using only locally attached resources,
you should be able to make use of most features, even without the use of
special equipment such as a console server.

First install conmux and cu::

    sudo add-apt-repository ppa:linaro-maintainers/tools
    sudo apt-get update
    sudo apt-get install conmux cu

Connect a development board to a local serial device (e.g. ttyUSB0).
You may have permission problem with cu running as root under conmux.

Create a configuration file for your board under /etc/conmux which
should look something like this::

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

Installation Options
^^^^^^^^^^^^^^^^^^^^

There are several installation options available:


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


Using Python Package Index
--------------------------

This package is being actively maintained and published in the `Python Package
Index <http://http://pypi.python.org>`_. You can install it if you have `pip
<http://pip.openplans.org/>`_ tool using just one line::

    pip install lava-dispatcher


Using source tarball
--------------------

To install from source you must first obtain a source tarball from either pypi
or from `Launchpad <http://launchpad.net/>`_. To install the package unpack the
tarball and run::

    python setup.py install

You can pass ``--user`` if you prefer to do a local (non system-wide)
installation. Note that executable programs are placed in ``~/.local/bin/`` and
this directory is not on ``PATH`` by default.

Creating a SD/MMC card with master image
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

