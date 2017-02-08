.. index:: writing test definition

.. _writing_tests:

Writing a LAVA test definition
##############################

A LAVA Test Job comprises

#. Metadata describing the test job
#. The actions and parameters to set up the test(s)
#. The instructions to run as part of the test(s)

For certain tests, the instructions can be included inline with the actions.
For more complex tests or to share test definitions across multiple devices,
environments and purposes, the test can use a repository of YAML files.

.. _test_definition_yaml:

Writing a test definition YAML file
***********************************

The YAML is downloaded from the repository (or handled inline) and installed
into the test image, either as a single file or as part of a git or bzr
repository. (See :ref:`test_repos`)

Each test definition YAML file contains metadata and instructions.
Metadata includes:

#. A format string recognised by LAVA
#. A short name of the purpose of the file
#. A description of the instructions contained in the file.

.. code-block:: yaml

  metadata:
      format: Lava-Test Test Definition 1.0
      name: singlenode-advanced
      description: "Advanced (level 3): single node test commands for Linux Linaro ubuntu Images"


.. note:: the short name of the purpose of the test definition, i.e.,
          value of field **name**, must not contain any non-ascii
          characters or special characters from the following list,
          including white space(s): ``$& "'`()<>/\|;``

If the file is not under version control (i.e. not in a git or bzr repository),
the **version** of the file must also be specified in the metadata:

.. code-block:: yaml

  metadata:
      format: Lava-Test Test Definition 1.0
      name: singlenode-advanced
      description: "Advanced (level 3): single node test commands for Linux Linaro ubuntu Images"
      version: "1.0"

There are also optional metadata fields:

#. The email address of the maintainer of this file.
#. A list of the operating systems which this file can support.
#. A list of devices which are expected to be able to run these
   instructions.

.. code-block:: yaml

      maintainer:
          - user.user@linaro.org
      os:
          - ubuntu
      scope:
          - functional
      devices:
          - kvm
          - arndale
          - panda
          - beaglebone-black
          - beagle-xm

The instructions within the YAML file can include installation requirements for
images based on supported distributions (currently, Ubuntu or Debian):

.. code-block:: yaml

  install:
      deps:
          - curl
          - realpath
          - ntpdate
          - lsb-release
          - usbutils


.. note:: for an `install` step to work, the test **must** first raise
          a usable network interface without running any instructions
          from the rest of the YAML file. If this is not possible,
          raise a network interface manually as a `run` step and
          install or build the components directly then.

When an external PPA or package repository (specific to debian based distros)
is required for installation of packages, it can be added in the `install`
section as follows:

.. code-block:: yaml

  install:
      keys:
          - 7C751B3F
          - 6CCD4038
      sources:
          - https://security.debian.org
          - ppa:linaro-maintainers/tools
      deps:
          - curl
          - ntpdate
          - lava-tool

Debian and Ubuntu repositories must be signed for the apt package management
tool to trust them as package sources. To tell the system to trust extra
repositories listed here, add references to the PGP keys used in the `keys`
list. These may be either the names of Debian keyring packages (already
available in the standard Debian archive), or PGP key IDs. If using key IDs,
LAVA will import them from a key server (`pgp.mit.edu`). PPA keys will be
automatically imported using data from `launchpad.net`. For more information,
see the documentation of ``apt-add-repository``, `man 1 apt-add-repository
<https://manpages.debian.org/cgi-bin/man.cgi?query=apt-add-repository&apropos=0&sektion=0&manpath=Debian+8+jessie&format=html&locale=en>`_

See `Debian apt source addition
<https://git.linaro.org/people/senthil.kumaran/test-definitions.git/blob_plain/92406804035c450fd7f3b0ab305ab9d2c0bf94fe:/debian/ppa.yaml>`_
and `Ubuntu PPA addition <https://git.linaro.org/people/senthil.kumaran/test-definitions.git/blob_plain/92406804035c450fd7f3b0ab305ab9d2c0bf94fe:/ubuntu/ppa.yaml>`_

.. note:: When a new source is added and there are no 'deps' in the
          'install' section, then it is the test writer's
          responsibility to run `apt update` before attempting any
          other `apt` operation elsewhere in the test definition.

.. note:: When `keys` are not added for an apt source repository
          listed in the `sources` section, packages may fail to
          install if the repository is not trusted. LAVA does not add
          the `--force-yes` option during `apt` operations which would
          over-ride the trust check.

The principal purpose of the test definitions in the YAML file is to
run commands on the device. These are specified in the run steps:

.. code-block:: yaml

  run:
      steps:

.. _writing_test_commands:

Writing commands to run on the device
*************************************

#. All commands need to be executables available on the device. This is why the
   metadata section includes an "os" flag, so that commands specific to that
   operating system can be accessed.

#. All tests will be run in a dedicated working directory. If a test repository
   is used, the local checkout of that repository will also be located within
   that same directory.

#. Avoid assumptions about the base system - if a test needs a particular
   interpreter, executable or environment, ensure that this is available. That
   can be done either by using the `install` step in the test definition, or by
   building or installing the components as a series of commands in the `run`
   steps. Many images will not contain any servers or compilers and many will
   only have a limited range of interpreters pre-installed. Some of those may
   also have reduced functionality compared to versions on other systems.

#. Keep the YAML files relatively small and clean to promote easier reuse in
   other tests or devices. It is often better to have many YAML files to be run
   in sequence than to have a large overly complex YAML file within which some
   tests will fail due to changed assumptions. e.g. a smoke test YAML file
   which checks for USB devices is not useful on devices where ``lsusb`` is not
   functional. It is much easier to scan through the test results if the
   baseline for the test is that all tests should be expected to pass on all
   supported platforms.

#. Check for the existence of one of the LAVA test helper scripts, like
   ``lava-test-case``, in the directories specified by the ``PATH`` environment
   variable to determine how the script should report results. For example,
   the script may want to use ``echo`` or ``print()`` when not running inside
   LAVA and ``lava-test-case`` only when that script exists.

   .. seealso:: :ref:`test_definition_portability`

#. Avoid use of redirects and pipes inside the run steps. If the command needs
   to use redirection and/or pipes, use a custom script in your repository and
   execute that script instead. See :ref:`custom_scripts`

#. Take care with YAML syntax. These lines will fail with wrong syntax:

.. code-block:: yaml

    - echo "test1: pass"
    - echo test2: fail

   While this syntax will pass:

.. code-block:: yaml

    - echo "test1:" "pass"
    - echo "test2:" "fail"

.. note:: Commands must not try to access files from other test
          definitions. If a script needs to be in multiple tests, either
          combine the repositories into one or copy the script into multiple
          repositories. The copy of the script executed will be the one below
          the working directory of the current test.

.. index:: inline test definition

.. _inline_test_definitions:

Using inline test definitions
*****************************

Rather than refer to a separate file or VCS repository, it is also possible to
create a test definition directly inside the test action of a job submission.
This is called an ``inline test definition``:

.. include:: examples/test-jobs/inline-test-definition-example.yaml
     :code: yaml
     :start-after: # START-INLINE-TEST-BLOCK
     :end-before: # END-INLINE-TEST-BLOCK

An inline test definition **must**:

#. Use the ``from: inline`` method.
#. Provide a path to which the definition will be written
#. Specify the metadata, at least:

   #. ``format: Lava-Test Test Definition 1.0``
   #. ``name``
   #. ``description``

Inline test definitions will be written out as **single files**, so if the test
definition needs to call any scripts or programs, those need to be downloaded
or installed before being called in the inline test definition.

`Download or view inline example <examples/test-jobs/inline-test-definition-example.yaml>`_

.. _custom_scripts:

Writing custom scripts to support tests
***************************************

.. note:: Custom scripts are not available in an :term:`inline` definition,
   *unless* the definition itself downloads the script and makes it
   executable.

When multiple actions are necessary to get usable output, write a custom script
to go alongside the YAML and execute that script as a run step:

.. code-block:: yaml

  run:
      steps:
          - $(./my-script.sh arguments)

You can choose whatever scripting language you prefer, as long as you
ensure that it is available in the test image.

Take care when using ``cd`` inside custom scripts - always store the initial
return value or the value of ``pwd`` before the call and change back to that
directory at the end of the script.

Example of a custom script wrapping the output:

https://git.linaro.org/lava-team/refactoring.git/tree/functional/unittests.sh

The script is simply called directly from the test shell definition:

https://git.linaro.org/lava-team/refactoring.git/tree/functional/server-pipeline-unit-tests.yaml

Example V2 job using this support:

https://git.linaro.org/lava-team/refactoring.git/tree/functional/qemu-server-pipeline.yaml

.. note:: Make sure that your custom scripts output some useful information,
   including some indication of progress, in all test jobs but control the
   total amount of output to make the logs easier to read.

.. _interpreters_scripts:

Script interpreters
===================

#. **shell** - consider running the script with ``set -x`` to see the operation
   of the script in the LAVA log files. Ensure that if your script expects
   ``bash``, use the bash shebang line ``#!/bin/bash`` and ensure that ``bash``
   is installed in the test image. The default shell may be ``busybox`` or
   ``dash``, so take care with non-POSIX constructs in your shell scripts if
   you use ``#!/bin/sh``.

#. **python** - ensure that python is installed in the test image. Add all the
   python dependencies necessary for your script.

#. **perl** - ensure that any modules required by your script are  available,
   bearing in mind that some images may only have a basic perl installation
   with a limited selection of modules.

If your YAML file does not reside in a repository, the YAML *run steps* will
need to ensure that a network interface is raised, install a tool like ``wget``
and then use that to obtain the script, setting permissions if appropriate.

.. _test_case_commands:

Using commands as test cases
****************************

If all your test does is feed the textual output of commands to the log file,
you will spend a lot of time reading log files. To make test results easier to
parse, aggregate and compare, individual commands can be converted into test
cases with a pass or fail result. The simplest way to do this is to use the
exit value of the command. A non-zero exit value is a test case failure. This
produces a simple list of passes and failures in the result bundle which can be
easily tracked over time.

To use the exit value, simply precede the command with a call to
``lava-test-case`` with a test-case name (no spaces):

.. code-block:: yaml

  run:
      steps:
          - lava-test-case test-ls-command --shell ls /usr/bin/sort
          - lava-test-case test-ls-fail --shell ls /user/somewhere/else/

Use subshells instead of backticks to execute a command as an argument to
another command:

.. code-block:: yaml

  - lava-test-case pointless-example --shell ls $(pwd)

For more details on the contents of the YAML file and how to construct YAML for
your own tests, see the :ref:`test_developer`.

.. _parsing_output:

Parsing command outputs
***********************

.. comment This duplicates lava_test_shell.rst Advanced Parsing

.. warning:: Parse patterns and fixup dictionaries are confusing and
   hard to debug. The syntax is Python and the support remains for
   compatibility with existing Lava Test Shell Definitions. With LAVA V2, it is
   recommended to move parsing into a :ref:`custom script <custom_scripts>`
   contained within the test definition repository. The script can simply call
   ``lava-test-case`` directly with the relevant options once the data is
   parsed. This has the advantage that the log output from LAVA can be tested
   directly as input for the script.

If the test involves parsing the output of a command rather than simply relying
on the exit value, LAVA can use a pass/fail/skip/unknown output:

.. code-block:: yaml

  run:
     steps:
        - echo "test1:" "pass"
        - echo "test2:" "fail"
        - echo "test3:" "skip"
        - echo "test4:" "unknown"

The quotes are required to ensure correct YAML parsing.

The parse section can supply a parser to convert the output into
test case results:

.. code-block:: yaml

  parse:
      pattern: "(?P<test_case_id>.*-*):\\s+(?P<result>(pass|fail))"

The result of the above test would be a set of results:

.. code-block:: yaml

  test1 -> pass
  test2 -> fail
  test3 -> pass
  test4 -> pass

.. _recording_test_results:

Recording test case results
***************************

``lava-test-case`` can also be used with a parser with the extra support for
checking the exit value of the call:

.. code-block:: yaml

  run:
     steps:
        - echo "test1:" "pass"
        - echo "test2:" "fail"
        - lava-test-case echo1 --shell echo "test3:" "pass"
        - lava-test-case echo2 --shell echo "test4:" "fail"

This syntax will result in extra test results:

.. code-block:: yaml

  test1 -> pass
  test2 -> fail
  test3 -> pass
  test4 -> fail
  echo1 -> pass
  echo2 -> pass

Note that ``echo2`` **passed** because the ``echo "test4:" "fail"`` returned
an exit code of zero.

Alternatively, the ``--result`` command can be used to output the value
to be picked up by the parser:

.. code-block:: yaml

  run:
     steps:
        - echo "test1:" "pass"
        - echo "test2:" "fail"
        - lava-test-case test5 --result pass
        - lava-test-case test6 --result fail

This syntax will result in the test results:

.. code-block:: yaml

  test1 -> pass
  test2 -> fail
  test5 -> pass
  test6 -> fail


.. _recording_test_measurements:

Recording test case measurements and units
******************************************

Various tests require measurements and ``lava-test-case`` supports
measurements and units per test at a precision of 10 digits.

``--result`` must always be specified and only numbers can be recorded
as measurements (to support charts based on measurement trends).

.. seealso:: :ref:`recording_test_result_data`

.. code-block:: yaml

  run:
     steps:
        - echo "test1:" "pass"
        - echo "test2:" "fail"
        - lava-test-case test5 --result pass --measurement 99 --units bottles
        - lava-test-case test6 --result fail --measurement 0 --units mugs

This syntax will result in the test results:

.. code-block:: yaml

  test1 -> pass
  test2 -> fail
  test5 -> pass -> 99.0000000000 bottles
  test6 -> fail -> 0E-10 mugs

The simplest way to use this with real data is to use a custom script
which runs ``lava-test-case`` with the relevant arguments.

Recording sets of test cases
****************************

Test Set is a way to allow test writers to subdivide individual results
within a single Lava Test Shell Definition using an arbitrary label.

Some test definitions run the same test with different parameters. To
distinguish between these similar tests, it can be useful to use a test set.

.. seealso: :ref:`test_set_results`

.. _test_case_references:

Recording test case references
******************************

Some test cases may relate to specific bug reports or have specific URLs
associated with the result. :ref:`recording_simple_strings` can be recorded
separately but if you need to relate a test case result to a URL, consider
using ``lava-test-reference``:

.. code-block:: shell

    lava-test-reference TEST_CASE_ID --result pass|fail|skip|unknown --reference URL

The TEST_CASE_ID can be the same as an existing test case or a new test case.

.. code-block:: yaml

  run:
     steps:
        - lava-test-case checked --result pass
        - lava-test-reference checked --result pass --reference https://staging.validation.linaro.org/static/doc/v2/index.html

.. note:: The URL should be a simple file reference, complex query strings could
   fail to be parsed.

.. seealso:: :ref:`publishing_artifacts`

.. _test_action_parameters:

Test shell parameters
*********************

The test action in the job definition supports parameters which are passed to
the test shell. These parameters can be used to allow different job definitions
to use a single test shell definition in multiple ways. A common example of
this is a :term:`hacking session`.

The parameters themselves are inserted into the ``lava-test-runner`` and will
be available to **all** Lava Test Shell Definitions used in that test job. The
parameters are **not** exported. The test shell definition needs to support
using the parameter and can then use that information to change how external
programs behave. This may include using ``export``, it may include changing the
command line options.

.. _recording_test_result_data:

Recording test case data
************************

.. _recording_simple_strings:

Simple strings
==============

A version string or similar can be recorded as a ``lava-test-case``
name::

 lava-test-case ${VERSION} --result pass

Version strings need specific handling to compare for newer, older etc. so LAVA
does not support comparing or ordering of such strings beyond simple
alphanumeric sorting. A :ref:`custom script <custom_scripts>` would be the best
way to handle such results.

For example, if your test definition uses a third party code repository, then
it is always useful to use whatever support exists within that repository to
output details like the current version or most recent commit hash or log
message. This information may be useful when debugging a failure in the tests
later. If or when particular tags, branches, commits or versions fail to work,
the custom script can check for the supported or unsupported versions or names
and report a ``fail`` test case result.

.. seealso:: :ref:`test_definition_portability`

Files
=====

.. seealso:: In LAVA V1, data files could be published using
   ``lava-test-case-attach``. In V2, there is a new way to publish directly
   from the :term:`DUT` - the :ref:`publishing API
   <publishing_artifacts>`.

Measurements
============

``lava-test-case`` supports recording integer or floating point measurements
for a particular test case. When a measurement is supplied, a text string can
also be supplied to be used as the units of that measurement, e.g. seconds or
bytes. Results are used to track changes across test jobs over time, so results
which cannot be compared as integers or floating point numbers cannot be used
as measurements.

.. seealso:: :ref:`recording_test_measurements`

The lava test results
=====================

Each test job creates a set of results in a reserved test suite called
``lava``. LAVA will reject any submission which tries to set ``lava`` as the
test definition name. These results are generated directly by the LAVA actions
and include useful metadata including the actual time taken for specific
actions and data generated during the test operation such as the VCS commit
hash of each test definition included into the overlay.

The results are available in the same ways as any other test suite. In addition
to strings and measurements, the ``lava`` suite also include an element called
**extra**.

Examples
--------

* The ``lava`` test suite may contain a result for the ``git-repo-action`` test
  case, generated during the running of the test. The **extra** data in this
  test case could look like:

  .. code-block:: yaml

   extra:
     path: ubuntu/smoke-tests-basic.yaml
     repository: git://git.linaro.org/qa/test-definitions.git
     success: c50a99ebb5835501181f4e34417e38fc819a6280

* The **duration** result for the ``auto-login-action`` records the time taken
  to boot the kernel and get to a login prompt. The **extra** data for the same
  result includes details of kernel messages identified during the boot
  including stack traces, kernel panics and other alerts, if any.

Results from any test suite can be tracked using :term:`queries <query>`,
:term:`charts <chart>` and / or the :ref:`REST API <downloading_results>`.

.. note:: The results in the ``lava`` test suite are managed by the software
   team. The results in the other test suites are entirely down to the test
   writer to manage. The less often the **names** of the test definitions
   and the test cases change, the easier it will be to track those test cases
   over time.

.. _best_practices:

Best practices for writing a LAVA test job
******************************************

A test job may consist of several LAVA test definitions and multiple
deployments, but this flexibility needs to be balanced against the complexity
of the job and the ways to analyse the results.

.. _test_definition_portability:

Write portable test definitions
===============================

``lava-test-shell`` is a useful helper but that can become a limitation. Avoid
relying upon the helper for anything more than the automation by putting the
logic and the parsing of your test into a more competent language. *Remember*:
as test writer, **you** control which languages are available inside your test.

``lava-test-shell`` has to try and get by with not much more than
``busybox ash`` as the lowest common denominator.

**Please don't expect lava-test-shell to do everything**.

Let ``lava-test-shell`` provide you with a directory layout containing your
scripts, some basic information about the job and a way of reporting test case
results - that's about all it should be doing outside of the
:ref:`multinode_api`.

**Do not lock yourself out of your tests**

#. Do not make your test code depend on the LAVA infrastructure any more than
   is necessary for automation. Make sure you can always run your tests by
   downloading the test code to a target device using a clean environment,
   installing its dependencies (the test code itself could do this), and
   running a single script. Emulation can be used in most cases where access to
   the device is difficult. Even if the values in the output change, the format
   of the output from the underlying test operation should remain the same,
   allowing a single script to parse the output in LAVA and in local testing.

#. Make the LAVA-specific part as small as possible, just enough
   to, for example, gather any inputs that you get via LAVA, call the main
   test program, and translate your regular output into ways to
   tell lava how the test went (if needed).

#. Standard test jobs are intended to showcase the design of the test job,
   **not** the test definitions. These test definitions tend to be very
   simplistic and are **not** intended to be examples of how to write test
   definitions, just how to prepare test jobs.

.. seealso:: :ref:`custom_scripts`

Rely less on install: steps
===========================

To make your test portable, the goal of the ``install`` block of any test
definition should be to get the raw LAVA environment up to the point where a
developer would be ready to start test-specific operations. For example,
installing package dependencies. Putting the operations into the ``run:`` steps
also means that the test writer can report results from these operations.

Whilst compatibility with V1 has been retained in most areas of the test shell,
there can be differences in how the install steps behave between V1 and V2.
Once V1 is removed, other changes are planned for the test shell to make it
easier for test writers to create portable tests. It is possible that the
``install:`` behaviour of the test shell could be restricted at this time.

Consider moving ``install: git-repos:`` into a run step or directly into a
:ref:`custom_script <custom_scripts>` along with the other setup (for example,
switching branches or compiling the source tree). Then, when debugging the test
job, a test writer can setup a similar environment and simply call exactly the
same script.

Use different test definitions for different test areas
=======================================================

Follow the standard UNIX model of *Make each program do one thing well*. Make a
set of separate test definitions. Each definition should concentrate on one
area of functionality and test that one area thoroughly.

Use different jobs for different test environments
==================================================

While it is supported to reboot from one distribution and boot into a different
one, the usefulness of this is limited. If the first environment fails, the
subsequent tests might not run at all.

Use a limited number of test definitions per job
================================================

While LAVA tries to ensure that all tests are run, adding more and more test
repositories to a single LAVA job increases the risk that one test will fail in
a way that prevents the results from all tests being collected.

Overly long sets of test definitions also increase the complexity of the log
files, which can make it hard to identify why a particular job failed.

Splitting a large job into smaller chunks also means that the device can run
other jobs for other users in between the smaller jobs.

Retain at least some debug output in the final test definitions
===============================================================

Information about which commit or version of any third-party code is and will
remain useful when debugging failures. When cloning such code, call a script in
the code or use the version control tools to output information about the
cloned copy. You may want to include the most recent commit message or the
current commit hash or version control tag or branch name.

If an item of configuration is important to how the test operates, write a test
case or a custom script which reports this information. Even if this only
exists in the test job log output, it will still be useful when comparing the
log files of other similar jobs.

Check for specific support as a test case
=========================================

If a particular package, service, script or utility **must** exist and / or
function for the rest of your test definition to operate, **test** for this
functionality.

Any command executed by ``lava-test-case <name> --shell`` will report a test
case as ``pass`` if that command exits zero and ``fail`` if that command exited
non-zero. If the command is complex or needs pipes or redirects, create a
simple script which returns the exit code of the command.

.. note:: remember that the test shell runs under ``set -e``, so if you need to
   prevent the rest of a test definition from exiting, you can report a
   non-zero exit code from your scripts and call the script directly instead of
   as a test case.

.. _controlling_tool_output:

Control the amount of output from scripts and tools
===================================================

Many tools available in distributions have ways to control the amount of output
during operation. A balance is needed and test writers are recommended to check
for available support. Wherever possible, use the available options to opt for
output intended for log file output rather than your typical terminal.

When writing your own scripts, consider using ``set -x`` or wrapping certain
blocks with ``set -x``, ``set +x`` when using shell scripts. With other
languages, use ``print()`` and similar functions often, especially where the
script uses a conditional that can be affected by parameters from within the
test job.

Specific tools
--------------

* **apt** - When calling ``apt update`` or ``apt-get update``, **always** use
  the ``-q`` option to avoid filling the log file with repeated progress output
  during downloads. This option still gives output but formats it in a way that
  is much more useful when reading log files compared to an interactive
  terminal.

* **wget** - **always** use the ``-S --progress=dot:giga`` options for
  downloads as this reduces the total amount of progress information during the
  operation.

