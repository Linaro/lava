.. _usage:

=====
Usage
=====

Workflow Overview
=================

LAVA Dispatcher can be used in two different ways. One is standalone (without
the LAVA Scheduler) and another is managed (when LAVA Dispatcher is controlled
by the LAVA Scheduler).

Standalone usage
^^^^^^^^^^^^^^^^

In standalone mode a human operator installs LAVA Dispatcher on some device
(development board, laptop or other computer or a virtual machine), edits the
job file that are to be executed and then executes them manually (by manually
running LAVA Dispatcher, the actual execution process are non-interactive).

Typically this mode is based on the following sequence of commands:

#. Install lava-dispatcher (from PPA or source) along with the required dependencies on LAVA Server.
#. Configure local or remote development boards and device types.
#. Add or edit job files which are to be executed.
#. Execute dispatcher manually: $ sudo lava-dispatch ./lava-ltp-job.json

At last dispatcher will publish the test results to LAVA Dashboard.

Usage with the LAVA Scheduler
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The scheduler is useful for automating LAVA Dispatcher environment setup, describing test scenarios (the list of tests to invoke) and finally storing the results in the LAVA dashboard.

Typically this mode is based on the following sequence of commands:

#. Install lava-dispatcher (from PPA or source) along with the required dependencies on LAVA Server.
#. Configure local or remote development boards and device types.
#. Add or edit job files which are to be executed.
#. Configure LAVA Scheduler to execute job files.

Debug
^^^^^
    
Debug 

.. todo::

    Describe how to collect enough information to debug dispatcher when the job execution failed.

Check test result on LAVA Dashboard
===================================

.. todo::

    Describe how to view test results on dashboard.

Debug with serial log
==============================

.. todo::

    Describe the information including logging information/warning and exception information.
