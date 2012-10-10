.. LAVA Dispatcher documentation master file, created by sphinx-quickstart on
   Fri Sep 23 10:15:12 2011.  You can adapt this file completely to your
   liking, but it should at least contain the root `toctree` directive.

LAVA Dispatcher Documentation
=============================
LAVA Dispatcher is used to dispatch test jobs from server(master node) to the target
boards in validation farm, and publish the test result back to dashboard. It is
scheduled by validation scheduler, and it could also run as standalone.

.. seealso:: To learn more about LAVA see https://launchpad.net/lava


Features
========

* Ability to accept, parse and run a job which consists of different actions
  and test cases, then upload test result to LAVA Dashboard on an ARM target
  system.
* Support ARM target boards including Beagle, Panda, i.MX51 EVK, i.MX53
  QuickStart, Snowball, Origen, Versatile Express, Fast Models, and QEMU.
* Support Android system on Panda, i.MX53 QuickStart board, Snowball, Origen,
  Versatile Express, and Fast Models.
* Support for local user-defined configuration data for boards, device types.
* Extensible device types and boards configuration editing, can add new device
  and new board.
* Make use of the output of LAVA test, which is Linaro Dashboard Bundle format,
  upload test results to the LAVA Dashboard for result archiving and analysis.

Installation
============

The best way to install this is by doing a full deployment of LAVA. This is
documented on our `main project page`_. However, you can also setup the
dispatcher for `stand-alone development and testing`_.

.. _main project page: http://lava.readthedocs.org/en/latest/
.. _stand-alone development and testing: standalonesetup.html

Source code, bugs and patches
=============================

The project is maintained on Launchpad at
http://launchpad.net/lava-dispatcher/.

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

