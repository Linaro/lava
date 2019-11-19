.. index:: lava test shell

.. _lava_test_shell:

Lava-Test Test Definition 1.0
*****************************

The ``lava_test_shell`` action provides a way to employ a black-box
style testing approach with the target device. It does this by
deploying an ``overlay`` to the target device; it requires a POSIX
system to be running on the target. The test definition format is
designed to be flexible, allowing many options on how to do things.

Quick start to Test Definition 1.0
**********************************

A minimal test definition looks like this:

.. code-block:: yaml

  metadata:
    name: passfail
    format: "Lava-Test-Shell Test Definition 1.0"
    description: "A simple passfail test for demo."

  run:
    steps:
      - lava-test-case test-1 --result pass
      - lava-test-case test-2 --result fail

Only the mandatory metadata parameters have been included (name, format,
description).

.. _versioned_test_definitions:

Versioned test definitions
==========================

If your test definition is not part of a git repository then it is must
include a **version** parameter in the metadata section like in the following
example.

.. code-block:: yaml

  metadata:
    name: passfail
    format: "Lava-Test-Shell Test Definition 1.0"
    description: "A simple passfail test for demo."
    version: "1.0"

.. _lava_test_shell_setx:

How a lava test shell is run
============================

A lava-test-shell is run by:

* *building* the test definition into a shell script.

  .. note:: This shell script will include ``set -e``, so a failing step will
      abort the entire test run. If you need to specify a step that might fail,
      finish the command with ``|| true`` to make that failure **not** abort
      the test run.

* copying an ``overlay`` onto the device. The ``overlay`` contains
  both the test script and the rest of the
  :ref:`lava_test_helpers`. and setup code to run the test script when
  the device boots

* booting the device and letting the test run

* retrieving the output from the device and turning it into a test result

* run subsequent test definitions, if any.

Writing a test for lava-test-shell
==================================

For the majority of cases, the above approach is the easiest thing to do: write
shell code that outputs "test-case-id: result" for each test case you are
interested in. See the Test Developer Guide:

* :ref:`test_developer`.
* :ref:`writing_tests_1_0`.

.. warning:: Older support for parse patterns and fixup dictionaries
   is **deprecated** because the support has proven too difficult to
   use and very hard to debug. The syntax is Python but converted
   through YAML and the scope is global. The support remains only for
   compatibility with existing Lava Test Shell Definitions. In future,
   any desired parsing should be moved into a :ref:`custom script
   <custom_scripts>` contained within the test definition
   repository. This script can simply call ``lava-test-case`` directly
   with the relevant options once the data is parsed. This has the
   advantage that the log output from LAVA can be tested directly as
   input for the script.

When a test runs, ``$PATH`` is arranged so that some LAVA-specific
utilities are available:

* :ref:`lava-test-case`
* :ref:`lava-background-process-start`
* :ref:`lava-background-process-stop`

.. seealso:: :ref:`multinode_api`

.. _lava-test-case:

lava-test-case
==============

lava-test-case records the results of a single test case. For example:

.. code-block:: yaml

  steps:
    - "lava-test-case simpletestcase --result pass"
    - "lava-test-case fail-test --shell false"

It has two forms. One takes arguments to describe the outcome of the test case.
The other takes the shell command to run, and the exit code of this shell
command is used to produce the test result.

Both forms take the name of the testcase as the first argument.

Specifying results directly
---------------------------

The first form takes these additional arguments:

* ``--result $RESULT``: $RESULT should be one of pass/fail/skip/unknown
* ``--measurement $MEASUREMENT``: A numerical measurement associated with the test result
* ``--units $UNITS``: The units of $MEASUREMENT

``--result`` must always be specified.  For example:

.. code-block:: yaml

  run:
    steps:
      - "lava-test-case simpletestcase --result pass"
      - "lava-test-case bottle-count --result pass --measurement 99 --units bottles"

If ``--measurement`` is used, ``--units`` must also be specified, even
if the unit is just a count.

The most useful way to produce output for ``lava-test-case result`` is
:ref:`custom_scripts` which allow preparation of LAVA results from other
sources, complete with measurements. This involves calling ``lava-test-case``
from scripts executed by the YAML file:

.. code-block:: python

 #!/usr/bin/env python

 from subprocess import call


 def test_case():
     """
     Calculate something based on a test
     and return the data
     """
     return {"name": "test-rate", "result": "pass",
         "units": "Mb/s", "measurement": 4.23}


 def main():
     data = test_case()
     call(
         ['lava-test-case',
          data['name'],
          '--result', data['result'],
          '--measurement', data['measurement'],
          '--units', data['units']])
     return 0

 if __name__ == '__main__':
     main()

The custom scripts themselves can be called from a ``lava-test-case`` using the
``--shell`` command to test whether failures from the tests caused a subsequent
failure in the custom script.

Using the exit status of a command
----------------------------------

The second form of ``lava-test-case`` is indicated by the ``--shell``
argument, for example:

.. code-block:: yaml

  run:
    steps:
      - "lava-test-case fail-test --shell false"
      - "lava-test-case pass-test --shell true"

The result of a ``shell`` call will only be recorded as a pass or fail,
dependent on the exit code of the command.

.. _yaml_parameters:

Using parameters in the job to update the definition
====================================================

Parameters used in the test definition YAML can be controlled from the
YAML job file. See the following YAML test definition for ean example
of how it works.

.. literalinclude:: examples/test-definitions/params.yaml
   :language: yaml
   :linenos:
   :lines: 1-23
   :emphasize-lines: 9-11, 19-21

Download or view params.yaml: `examples/test-definitions/params.yaml
<examples/test-definitions/params.yaml>`_

This Lava-Test Test Definition 1.0 can be used in a simple QEMU test
job:

.. literalinclude:: examples/test-jobs/qemu-stretch-params.yaml
   :language: yaml
   :linenos:
   :lines: 43-54
   :emphasize-lines: 10-12

Download or view the test job:
`examples/test-jobs/qemu-stretch-params.yaml
<examples/test-jobs/qemu-stretch-params.yaml>`_

.. _lava-background-process-start:

lava-background-process-start
=============================

This starts a process in the background, for example:

.. code-block:: yaml

  steps:
    - lava-background-process-start MEM --cmd "free -m | grep Mem | awk '{print $3}' >> /tmp/memusage"
    - lava-background-process-start CPU --cmd "grep 'cpu ' /proc/stat"
    - uname -a
    - lava-background-process-stop CPU
    - lava-background-process-stop MEM --attach /tmp/memusage text/plain --attach /proc/meminfo application/octet-stream

The arguments are:

#. The name that is used to identify the process later in
   lava-background-process-stop
#. The command line for the process to be run in the background

See :ref:`test_attach`.

.. _lava-background-process-stop:

lava-background-process-stop
============================

This stops a process previously started in the background using
:ref:`lava-background-process-start`. The user can attach files to the test run
if there is a need.

For example:

.. code-block:: yaml

  steps:
    - lava-background-process-start MEM --cmd "free -m | grep Mem | awk '{print $3}' >> /tmp/memusage"
    - lava-background-process-start CPU --cmd "grep 'cpu ' /proc/stat"
    - uname -a
    - lava-background-process-stop CPU
    - lava-background-process-stop MEM --attach /tmp/memusage text/plain --attach /proc/meminfo application/octet-stream

The arguments are:

#. The name that was specified in lava-background-process-start
#. (optional) An indication that you want to attach file(s) to the
   test run with specified mime type. See :ref:`test_attach`.

Handling test attachments
=========================

Handling of attachments is in the control of the test writer. A separate
publishing location can be configured or text based data is simply to output
the contents into the log file.

.. seealso:: :ref:`publishing_artifacts`

Deprecated elements
*******************

.. _handling_dependencies_deprecated:

Handling Dependencies (Debian)
==============================

.. warning:: The ``install`` element of Lava-Test Test Definition 1.0
   is **DEPRECATED**. See :ref:`test_definition_portability`. Newly
   written Lava-Test Test Definition 1.0 files should not use
   ``install``.

If your test requires some packages to be installed before its run it can
express that in the ``install`` section with:

.. code-block:: yaml

  install:
      deps:
          - linux-libc-dev
          - build-essential

.. _adding_repositories_deprecated:

Adding Git Repositories
===========================

If the test needs code from a shared repository, the action can clone this
data on your behalf with:

.. code-block:: yaml

  install:
      git-repos:
          - git://git.linaro.org/people/davelong/lt_ti_lava.git

  run:
      steps:
          - cd lt_ti_lava
          - echo "now in the git cloned directory"

git-repos
---------

There are several options for customizing git repository handling in
the git-repos action, for example:

.. code-block:: yaml

  install:
      git-repos:
          - url: https://git.lavasoftware.org/lava/lava.git
            skip_by_default: False
          - url: https://git.lavasoftware.org/lava/lava.git
            destination:  lava-d-r
            branch:       release
          - url: https://git.lavasoftware.org/lava/lava.git
            destination:  lava-d-s
            branch:       staging

* `url` is the git repository URL.

* `skip_by_default` (optional) accepts a True or False. Repositories can be
  skipped by default in the test definition YAML and enabled for particular
  jobs directly in the job submission YAML, and vice versa.

* `destination` (optional) is the directory in which the git repository given
  in `url` should be cloned, to override normal git behavior.

* `branch` (optional) is the branch within the git repository given in `url`
  that should be checked out after cloning.

.. _install_steps_deprecated:

Install Steps
=============

.. warning:: The ``install`` element of Lava-Test Test Definition 1.0
   is **DEPRECATED**. See :ref:`test_definition_portability`. Newly
   written Lava-Test Test Definition 1.0 files should not use
   ``install``.

Before the test shell code is executed, it will optionally do some install work
if needed. For example if you needed to build some code from a git repo you
could do:

.. code-block:: yaml

  install:
      git-repos:
          - git://git.linaro.org/people/davelong/lt_ti_lava.git

      steps:
          - cd lt_ti_lava
          - make

.. note:: The repo steps are done in the dispatcher itself. The install steps
          are run directly on the target.

.. _parse_patterns_1_0_deprecated:

Parse patterns
==============

.. warning:: Parse patterns and fixup dictionaries are confusing and hard to
   debug. The syntax is Python and the support remains for compatibility with
   existing Lava Test Shell Definitions. With LAVA V2, it is recommended to
   move parsing into a :ref:`custom script <custom_scripts>` contained within
   the test definition repository. The script can simply call
   ``lava-test-case`` directly with the relevant options once the data is
   parsed. This has the advantage that the log output from LAVA can be tested
   directly as input for the script.

You may need to incorporate an existing test that doesn't output results in in
the required ``pass``/``fail``/``skip``/``unknown`` format required by LAVA.
The parse section has a fixup mechanism that can help:

.. code-block:: yaml

  parse:
      pattern: "(?P<test_case_id>.*-*)\\s+:\\s+(?P<result>(PASS|FAIL))"
      fixupdict:
          PASS: pass
          FAIL: fail

.. note:: Pattern can be double-quoted or single quoted. If it's double-quoted,
          special characters need to be escaped. Otherwise, no escaping is
          necessary.

Single quote example:

.. code-block:: yaml

  parse:
      pattern: '(?P<test_case_id>.*-*)\s+:\s+(?P<result>(PASS|FAIL))'
      fixupdict:
          PASS: pass
          FAIL: fail
