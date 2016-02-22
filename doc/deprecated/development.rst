LAVA development (Deprecated model)
###################################

.. Resource: Various places in the wiki

.. _lava_architecture:

Understanding the LAVA architecture
***********************************

.. note:: This is the current architecture and differs
   from the :ref:`dispatcher_design` which will replace it. The new
   design isolates the database from the worker and replaces the
   scheduler daemon with a slave dispatcher daemon which communicates
   over :term:`ZMQ`.

The first step for LAVA development is understanding its architecture.
The major LAVA components are depicted below::

                  +-------------+
                  |web interface|
                  +-------------+
                         |
                         v
                     +--------+
               +---->|database|
               |     +--------+
               |
   +-----------+------[worker]-------------+
   |           |                           |
   |  +----------------+     +----------+  |
   |  |scheduler daemon|---→ |dispatcher|  |
   |  +----------------+     +----------+  |
   |                              |        |
   +------------------------------+--------+
                                  |
                                  V
                        +-------------------+
                        | device under test |
                        +-------------------+

* The *web interface* is responsible for user interaction, including
  presenting test jobs results, navigating devices, and receiving job
  submissions through it's XMLRPC API. It stores all data, including
  submitted jobs, into the *RDBMS*.
* The *scheduler daemon* is responsible for allocating jobs that were
  submitted. It works by polling the database, reserving devices to run
  those jobs, and triggering the dispatcher to actually run the tests.
  [#deprecated]_
* The *dispatcher* is responsible for actually running the job. It will
  manage the serial connection to the :term:`DUT`, image downloads and
  collecting results etc. When doing local tests or developing new
  testing features, the dispatcher can usually be run standalone without
  any of the other components.

On single-server deployments, both the web interface and the worker
components (scheduler daemon + dispatcher) run on a same server. You can
also install one or more separated worked nodes, that will only run
scheduler daemon + dispatcher.

Adding support for new devices
******************************

.. TODO

to LAVA - Board addition howto?
Requirements for a device in LAVA

What do I need to create a test image for LAVA?
What do I need to create a master image for LAVA?
* 8GB SD Card

Writing LAVA extensions
***********************

*TODO*


API Docs
********

*Coming soon*.

..
  TODO determine with classes (and from which components) we want to document
  TODO figure out how to actually make the modules available in the l-d-t tree (or in the path)

.. [#deprecated] These terms reflect objects and methods which will be
   removed after the migration to the new :ref:`dispatcher_design`.
