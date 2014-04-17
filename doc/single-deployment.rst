.. _single_deployment:

Deploying Single LAVA Instances
*******************************

This section will lead you through installing a single LAVA server and
dispatcher instance on a single computer. If you wish to deploy a
distributed instance with a LAVA server and multiple worker nodes, you
should read :ref:`distributed_deployment`.

Assumptions
###########

The device you wish to deploy in LAVA is:
 * Physically connected to the server via usb, usb-serial, 
   or serial [#f1]_ or
 * connected over the network via a serial console server [#f1]_ or
 * a fastboot capable device accessible from the server or
 * an emulated virtual machines and/or simulators that allow a
   serial connection

A small LAVA instance can be deployed on reasonably modest hardware. [#f2]_
We recommend:

 * At least 1GB of RAM for runtime activity (this is shared, on a single
   host, among the database server, the application server and the web server)
 * At least 20GB of storage for application data, job log files etc. in
   addition to the space taken up by the operating system.

.. rubric:: Footnotes

.. [#f1] See the section :ref:`serial_connections` for details of
         configuring serial connections to devices
.. [#f2] If you are deploying many devices and expect to be running large
         numbers of jobs, you will obviously need more RAM and disk space

.. _serial_connections:

Setting Up Serial Connections to LAVA Devices
#############################################

.. _ser2net:

Ser2net daemon
==============

ser2net provides a way for a user to connect from a network connection to a serial port, usually over telnet.

http://ser2net.sourceforge.net/

Example config (in /etc/ser2net.conf)::

 #port:connectiontype:idle_timeout:serial_device:baudrate databit parity stopbit
 7001:telnet:36000:/dev/serial_port1:115200 8DATABITS NONE 1STOPBIT

StarTech rackmount usb
======================

W.I.P

* udev rules::

   SUBSYSTEM=="tty", ATTRS{idVendor}=="0403", ATTRS{idProduct}=="6001", ATTRS{serial}=="ST167570", SYMLINK+="rack-usb02"
   SUBSYSTEM=="tty", ATTRS{idVendor}=="0403", ATTRS{idProduct}=="6001", ATTRS{serial}=="ST167569", SYMLINK+="rack-usb01"
   SUBSYSTEM=="tty", ATTRS{idVendor}=="0403", ATTRS{idProduct}=="6001", ATTRS{serial}=="ST167572", SYMLINK+="rack-usb04"
   SUBSYSTEM=="tty", ATTRS{idVendor}=="0403", ATTRS{idProduct}=="6001", ATTRS{serial}=="ST167571", SYMLINK+="rack-usb03"

This will create a symlink in /dev called rack-usb01 etc. which can then be addressed in the :ref:`ser2net` config file.
