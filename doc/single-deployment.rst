.. _single_deployment:

Deploying Single LAVA Instances
*******************************

This section will lead you through installing a single LAVA server and
dispatcher instance on a single computer. If you wish to deploy a
distributed instance with a LAVA server and multiple worker nodes, you
should read :ref:`distributed_deployment`.


Assumptions
===========

The device(s) you wish to deploy in LAVA are either:
   * Physically connected to the server via usb, usb-serial, or serial
     [#f1]_
   * Connected over the network via a serial console server [#f1]_
   * A fastboot capable device accessible from the server
   * Emulated virtual machines and/or simulators that allow a serial connection

A small LAVA instance can be deployed on reasonably modest hardware.[#f2]_ We
recommend:
   * At least one 1GB of RAM for runtime activity (this is shared, on a single host, among the database server, the application server and the web server)
   * At least 20GB for application data


.. [#f1] See the section :ref:`serial_connections` for details of
         configuring serial connections to devices

.. [#f2] If you are deploying many devices and expect to be running large
         numbers of jobs, you will obviously need more RAM and disk space

.. _serial_connections:

Setting Up Serial Connections to LAVA Devices
=============================================

