.. LAVA Dispatcher documentation master file, created by
   sphinx-quickstart on Fri Sep 23 10:15:12 2011.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

LAVA Dispatcher Documentation
=============================
LAVA Dispatcher is to dispatch test jobs from server(master node) to the target boards in validation farm, and publish the test result back to dashboard. It is scheduled by validation scheduler, and it could also run as standalone.

.. seealso:: To learn more about LAVA see https://launchpad.net/lava

Contents:

.. toctree::
   :maxdepth: 1

   installation.rst
   jobfile.rst
   usage.rst
   changes.rst
   todo.rst


60 second example
=================

This example will run on Ubuntu Lucid and beyond::

 $ sudo add-apt-repository ppa:linaro-validation/ppa
 $ sudo apt-get update
 $ sudo apt-get install lava-dispatcher
 $ sudo lava-dispatch ./lava-ltp-job.json
 (lava-ltp-job.json can be found in lava-dispatcher/doc)

.. seealso:: For detailed installation instructions see :ref:`installation`
.. seealso:: For writing a new dispatcher job file see :ref:`jobfile`

Features
========

* Ability to accept, parse and run a job which consists of different actions and test cases, then upload test result to LAVA Dashboard on an ARM target system.
* Support ARM target boards including Beagle, Panda, i.MX51 EVK, i.MX53 QuickStart and Snowball, more boards support is coming.
* Support Android system on Beagle, Panda and i.MX53 QuickStart board, more boards support is coming.
* Support for local user-defined configuration data for boards, device types.
* Extensible device types and boards configuration editing, can add new device and new board.
* Make use of the output of LAVA test, which is Linaro Dashboard Bundle format, upload test results to the LAVA Dashboard for result archiving and analysis.

.. seealso:: See what's new in :ref:`version_0_5_2`

.. todo::

    Add inline document to source code and open code reference in doc

Latest documentation
====================

This documentation may be out of date, we try to make sure that all the latest
and greatest releases are always documented on http://lava-dispatcher.readthedocs.org/


Source code, bugs and patches
=============================

The project is maintained on Launchpad at http://launchpad.net/lava-dispatcher/.

You can get the source code with bazaar using ``bzr branch lp:lava-dispatcher``.
Patches can be submitted using Launchpad merge proposals (for introduction to
this and topic see https://help.launchpad.net/Code/Review).

Please report all bugs at https://bugs.launchpad.net/lava-dispatcher/+filebug.

Most of the team is usually available in ``#linaro`` on ``irc.freenode.net``.
Feel free to drop by to chat and ask questions.

Indices and tables
==================

.. toctree::
   :maxdepth: 2

   installation.rst
   jobfile.rst
   usage.rst
   changes.rst
   todo.rst

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

