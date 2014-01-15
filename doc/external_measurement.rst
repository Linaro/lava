.. _hooks_external_measurement:

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
as produced on the device (this on-disk representation is not yet
fully documented).  If a hook produces output, it will be attached to
the test result.

As many interesting hooks need to have information about the device
being tested, there is a facility for putting values from the device
config into the environment of the hooks.  For example, the following
test definition sets the environment variable ``$DEVICE_TYPE`` to the
value of the ``device_type`` key::

  handler:
    handler-name: shell-hooks
    params:
      device_config_vars:
        DEVICE_TYPE: device_type
      handlers:
        ...

For a slightly silly example of a shell hook, let's try to mark any
test that takes more than 10 seconds (as viewed from the host) as
failed, even if they report success on the device, and also attach
some meta data about the device to each test result.

The start hook (``start-hook.sh`` in the repository) just records the
current unix timestamp in a file (we can just use the cwd as a scratch
storage area)::

  #!/bin/sh
  date +%s > start-time

The end hook (``end-hook.sh``) just records the end time::

  #!/bin/sh
  date +%s > end-time

The postprocess hook (``post-process-result-hook.sh``) reads the times
recorded by the above hooks, overwrites the result if necessary and
creates an attachment containing the device type::

  #!/bin/sh
  start_time=`cat start-time`
  end_time=`cat end-time`
  if [ $((end_time - start_time)) -gt 10 ]; then
      echo fail > $1/result
  fi
  echo $DEVICE_TYPE > $1/attachments/device-type.txt

A test definition that glues this all together would be::

  metadata:
    format: Lava-Test Test Definition 1.0
    name: shell-hook-example

  run:
    steps:
      - lava-test-case pass-test --shell sleep 5
      - lava-test-case fail-test --shell sleep 15

  handler:
    handler-name: shell-hooks
    params:
      device_config_vars:
        DEVICE_TYPE: device_type
      handlers:
        start_testcase: start-hook.sh
        end_testcase: end-hook.sh
        postprocess_test_result: post-process-result-hook.sh

A repository with all the above piece is on Launchpad in the branch
`lp:~linaro-validation/+junk/shell-hook-example`_ so an action for
your job file might look like::

    {
        "command": "lava_test_shell",
        "parameters": {
            "testdef_repos": [{"bzr-repo": "lp:~linaro-validation/+junk/shell-hook-example"}],
            "timeout": 1800
         }
    },

.. _`lp:~linaro-validation/+junk/shell-hook-example`: http://bazaar.launchpad.net/~linaro-validation/+junk/shell-hook-example/files
