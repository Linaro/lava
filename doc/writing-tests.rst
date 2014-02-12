.. _writing_tests:

Writing a LAVA test definition
##############################

A LAVA Test Definition comprises of two parts:

#. the data to setup the test, expressed as a JSON file.
#. the instructions to run inside the test, expressed as a YAML file.

This allows the same tests to be easily migrated to a range of different
devices, environments and purposes by using the same YAML files in
multiple JSON files. It also allows tests to be built from a range of
components by aggregating YAML files inside a single JSON file.

.. _json_contents:

Contents of the JSON file
*************************

The JSON file is submitted to the LAVA server and contains:

#. Demarcation as a :term:`health check` or a user test.
#. The default timeout of each action within the test.
#. The :term:`logging level` for the test, DEBUG or INFO.
#. The name of the test, shown in the list of jobs.
#. The location of all support files.
#. All parameters necessary to use the support files.
#. The declaration of which device(s) to use for the test.
#. The location to which the results should be uploaded.

The JSON determines how the test is deployed onto the device and
where to find the tests to be run. 

All user tests should use::

    "health_check": false,

See :ref:`health_checks`.

Multiple tests can be defined in a single JSON file by listing multiple
locations of YAML files. Each set of instructions in the YAML files can
be run with or without a reboot between each set.

If a test needs to use more than one device, it is the JSON file which 
determines which other devices are available within the test and how
the test(s) are deployed to the devices in the group.

Support files
=============

These include:

#. Files to boot the device: Root filesystem images, kernel images,
   device tree blobs, bootloader parameters
#. Files containing the tests: The YAML files, either alone or as part
   of a repository, are added to the test by LAVA.

.. expand this section to go through each way of specifying support
   files by summaries with links to full sections.

Using local files
------------------

Support files do not need to be at remote locations, all files specified
in the JSON can be local to the :term:`dispatcher` executing the test. This
is useful for local tests on your own LAVA instance, simply ensure that
you use the ``file://`` protocol for support files. Note that a local
YAML file will still need to download any custom scripts and required
packages from a remote location.

.. _initial_json_actions:

Initial actions in the JSON
===========================

The simplest tests involve using a pre-built image, a test definition
and submission of the results to the server.

Actions defined in the JSON will be executed in the order specified
in the JSON file, so a deployment is typically followed by a
test shell and then submission of results.

#. **deploy_linaro_image** : Download a complete image (usually but not
   necessarily compressed) containing the kernel, kernel modules and
   root filesystem. The LAVA overlay will be applied on top before the
   image boots, to provide access to the LAVA test tools and the test
   definitions defined in the subsequent ``actions``.
#. **lava_test_shell** : Boots the deployed image and starts the
   ``lava_test_runner`` which starts the execution of the commands
   defined in the YAML.
#. **submit_results_on_host** : (Equivalent to **submit_results**)
   Collects the result data from the image after the completion of
   all the commands in the YAML and submits a bundle containing the
   results and metadata about the job to the server, to be added to
   the :term:`bundle stream` listed in the submission. These result bundles can then
   be viewed, downloaded and used in filters and reports.

See :ref:`available_actions`

.. _basic_json:

Basic JSON file
===============

Your first LAVA test should use DEBUG logging so that it is easier
to see what is happening.

See :ref:`timeouts` for detailed information on how LAVA handles the
timeouts. A suitable example for your first tests is 900 seconds.

Make the ``job_name`` descriptive and explanatory, you will want to be
able to tell which job is which when reviewing the results.

Make sure the :term:`device type` matches exactly with one of the suitable
device types listed on the server to which you want to submit this job.

Change the :term:`stream` to one to which you are allowed to upload results,
on your chosen server. If you use ``localhost``, note that this will
be replaced by the fully qualified domain name of the server to which
the job is submitted.

::

 {
    "health_check": false,
    "logging_level": "DEBUG",
    "timeout": 900,
    "job_name": "kvm-basic-test",
    "device_type": "kvm",
    "actions": [
        {
            "command": "deploy_linaro_image",
            "parameters": {
                "image": "http://images.validation.linaro.org/kvm-debian-wheezy.img.gz"
            }
        },
        {
            "command": "lava_test_shell",
            "parameters": {
                "testdef_repos": [
                    {
                        "git-repo": "git://git.linaro.org/qa/test-definitions.git",
                        "testdef": "ubuntu/smoke-tests-basic.yaml"
                    }
                ],
                "timeout": 900
            }
        },
        {
            "command": "submit_results_on_host",
            "parameters": {
                "stream": "/anonymous/example/",
                "server": "http://localhost/RPC2/"
            }
        }
    ]
 }

.. note:: Always check your JSON syntax. A useful site for this is
          http://jsonlint.com.

For more on the contents of the JSON file and how to construct JSON
for devices known to LAVA or devices new to LAVA, see the
:ref:`test_developer`.

.. _yaml_contents:

Contents of the YAML file
*************************

The YAML is downloaded from the location specified in the JSON and
installed into the test image, either as a single file or as part of
a git or bzr repository. (See :ref:`test_repos`)

Each YAML file contains metadata and instructions. Metadata includes:

#. A format string recognised by LAVA
#. A short name of the purpose of the file
#. A description of the instructions contained in the file.

::

  metadata:
      format: Lava-Test Test Definition 1.0
      name: singlenode-advanced
      description: "Advanced (level 3): single node test commands for Linux Linaro ubuntu Images"

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
the log files and the result bundles, making it hard to identify why
a particular job failed.

LAVA supports filters and image reports to combine result bundles into
a single analysis.

LAVA also support retrieving individual result bundles using ``lava-tool``
so that the bundles can be aggregated outside LAVA for whatever tests
and export the script writer chooses to use.

Splitting a large job into smaller chunks also means that the device can
run other jobs for other users in between the smaller jobs.

Minimise the number of reboots within a single test
***************************************************

In many cases, if a test definition needs to be isolated from another
test case by a reboot (to prevent data pollution etc.) it is likely that
the tests can be split into different LAVA jobs.

To run two test definitions without a reboot, simply combine the JSON
to not use two ``lava_test_shell`` commands::

        {
            "command": "lava_test_shell",
            "parameters": {
                "testdef_repos": [
                    {
                        "git-repo": "git://git.linaro.org/qa/test-definitions.git",
                        "testdef": "ubuntu/smoke-tests-basic.yaml"
                    }
                ],
                "timeout": 900
            }
        },
        {
            "command": "lava_test_shell",
            "parameters": {
                "testdef_repos": [
                    {
                        "git-repo": "http://git.linaro.org/git-ro/people/neil.williams/temp-functional-tests.git",
                        "testdef": "singlenode/singlenode01.yaml"
                    }
                ],
                "timeout": 900
            }
        }

Becomes::

        {
            "command": "lava_test_shell",
            "parameters": {
                "testdef_repos": [
                    {
                        "git-repo": "git://git.linaro.org/qa/test-definitions.git",
                        "testdef": "ubuntu/smoke-tests-basic.yaml"
                    },
                    {
                        "git-repo": "http://git.linaro.org/git-ro/people/neil.williams/temp-functional-tests.git",
                        "testdef": "singlenode/singlenode01.yaml"
                    }
                ],
                "timeout": 900
            }
        },
