Hooks, Signals and External Measurement
=======================================

.. warning::
   This is work in progress!  Expect changes in details until at least early 2013.

It is sometimes the case that an interesting test cannot be run solely
on the device being tested: additional data from somewhere else is
required.  For example, a test of the sound subsystem may want to
generate audio, play it, capture it on another system and then compare
the generated and captured audio.  A `lava-test-shell`_ test can be
written to send **signals** to indicate when a test case starts and
finishes which can be handled by a **handler** specified by the test
definition.

.. _`lava-test-shell`: lava_test_shell.html

Signals
-------

A signal is a message from the system being tested ("device") to the
system the dispatcher is running on ("host").  The messaging is
synchronous and uni-directional: lava-test-shell on the device will
wait for the signal to be processesed and there is no way for the
device to receieve data from the host.

Generally speaking, we expect a test author will only be interested in
handling the "start test case" and "end test case" signals that are
sent by ``lava-test-case --shell``.

Handler
-------

A handler is a Python class that subclasses:

.. autoclass:: lava_dispatcher.signals.SignalHandler
   :members:

This class defines six methods that you may which to override, and
three that you almost certainly want to:

 1. ``start_testcase(self, test_case_id):``

    Called when a testcase starts on the device.  Here you might want
    to start 

 2. ``end_testcase(self, test_case_id):``
 3. ``process_test_run(self, test_run):``
