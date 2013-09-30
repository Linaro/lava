.. LAVA Dispatcher documentation master file, created by sphinx-quickstart on
   Fri Sep 23 10:15:12 2011.  You can adapt this file completely to your
   liking, but it should at least contain the root `toctree` directive.

LAVA Dispatcher Documentation
*****************************

LAVA Dispatcher is used to dispatch test jobs from server(master node) to the target
boards in validation farm, and publish the test result back to dashboard. It is
scheduled by validation scheduler, and it could also run as standalone.

You can see an up-to-date list of supported target devices by looking at the
`device types`_ in Launchpad.

.. _device types: http://bazaar.launchpad.net/~linaro-validation/lava-dispatcher/trunk/files/head:/lava_dispatcher/default-config/lava-dispatcher/device-types

Installation
============

The best way to install this is by doing a full deployment of LAVA. This is
documented on our `main project page`_ or the Documentation link on any
LAVA instance. However, you can also setup the dispatcher for 
`stand-alone development and testing`_.

.. _main project page: /static/docs/
.. _stand-alone development and testing: standalonesetup.html

Indices and tables
==================

.. toctree::
   :maxdepth: 2

   standalonesetup.rst
   configuration.rst
   jobfile.rst
   usage.rst
   lava_test_shell.rst
   external_measurement.rst
   arm_energy_probe.rst
   sdmux.rst
   multinode.rst
   proxy.rst
   lava-image-creation.rst
   qemu-deploy.rst
   kvm-deploy.rst
   nexus-deploy.rst
   ipmi-pxe-deploy.rst
   components.rst
   process.rst

* :ref:`search`

Source code, bugs and patches
=============================

You can get the source code with git using ``git clone
http://git.linaro.org/git-ro/lava/lava-dispatcher.git``.
Patches can be submitted to
http://lists.linaro.org/mailman/listinfo/linaro-validation mailing list.

Please report all bugs at https://bugs.launchpad.net/lava-dispatcher/+filebug.

Most of the team is usually available in ``#linaro-lava`` on ``irc.freenode.net``.
Feel free to drop by to chat and ask questions.
