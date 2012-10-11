.. LAVA Dispatcher documentation master file, created by sphinx-quickstart on
   Fri Sep 23 10:15:12 2011.  You can adapt this file completely to your
   liking, but it should at least contain the root `toctree` directive.

LAVA Dispatcher Documentation
=============================
LAVA Dispatcher is used to dispatch test jobs from server(master node) to the target
boards in validation farm, and publish the test result back to dashboard. It is
scheduled by validation scheduler, and it could also run as standalone.

You can see an up-to-date list of supported target devices by looking at the
`device types`_ in Launchpad.

.. _device types: http://bazaar.launchpad.net/~linaro-validation/lava-dispatcher/trunk/files/head:/lava_dispatcher/default-config/lava-dispatcher/device-types

Installation
============

The best way to install this is by doing a full deployment of LAVA. This is
documented on our `main project page`_. However, you can also setup the
dispatcher for `stand-alone development and testing`_.

.. _main project page: http://lava.readthedocs.org/en/latest/
.. _stand-alone development and testing: standalonesetup.html

Indices and tables
==================

.. toctree::
   :maxdepth: 2

   standalonesetup.rst
   configuration.rst
   jobfile.rst
   usage.rst
   proxy.rst

* :ref:`search`

Source code, bugs and patches
=============================

The project is maintained on Launchpad at
http://launchpad.net/lava-dispatcher/.

We maintain an online log of `release notes`_

.. _release notes: changes.html

You can get the source code with bazaar using ``bzr branch
lp:lava-dispatcher``.  Patches can be submitted using Launchpad merge proposals
(for introduction to this and topic see
https://help.launchpad.net/Code/Review).

Please report all bugs at https://bugs.launchpad.net/lava-dispatcher/+filebug.

Most of the team is usually available in ``#linaro`` on ``irc.freenode.net``.
Feel free to drop by to chat and ask questions.

Indices and tables
==================

.. toctree::
   :maxdepth: 2

   standalonesetup.rst
   configuration.rst
   jobfile.rst
   usage.rst
   changes.rst
   code.rst
   todo.rst

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

