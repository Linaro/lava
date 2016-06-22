.. _writing_tests:

Writing a LAVA test definition
##############################

A LAVA Test Job comprises

#. Metadata describing the test job
#. The actions and parameters to set up the test(s)
#. The instructions to run as part of the test(s)

For certain tests, the instructions can be included inline with the
actions. For more complex tests or to share test definitions across
multiple devices, environments and purposes, the test can use a
repository of YAML files.

.. _test_definition_yaml:

Writing a test definition YAML file
***********************************

The YAML is downloaded from the repository (or handled inline)
and installed into the test image, either as a single file or as part
of a git or bzr repository. (See :ref:`test_repos`)

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

If the file is not under version control (i.e. not in a git or bzr
repository), the **version** of the file must also be specified in the
metadata:

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

The instructions within the YAML file can include installation
requirements for images based on supported distributions (currently,
Ubuntu or Debian):

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

When an external PPA or package repository (specific to debian based
distros) is required for installation of packages, it can be added in
the `install` section as follows:

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

Debian and Ubuntu repositories must be signed for the apt package
management tool to trust them as package sources. To tell the system
to trust extra repositories listed here, add references to the PGP
keys used in the `keys` list. These may be either the names of Debian
keyring packages (already available in the standard Debian archive),
or PGP key IDs. If using key IDs, LAVA will import them from a key
server (`pgp.mit.edu`). PPA keys will be automatically imported using
data from `launchpad.net`. FIXME! Is this true?

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
######################################

#. All commands need to be executables available on the device. This
   is why the metadata section includes an "os" flag, so that commands
   specific to that operating system can be accessed.
#. All tests will be run in a dedicated working directory. If a test
   repository is used, the local checkout of that repository will also
   be located within that same directory.
#. Avoid assumptions about the base system - if a test needs a
   particular interpreter, executable or environment, ensure that this
   is available. That can be done either by using the `install` step
   in the test definition, or by building or installing the components
   as a series of commands in the `run` steps. Many images will not
   contain any servers or compilers and many will only have a limited
   range of interpreters pre-installed. Some of those may also have
   reduced functionality compared to versions on other systems.
#. Keep the YAML files relatively small and clean to promote easier
   reuse in other tests or devices. It is often better to have many
   YAML files to be run in sequence than to have a large overly complex
   YAML file within which some tests will fail due to changed assumptions.
   e.g. a smoke test YAML file which checks for USB devices is not
   useful on devices where ``lsusb`` is not functional. It is much easier to
   scan through the test results if the baseline for the test is that
   all tests should be expected to pass on all supported platforms.
#. Avoid use of redirects and pipes inside the run steps. If the command
   needs to use redirection and/or pipes, use a custom script in your
   repository and execute that script instead. See :ref:`custom_scripts`
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
          combine the repositories into one or copy the script into
          multiple repositories. The copy of the script executed will be
          the one below the working directory of the current test.

.. _custom_scripts:

Writing custom scripts to support tests
***************************************

When multiple actions are necessary to get usable output, write a
custom script to go alongside the YAML and execute that script as a
run step:

.. code-block:: yaml

  run:
      steps:
          - $(./my-script.sh arguments)

You can choose whatever scripting language you prefer, as long as you
ensure that it is available in the test image.

Take care when using ``cd`` inside custom scripts - always store the
initial return value or the value of ``pwd`` before the call and change
back to that directory at the end of the script.

Example of a custom script wrapping the output:

https://git.linaro.org/lava-team/refactoring.git/blob/HEAD:/functional/unittests.sh

The script is simply called directly from the test shell definition:

https://git.linaro.org/lava-team/refactoring.git/blob/HEAD:/functional/server-pipeline-unit-tests.yaml

Example V2 job using this support:

https://git.linaro.org/lava-team/refactoring.git/blob/HEAD:/functional/qemu-server-pipeline.yaml

.. _interpreters_scripts:

Script interpreters
===================

#. **shell** - consider running the script with ``set -x`` to see the
   operation of the script in the LAVA log files. Ensure that if your
   script expects ``bash``, use the bash shebang line ``#!/bin/bash``
   and ensure that ``bash`` is installed in the test image. The
   default shell may be ``busybox`` or ``dash``, so take care with
   non-POSIX constructs in your shell scripts if you use
   ``#!/bin/sh``.
#. **python** - ensure that python is installed in the test image. Add
   all the python dependencies necessary for your script.
#. **perl** - ensure that any modules required by your script are
   available, bearing in mind that some images may only have a basic
   perl installation with a limited selection of modules.

If your YAML file does not reside in a repository, the YAML *run steps*
will need to ensure that a network interface is raised, install a
tool like ``wget`` and then use that to obtain the script, setting
permissions if appropriate.

.. _test_case_commands:

Using commands as test cases
****************************

If all your test does is feed the textual output of commands to the
log file, you will spend a lot of time reading log files. To make test
results easier to parse, aggregate and compare, individual commands can
be converted into test cases with a pass or fail result. The simplest
way to do this is to use the exit value of the command. A non-zero
exit value is a test case failure. This produces a simple list of
passes and failures in the result bundle which can be easily tracked
over time.

To use the exit value, simply precede the command with a call to
``lava-test-case`` with a test-case name (no spaces):

.. code-block:: yaml

  run:
      steps:
          - lava-test-case test-ls-command --shell ls /usr/bin/sort
          - lava-test-case test-ls-fail --shell ls /user/somewhere/else/

Use subshells instead of backticks to execute a command as an argument
to another command:

.. code-block:: yaml

  - lava-test-case pointless-example --shell ls $(pwd)

For more details on the contents of the YAML file and how to construct
YAML for your own tests, see the :ref:`test_developer`.

.. _parsing_output:

Parsing command outputs
***********************

FIXME - is this still relevant for V2? Still mentions a bundle...

If the test involves parsing the output of a command rather than simply
relying on the exit value, LAVA can use a pass/fail/skip/unknown output:

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

The result of the above test would be a result bundle:

.. code-block:: yaml

  test1 -> pass
  test2 -> fail
  test3 -> pass
  test4 -> pass

.. _recording_test_results:

Recording test case results
***************************

``lava-test-case`` can also be used with a parser with the extra
support for checking the exit value of the call:

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

``--result`` must always be specified.

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


.. note:: Each time a choice of unit is passed to lava-test-case, this
	  will **overwrite** the choice of unit for all test cases
	  with the same name. All previous test results will be
	  changed to use the new ``units`` string. To counteract this,
	  you can set the units manually on the test result details
	  page. Setting this unit manually will raise a warning, since
	  this will affect all the other test results in the system.

FIXME: This is a mess, both in terms of documentation and
implementation?!?

.. _best_practices:

Best practices for writing a LAVA test job
##########################################

A test job may consist of several LAVA test definitions and multiple
deployments, but this flexibility needs to be balanced against the
complexity of the job and the ways to analyse the results.

Use different test definitions for different test areas
*******************************************************

Follow the standard UNIX model of *Make each program do one thing
well*. Make a set of separate test definitions. Each definition should
concentrate on one area of functionality and test that one area
thoroughly.

Use different jobs for different test environments
**************************************************

While it is supported to reboot from one distribution and boot into a
different one, the usefulness of this is limited. If the first
environment fails, the subsequent tests might not run at all.

Use a limited number of test definitions per job
************************************************

While LAVA tries to ensure that all tests are run, adding more and
more test repositories to a single LAVA job increases the risk that
one test will fail in a way that prevents the results from all tests
being collected.

Overly long sets of test definitions also increase the complexity of
the log files, which can make it hard to identify why a particular job
failed.

Splitting a large job into smaller chunks also means that the device can
run other jobs for other users in between the smaller jobs.
