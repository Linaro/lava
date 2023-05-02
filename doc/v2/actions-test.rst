.. _test_action:

Test Action Reference
#####################

The pipeline jobs (LAVA v2) have retained compatibility with respect to the
content of Lava-Test-Shell Test Definitions although the submission format
has changed:

#. The :ref:`test action <test_action>` will **never** boot the device -
   a :ref:`boot action <boot_action>` **must** be specified. Multiple test
   operations need to be specified as multiple definitions listed within
   the same test block.

#. The LAVA support scripts are prepared by the :ref:`deploy action <deploy_action>`
   action and the same scripts will be used for all test definitions
   until next ``deploy`` block is encountered.

There are 3 types of test actions:

* :ref:`lava-test-shell definitions <test_action_definitions>`
  (YAML directive: ``definitions``) are used for POSIX compliant operating
  systems on the :term:`DUT`. The deployed system is expected to support
  a POSIX shell environment (``/bin/ash``, ``/bin/dash`` or ``/bin/bash``
  are the most common) so that LAVA can execute the LAVA Test Shell Helper
  scripts.

* :ref:`Output monitors <monitor_test_action>` (YAML directive:
  ``monitors``) are used for devices which have no POSIX shell and start
  the test (and corresponding output) immediately after booting, for
  example microcontroller/IoT boards.

* :ref:`Interactive tests <interactive_test_action>` (YAML directive:
  ``interactive``) are further extension of "monitor" tests idea, allowing
  not just matching some output from a device, but also feeding some input.
  They are useful for non-POSIX shells like bootloaders (u-boot for instance)
  and other interactive command-line applications.


.. seealso:: :ref:`lava_test_helpers`

.. contents::
   :backlinks: top

.. index:: test action definitions (POSIX)

.. _test_action_definitions:

Definitions
***********

repository
==========

A publicly readable repository location.

from
====

The type of the repository is **not** guessed, it **must** be specified
explicitly. Support is available for ``git``. Support is planned
for ``url`` and ``tar``.

git
---

A remote git repository which needs to be cloned by the dispatcher.

inline
------

A simple test definition present in the same file as the job submission,
instead of from a separate file or VCS repository. This allows tests to be run
based on a single file. When combined with ``file://`` URLs to the ``deploy``
parameters, this allows tests to run without needing external access. See
:ref:`inline_test_definition_example`.

path
----

The path within that repository to the YAML file containing the test
definition.

name
----

(required) - replaces the name from the YAML.

params
------

(optional): Pass parameters to the Lava Test Shell Definition. The format is a
YAML dictionary - the key is the name of the variable to be made available to
the test shell, the value is the value of that variable.

.. code-block:: yaml

  - test:
      definitions:
      - repository: https://git.linaro.org/lava-team/hacking-session.git
        from: git
        path: hacking-session-debian.yaml
        name: hacking
        params:
          IRC_USER: ""
          PUB_KEY: ""

.. code-block:: yaml

  - test:
      definitions:
      - repository: git://git.linaro.org/lava-team/lava-functional-tests.git
        from: git
        path: lava-test-shell/smoke-tests-basic.yaml
        name: smoke-tests
      - repository: https://git.linaro.org/lava-team/lava-functional-tests.git
        from: git
        path: lava-test-shell/single-node/singlenode03.yaml
        name: singlenode-advanced

Skipping elements of test definitions
=====================================

When a single test definition is to be used across multiple deployment types
(e.g. Debian and OpenEmbedded), it may become necessary to only perform certain
actions within that definition in specific jobs. The ``skip_install`` support
has been migrated from V1 for compatibility. Other methods of optimizing test
definitions for specific deployments may be implemented in V2 later.

The available steps which can be (individually) skipped are:

deps
----

skip running ``lava-install-packages`` for the ``deps:`` list of the
``install:`` section of the definition.

keys
----

skip running ``lava-add-keys`` for the ``keys:`` list of the ``install:``
section of the definition.

sources
-------

skip running ``lava-add-sources`` for the ``sources:`` list of the ``install:``
section of the definition.

steps
-----

skip running any of the ``steps:`` of the ``install:`` section of the
definition.

all
---

identical to ``['deps', 'keys', 'sources', 'steps']``

Example syntax:

.. code-block:: yaml

  - test:
      failure_retry: 3
      name: kvm-basic-singlenode
      timeout:
        minutes: 5
      definitions:
      - repository: git://git.linaro.org/lava-team/lava-functional-tests.git
        from: git
        path: lava-test-shell/smoke-tests-basic.yaml
        name: smoke-tests
      - repository: http://git.linaro.org/lava-team/lava-functional-tests.git
        skip_install:
        - all
        from: git
        path: lava-test-shell/single-node/singlenode03.yaml
        name: singlenode-advanced

The following will skip dependency installation and key addition in
the same definition:

.. code-block:: yaml

  - test:
      failure_retry: 3
      name: kvm-basic-singlenode
      timeout:
        minutes: 5
      definitions:
      - repository: git://git.linaro.org/lava-team/lava-functional-tests.git
        from: git
        path: lava-test-shell/smoke-tests-basic.yaml
        name: smoke-tests
      - repository: http://git.linaro.org/lava-team/lava-functional-tests.git
        skip_install:
        - deps
        - keys
        from: git
        path: lava-test-shell/single-node/singlenode03.yaml
        name: singlenode-advanced

.. _inline_test_definition_example:

Inline test definition example
==============================

https://git.lavasoftware.org/lava/lava/blob/master/lava_dispatcher/tests/sample_jobs/kvm-inline.yaml

.. code-block:: yaml

  - test:
      failure_retry: 3
      definitions:
      - repository:
          metadata:
            format: Lava-Test Test Definition 1.0
            name: smoke-tests-basic
            description: "Basic system test command for Linaro Ubuntu images"
            os:
            - ubuntu
            scope:
            - functional
            devices:
            - panda
            - panda-es
            - arndale
            - vexpress-a9
            - vexpress-tc2
          run:
            steps:
            - lava-test-case linux-INLINE-pwd --shell pwd
            - lava-test-case linux-INLINE-uname --shell uname -a
            - lava-test-case linux-INLINE-vmstat --shell vmstat
            - lava-test-case linux-INLINE-ifconfig --shell ifconfig -a
            - lava-test-case linux-INLINE-lscpu --shell lscpu
            - lava-test-case linux-INLINE-lsusb --shell lsusb
            - lava-test-case linux-INLINE-lsb_release --shell lsb_release -a
        from: inline
        name: smoke-tests-inline
        path: inline/smoke-tests-basic.yaml


Additional support
==================

The V2 dispatcher supports some additional elements in Lava Test Shell which
will not be supported in the older V1 dispatcher.

Result checks
-------------

LAVA collects results from internal operations, these form the ``lava`` test
suite results as well as from the submitted test definitions. The full set of
results for a job are available at:

.. code-block:: none

 results/1234

LAVA records when a submitted test definition starts execution on the test
device. If the number of test definitions which started is not the same as the
number of test definitions submitted (allowing for the ``lava`` test suite
results), a warning will be displayed on this page.

TestSets
--------

A TestSet is a group of lava test cases which will be collated within the LAVA
Results. This allows queries to look at a set of related test cases within a
single definition.

.. code-block:: yaml

  - test:
     definitions:
     - repository:
         run:
           steps:
           - lava-test-set start first_set
           - lava-test-case date --shell ntpdate-debian
           - ls /
           - lava-test-case mount --shell mount
           - lava-test-set stop
           - lava-test-case uname --shell uname -a

This results in the ``date`` and ``mount`` test cases being included into a
``first_set`` TestSet, independent of other test cases. The TestSet is
concluded with the ``lava-test-set stop`` command, meaning that the ``uname``
test case has no test set, providing a structure like:

.. code-block:: yaml

 results:
   first_set:
     date: pass
     mount: pass
   uname: pass

.. code-block:: python

 {'results': {'first_set': {'date': 'pass', 'mount': 'pass'}, 'uname': 'pass'}}

Each TestSet name must be valid as a URL, which is consistent with the
requirements for test definition names and test case names in the V1
dispatcher.

For TestJob ``1234``, the ``uname`` test case would appear as:

.. code-block:: none

 results/1234/testset-def/uname

The ``date`` and ``mount`` test cases are referenced via the TestSet:

.. code-block:: none

 results/1234/testset-def/first_set/date
 results/1234/testset-def/first_set/mount

A single test definition can start and stop different TestSets in sequence, as
long as the name of each TestSet is unique for that test definition.

.. index:: test action interactive

.. _interactive_test_action:

Interactive
***********

An interactive test action allows to interact with a non-POSIX shell or
just arbitrary interactive application. For instance, the shell of u-boot
bootloader.

The workflow of the interactive test action is:

* send the ``command`` to the :term:`DUT`, unless empty
* if ``echo: discard`` is specified, discard next output line (assumed to be
  an echo of the command)
* wait for the ``prompts``, ``successes`` or ``failures``
* if a ``name`` is defined, log the result for this command (as soon as a prompt or a message is matched)
* if a ``successes`` or ``failures`` was matched, wait for the ``prompts``

.. note:: The interactive test action expects the prompt to be already matched
  before it starts. If this is not the case, then wait for the prompt by
  adding an empty ``command`` directive as described below.

A u-boot interactive test might look like:

.. code-block:: yaml

  - test:
      interactive:
      - name: network
        prompts: ["=>", "/ # "]
        echo: discard
        script:
        - name: dhcp
          command: dhcp
          successes:
          - message: "DHCP client bound to address"
          failures:
          - message: "TIMEOUT"
            exception: InfrastructureError
            error: "dhcp failed"
        - name: setenv
          command: "setenv serverip {SERVER_IP}"
        - name: wait for the prompt
          command:

name
====

The name of the :ref:`test suite <results_test_suite>`.

prompts
=======

The list of possible prompts for the interactive session. In many cases,
there is just one prompt, but if shell has different prompts for different
states, it can be accommodated. (Prompts can also include regexps, as any
other match strings).

echo
====

If set to ``discard``, after each sent ``command`` of a ``script``, discard
the next output line (assumed to be an echo of the command). This option
should be set when interacting with shell (like u-boot shell) that will echo
the command, to avoid false positive matches. Note that this options applies
to every ``command`` in the script. If you need different value of this
option for different commands, you would need to group them in different
``script``'s.

script
======

The list of commands to send and what kind of output to expect:

* ``name``: If present, log the result (pass/fail) of this command
  under the given name (as a testcase). If not present, and the command
  fails, the entire test will fail (with :ref:`TestError <test_error_exception>`).
* ``command``: The command (string) to send to device, followed by newline.
  The command can use variables that will be substituted with live data,
  like ``{SERVER_IP}``. If value is empty (``command:`` in YAML), nothing
  is sent, but output matching (prompts/successes/failures) will be
  performed as usual. (Note that empty ``command:`` is different from empty
  string ``command: ""``. In the latter case, just a newline will be sent
  to device.)
* ``failures`` and ``successes``: Each optional. If present, check the
  device output for the given patterns.

``successes`` should be a list of dictionaries with just one key:

* ``message``: The string (or regexp) to match. Substring match is
  performed, so care should be taken to reliably encode the match pattern.
  (E.g. ``message: 4`` would match "4" appearing anywhere in the output,
  e.g. "14" or "41").

``failures`` should be a list of dictionaries with:

* ``message``: The string (or regexp) to match. Substring match is performed.
* ``exception`` (optional): If the message indicates a fatal problem,
  an exception can be raised, one of:
  :ref:`InfrastructureError <infrastructure_error_exception>`,
  :ref:`JobError <job_error_exception>`,
  :ref:`TestError <test_error_exception>`. If not present, the error
  is not fatal and will be recorded just as a failed testcase in test
  results. (If this is a named command; as mentioned above, failure of
  unnamed ("not a testcase") command leads to implicit TestError).

* ``error``: if defined, the exception message which will appear in the job log

If ``successes`` is defined, but LAVA matches one of the prompts
instead, an error will be recorded (following the logic that the lack
of expected success output is an error). This means that in many cases
you don't need to specify ``failures`` - any output but the successes
will be recorded as an error.

However, if ``successes`` is not defined, then matching a prompt will
generate a passing result (this is useful for interactive commands
which don't generate any output on success; of course, in this case
you would need to specify ``failures`` to catch them).

.. seealso:: :ref:`writing_tests_interactive`

.. index:: test action monitors

.. _monitor_test_action:

Monitors
********

Test jobs using Monitors **must**:

#. Be carefully designed to automatically execute after boot.

#. Emit a unique ``start`` string:

   #. Only once per boot operation.
   #. Before any test operation starts.

#. Emit a unique ``end`` string:

   #. Only once per boot operation.
   #. After all test operations have completed.

#. Provide a regular expression which matches all expected test output
   and maps the output to results **without** leading to excessively
   long test case names.

``start`` and ``end`` strings will match part of a line but make sure
that each string is long enough that it can only match once per boot.

If ``start`` does not match, the job will timeout with no results.

If ``end`` does not match, the job will timeout but the results (of
the current boot) will already have been reported.

name
====

The name of the :ref:`test suite <results_test_suite>`.

.. code-block:: yaml

 - test:
     monitors:
     - name: tests
       start: BOOTING ZEPHYR
       end: PROJECT EXECUTION SUCCESSFUL
       pattern: '(?P<test_case_id>\d+ *- [^-]+) (?P<measurement>\d+) tcs = [0-9]+ nsec'
       fixupdict:
         PASS: pass
         FAIL: fail

If the device output is of the form:

.. code-block:: none

 ***** BOOTING ZEPHYR OS v1.7.99 - BUILD: Apr 18 2018 10:00:55 *****
 |-----------------------------------------------------------------------------|
 |                            Latency Benchmark                                |
 |-----------------------------------------------------------------------------|
 |  tcs = timer clock cycles: 1 tcs is 12 nsec                                 |
 |-----------------------------------------------------------------------------|
 | 1 - Measure time to switch from ISR back to interrupted thread              |
 | switching time is 107 tcs = 1337 nsec                                       |
 |-----------------------------------------------------------------------------|

 ...

 PROJECT EXECUTION SUCCESSFUL

The above regular expression can result in test case names like:

.. code-block:: none

 1_measure_time_to_switch_from_isr_back_to_interrupted_thread_switching_time_is

The raw data will be logged as:

.. code-block:: none

 test_case_id: 1 - Measure time to switch from ISR back to interrupted thread              |
 | switching time is

.. caution:: Notice how the regular expression has not closed the match
   at the end of the "line" but has continued on to the first
   non-matching character. The test case name then concatenates all
   whitespace and invalid characters to a single underscore. LAVA uses pexpect
   to perform output parsing. pexpect docs explain how to find line ending
   strings: https://pexpect.readthedocs.io/en/stable/overview.html#find-the-end-of-line-cr-lf-conventions

.. code-block:: python

 r'(?P<test_case_id>\d+ *- [^-]+) (?P<measurement>\d+) tcs = [0-9]+ nsec'

The test_case_id will be formed from the match of the expression ``\d+
*- [^-]+`` followed by a single space - but **only** if the rest of the
expression matches as well.

The measurement will be taken from the match of the expression ``\d+``
preceded by a single space and followed by the **exact** string ``tcs =
`` which itself must be followed by a number of digits, then a single
space and finally the **exact** string ``nsec`` - but only if the rest
of the expression also matches.

.. seealso:: `Regular Expression HOWTO for Python3 <https://docs.python.org/3/howto/regex.html>`_
