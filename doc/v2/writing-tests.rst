.. _writing_tests:

Writing a LAVA test definition
##############################

A LAVA Test Job comprises of

#. the actions and parameters to setup the test(s)
#. the instructions to run as part of the test(s)

For certain tests, the instructions can be included inline with the
actions. For more complex tests or to share test definitions across
multiple devices, environments and purposes, the test can use a
repository of YAML files.

.. _test_definition_yaml:

Writing a test definition YAML file
***********************************

The YAML is downloaded from the repository (or handled as an inline) and
installed into the test image, either as a single file or as part of
a git or bzr repository. (See :ref:`test_repos`)

Each test definition YAML file contains metadata and instructions.
Metadata includes:

#. A format string recognised by LAVA
#. A short name of the purpose of the file
#. A description of the instructions contained in the file.

::

  metadata:
      format: Lava-Test Test Definition 1.0
      name: singlenode-advanced
      description: "Advanced (level 3): single node test commands for Linux Linaro ubuntu Images"


.. note:: the short name of the purpose of the test definition, i.e., value of field **name**,
          should not contain any non-ascii characters and special characters
          from the following list, including white space(s): ``$& "'`()<>/\|;``

If the file is not under version control (i.e. not in a git or bzr
repository), the version of the file must also be specified in the
metadata:

::

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

::

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
Ubuntu or Debian)::

  install:
      deps:
          - curl
          - realpath
          - ntpdate
          - lsb-release
          - usbutils


.. note:: the test **must** raise a usable network interface without
          running any instructions from the rest of the YAML file or
          the installation will fail. If this is not always possible,
          raise a network interface manually as a run step and install
          or build the components directly.

When an external PPA or package repository (specific to debian based
distros) is required for installation of packages, it could be
added in the `install` section as follows::

  install:
      keys:
          - 7C751B3F
          - 6CCD4038
      sources:
          - http://security.debian.org
          - ppa:linaro-maintainers/tools
      deps:
          - curl
          - ntpdate
          - lava-tool

`keys` refer to the gpg keys that needs to be imported in order to
trust a repository that is getting added in the `sources`
section. `keys` could be either debian keyring packages or gpg security
keys (the key server used for importing is `pgp.mit.edu`) For PPAs
(referred from `launchpad.net`) the keys are automatically imported.

See `Debian apt source addition
<https://git.linaro.org/people/senthil.kumaran/test-definitions.git/blob_plain/92406804035c450fd7f3b0ab305ab9d2c0bf94fe:/debian/ppa.yaml>`_
and `Ubuntu PPA addition <https://git.linaro.org/people/senthil.kumaran/test-definitions.git/blob_plain/92406804035c450fd7f3b0ab305ab9d2c0bf94fe:/ubuntu/ppa.yaml>`_

.. note:: When a new source is added and there are no 'deps' in the
          'install' section, then it is the users responsibility to
          run 'apt-get update' before attempting an 'apt-get \*'
          operation, elsewhere in the test definition.

.. note:: When `keys` are not added for an apt source repository
          referred in `sources` section the packages may fail to
          install, if the repository is not trusted. We do not
          `--force-yes` during `apt-get` operation though we pass `-y`
          option to `apt-get`. Hence the user must add the appropriate
          `keys` in order to trust the new apt source repository that is
          added.

The principle purpose of the YAML is to run commands on the device
and these are specified in the run steps::

  run:
      steps:

.. _writing_test_commands:

Writing commands to run on the device
######################################

#. All commands need to be executables available on the device.
   This is why the metadata includes an "os" flag, so that commands
   specific to that operating system can be accessed.
#. All tests run in a dedicated working directory. If a repository is
   used, all files in the repository copy on the device will be in
   the same directory structure as the repository inside this working
   directory.
#. Avoid assumptions about the base system - if a test needs a particular
   interpreter, executable or environment, ensure that this is available
   either by using the installation step in the YAML or by building or
   installing the components as a series of commands in the run steps.
   Many images will not contain any servers or compilers, many will only
   have a limited range of interpreters installed and some of those may
   have reduced functionality.
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
#. Take care with YAML syntax. These lines will fail with wrong syntax::

    - echo "test1: pass"
    - echo test2: fail

   When this syntax will pass::

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
run step::

  run:
      steps:
          - $(./my-script.sh arguments)

You can choose whatever scripting language you prefer, as long as you
ensure that it is available in the test image.

Take care when using ``cd`` inside custom scripts - always store the
initial return value or the value of ``pwd`` before the call and change
back to that directory at the end of the script.

.. _interpreters_scripts:

Script interpreters
===================

#. **shell** - consider running the script with ``set -x`` to see the
   operation of the script in the LAVA log files. Ensure that if your
   script expects ``bash``, use the bash shebang line ``#!/bin/bash``
   and ensure that ``bash`` is installed in the test image. The default
   shell may be ``busybox``, so take care with non-POSIX constructs in
   your shell scripts if you use ``#!/bin/sh``.
#. **python** - ensure that python is installed in the test image. Add
   all the python dependencies necessary for your script.
#. **perl** - ensure that any modules required by your script are
   available, bearing in mind that some images may only have the base
   perl install or a limited selection of modules.

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
``lava-test-case`` with a test-case name (no spaces)::

  run:
      steps:
          - lava-test-case test-ls-command --shell ls /usr/bin/sort
          - lava-test-case test-ls-fail --shell ls /user/somewhere/else/

Use subshells instead of backticks to execute a command as an argument
to another command::

  - lava-test-case pointless-example --shell ls $(pwd)

For more on the contents of the YAML file and how to construct YAML
for your own tests, see the :ref:`test_developer`.

.. _parsing_output:

Parsing command outputs
***********************

If the test involves parsing the output of a command rather than simply
relying on the exit value, LAVA can use a pass/fail/skip/unknown output::

  run:
     steps:
        - echo "test1:" "pass"
        - echo "test2:" "fail"
        - echo "test3:" "skip"
        - echo "test4:" "unknown"

The quotes are required to ensure correct YAML parsing.

The parse section can supply a parser to convert the output into
test case results::

  parse:
      pattern: "(?P<test_case_id>.*-*):\\s+(?P<result>(pass|fail))"

The result of the above test would be a result bundle::

  test1 -> pass
  test2 -> fail
  test3 -> pass
  test4 -> pass

.. _recording_test_results:

Recording test case results
***************************

``lava-test-case`` can also be used with a parser with the extra
support for checking the exit value of the call::

  run:
     steps:
        - echo "test1:" "pass"
        - echo "test2:" "fail"
        - lava-test-case echo1 --shell echo "test3:" "pass"
        - lava-test-case echo2 --shell echo "test4:" "fail"

This syntax will result in extra test results::

  test1 -> pass
  test2 -> fail
  test3 -> pass
  test4 -> fail
  echo1 -> pass
  echo2 -> pass

Note that ``echo2`` **passed** because the ``echo "test4:" "fail"`` returned
an exit code of zero.

Alternatively, the ``--result`` command can be used to output the value
to be picked up by the parser::

  run:
     steps:
        - echo "test1:" "pass"
        - echo "test2:" "fail"
        - lava-test-case test5 --result pass
        - lava-test-case test6 --result fail

This syntax will result in the test results::

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

::

  run:
     steps:
        - echo "test1:" "pass"
        - echo "test2:" "fail"
        - lava-test-case test5 --result pass --measurement 99 --units bottles
        - lava-test-case test6 --result fail --measurement 0 --units mugs

This syntax will result in the test results::

  test1 -> pass
  test2 -> fail
  test5 -> pass -> 99.0000000000 bottles
  test6 -> fail -> 0E-10 mugs

The simplest way to use this with real data is to use a custom script
which runs ``lava-test-case`` with the relevant arguments.


.. _overwriting_units:

Overwriting units in existing test cases
****************************************

Each time a units is passed to the lava-test-case in this fashion
:ref:`recording_test_measurements`, the units get overwritten for the test
cases if test case with the same name already exists in system. This will cause
all previous test results to have the updated units string. To counteract this,
you can set the units manually on the test result details page. Setting this
unit manually will raise a warning, since this affects all the other test
results in the system.

.. _best_practices:

Best practices for writing a LAVA job
#####################################

A LAVA job can consist of several LAVA test definitions and multiple
deployments but this flexibility needs to be balanced against the
complexity of the job and the ways to analyse the results.

Use different test definitions for different test areas
*******************************************************

Follow the standard UNIX model of *Make each program do one thing well*
by making a set of test definitions, each of which tests one area of
functionality and tests that one area thoroughly.

Use different jobs for different test environments
**************************************************

Whilst it is supported to reboot from one distribution and boot into a
different one, the usefulness of this is limited because if the first
environment fails, the subsequent tests might not run at all.

Use a limited number of test definitions per job
************************************************

Whilst LAVA tries to ensure that all tests are run, endlessly adding
test repositories to a single LAVA job only increases the risk that
one test will fail in a way that prevents the results from all tests
being collected.

Overly long sets of test definitions also increase the complexity of
the log files which can make it hard to identify why a particular job
failed.

Splitting a large job into smaller chunks also means that the device can
run other jobs for other users in between the smaller jobs.
