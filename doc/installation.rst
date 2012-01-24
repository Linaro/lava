Installation
^^^^^^^^^^^^

To install LAVA Dashboard, you will first need to install LAVA Server.
For more information about LAVA Server, see
http://lava-server.readthedocs.org

Installation from PPA
*********************

This method is only suitable for users running Ubuntu 10.04 or later. Here LAVA
is pre-compiled and packaged as Debian packages (debs). The installation
scripts embedded in the packages take care for setting up additional services
so usually this is the best method to quickly have a self-contained running
installation. The downside is longer release period as packaging takes
additional time after each release. Another downside is that our support is
limited to Ubuntu.

To install using the ppa ::

 $ sudo add-apt-repository ppa:linaro-validation/ppa
 $ sudo apt-get update
 $ sudo apt-get install lava-dashboard

.. todo::
 Installation instructions from sources and pypi
