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

Follow the `Quick Developer Setup`_ instructions to get started.

.. _Quick Developer Setup: standalonesetup.html

Usage with the LAVA Scheduler
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The scheduler is useful for automating LAVA Dispatcher environment setup, describing test scenarios (the list of tests to invoke) and finally storing the results in the LAVA dashboard.

This scenario can be configured by following our `deployment instructions`_
or the Documentation link on any LAVA instance.

.. _deployment instructions: /static/docs/
