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

This class defines three methods that you almost certainly want to
override:

 1. ``start_testcase(self, test_case_id):``

    Called when a testcase starts on the device.  The return value of
    this method is passed to both ``end_testcase`` and
    ``processes_test_run``.

    The expected case is something like: starting a process that
    captures some data from or about the device and returning a
    dictionary that indicates the pid of that process and where its
    output is going.

 2. ``end_testcase(self, test_case_id, case_data):``

    Called when a testcase ends on the device.  ``case_data`` is
    whatever the corresponding ``start_testcase`` call returned.

    The expected case here is that you will terminate the process that
    was started by ``start_testcase``.

 3. ``process_test_result(self, test_result, case_data):``

    Here you are expected to add the data that was recorded during the
    test run to the results.  You need to know about the bundle format
    to do this.

These methods are invoked with catch-all exception handlers around
them so you don't have to be super careful in their implementation: it
should not be possible to crash the whole dispatcher with a typo in
one of them.

There are other methods you might want to override in some situations
-- see the source for more.

Here is a very simple complete handler::

  import datetime
  import time

  from json_schema_validator.extensions import timedelta_extension

  from lava_dispatcher.signals import SignalHandler

  class AddDuration(SignalHandler):

      def start_testcase(self, test_case_id):
          return {
              'starttime': time.time()
              }

      def end_testcase(self, test_case_id, data):
          data['endtime'] = time.time()

      def postprocess_test_result(self, test_result, data):
          delta = datetime.timedelta(seconds=data['endtime'] - data['starttime'])
          test_result['duration'] = timedelta_extension.to_json(delta)

Specifying a handler
--------------------

A handlers are named the test definition, for example::

  handler:
    handler-name: add-duration

The name is the name of an `entry point`_ from the
``lava.signal_handlers`` "group".  The entry point must be provided by
a package installed into the instance that the dispatcher is running
from.

.. _`entry point`: http://packages.python.org/distribute/pkg_resources.html#entry-points

Providing handlers as shell scripts
-----------------------------------

Using the 'shell-hooks' handler that is distributed with the
dispatcher it is possible to write handlers as scripts in the same VCS
repository as the test definition itself.

The simplest usage looks like this::

  handler:
    handler-name: shell-hooks
    params:
      handlers:
        start_testcase: start-testcase.sh
        end_testcase: end-testcase.sh
        postprocess_test_result: postprocess-test-result.sh

The scripts named in ``handlers`` are invoked with a test-case
specific directory as the current working directory so they can store
and access data in local paths.  The scripts named by
``start_testcase`` and ``end_testcase`` are invoked with no arguments
but ``postprocess_test_result`` is invoked with a single argument: a
directory which contains the on-disk representation of the test result
as produced on the device.
