.. index:: writing test - Lava-Test Test definition 1.0

.. _writing_tests_1_0:

Writing a Lava-Test Test Definition 1.0
#######################################

.. note:: A Lava Test Shell Definition is distinct from a test job
   definition, although both use YAML. Typically, the test job definition
   includes URLs for one or more test shell definitions. The
   :ref:`lava_test_shell` action then executes the test shell definitions and
   reports results as part of the test job. See also :ref:`job definition
   <first_job_definition>` and :ref:`job_metadata`.

A LAVA Test Definition comprises

#. Metadata describing the test definition, used by the test writers but not
   read by LAVA.
#. The actions and parameters to set up the test(s)
#. The instructions or steps to run as part of the test(s)

For certain tests, the instructions can be included inline with the actions.
For more complex tests or to share test definitions across multiple devices,
environments and purposes, the test can use a repository of YAML files.

.. seealso:: :ref:`test_repos` and :ref:`test_definition_kmsg`.

.. _test_definition_yaml:

Writing a test definition YAML file
***********************************

Metadata
========

The YAML is downloaded from the repository (or handled inline) and installed
into the test image, either as a single file or as part of a git repository.
(See :ref:`test_repos`)

Each test definition YAML file contains metadata and instructions.
Metadata includes:

#. A format string recognized by LAVA
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

If the file is not under version control (i.e. not in a git repository),
the **version** of the file must also be specified in the metadata:

.. code-block:: yaml

  metadata:
      format: Lava-Test Test Definition 1.0
      name: singlenode-advanced
      description: "Advanced (level 3): single node test commands for Linux Linaro ubuntu Images"
      version: "1.0"

Optional metadata
-----------------

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

These fields are ignored by LAVA itself; they exist only for test
writers to use for their own requirements.

Deprecated installation commands
================================

.. warning:: The ``install`` element of Lava-Test Test Definition 1.0
   is **DEPRECATED**. See :ref:`test_definition_portability`. Newly
   written Lava-Test Test Definition 1.0 files should not use
   ``install``.

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

When an external PPA or package repository (specific to debian based distributions)
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
          - lavacli

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

Download or view the complete example:
`examples/test-jobs/inline-test-definition-example.yaml
<examples/test-jobs/inline-test-definition-example.yaml>`_

.. index:: terminology - test writer

.. _portability_terminology:

Terminology reference
*********************

.. _lava_test_job:

LAVA Test Job
=============

The test job provides test shell definitions (and inline definitions), as well
as describing the steps needed to deploy code and boot a device to a command
prompt. These steps will not be portable between devices or operating system
deployments.

This design is quite different from LAVA V1 because V1 used to perform *magic*
implicit steps. In V2 test jobs need to be explicit about all steps required.

Inline definitions are often used for prototyping test definitions. They are
also the recommended choice for MultiNode synchronization primitives, inserted
between the other LAVA Test Shell Definitions which do the bulk of the work.

The test job definition is what is submitted to LAVA to generate a test job.

.. _lava_test_shell_definition:

LAVA Test Shell Definition
==========================

The LAVA Test Shell Definition is a YAML file, normally stored in a git
repository alongside test writer scripts. Again, this will normally not be
portable between operating system deployments.

It is possible to use different scripts, with the test job selecting which
scripts to use for a particular deployment as it runs.

Each line in the definition must be a single line of shell, with no redirects,
functions or pipes. Ideally, the Lava-Test Test Definition 1.0 will consist of a
single ``run`` step which simply calls the appropriate test writer script.

.. _lava_test_helpers:

LAVA Test Helpers
=================

The LAVA Test Helpers are scripts maintained in the LAVA codebase, like
``lava-test-case``. These are designed to work using only the barest
minimum of operating system support, to make them portable to all deployments.
Where necessary they will use ``deployment_data`` to customize content.

The helpers have two main uses:

* to embed information from LAVA into the test shell and

* to support communication with LAVA during test jobs.

Some helpers will always be required, for example to locate and start the test
shell scripts.

Helpers which are too closely tied to any one operating system are likely to
be deprecated and removed after LAVA V1 is dropped, along with helpers which
duplicate standard operating system support.

For example, helpers which use distribution-specific utilities to install
packages or add repositories.

Supporting OS variants
----------------------

Most test shells can support portable test scripts without changes to the
defaults.

* ``lava_test_sh_cmd`` specifies the location of the shell interpreter.
  Default: ``/bin/sh``

* ``lava_test_results_dir`` specifies the location of the LAVA test directory
  which includes ``lava-test-runner``. If this directory does not exist,
  the test shell will not start. Default: ``'/lava-%s'``

* ``lava_test_shell_file`` specifies the file to append with any
  :ref:`dispatcher_environment`. Note: this is not the same as the :ref:`LAVA
  params support <yaml_parameters>`. Default: ``'~/.bashrc'``

These values can be overridden in the :term:`job context` if the test job
deploys a non-standard system as long as none of the deployments specify the
``os``.

.. _test_writer_scripts:

Test Writer Scripts
===================

Test writer scripts are scripts written by test writers, designed to be run
both by LAVA and by developers. They do not need to be portable to different
operating system deployments, as the choice of script to run is up to the
developer or test writer. This means that the test writer has a free choice of
languages, methods and tools in these scripts - whatever is available within
the particular operating system deployment. This can even include building
custom tools from source if so desired.

The key feature of these scripts is that they should **not** depend on any
LAVA features or helpers for their basic functionality. That way, developers
can run exactly the same scripts both inside and outside of LAVA, to help
reproduce problems.

When running inside LAVA, scripts should check for the presence of
``lava-test-case`` in the PATH environment variable and behave accordingly,
using ``lava-test-case`` to report results to LAVA if it is available.
Otherwise, report results to the user in whatever way makes most sense.

Test writers are strongly encouraged to make their scripts verbose: add
progress messages, debug statements, error handling, logging and other
support to allow developers to see what is actually happening when a test is
running. This will aid debugging greatly.

Finally, scripts are commonly shared amongst test writers. It is a good idea
to keep them self-contained as much as possible, as this will aid reuse.
Also, try to stick to the common Unix model: one script doing one task.

.. seealso:: The next section on :ref:`custom_scripts`.

.. _custom_scripts:

Writing custom scripts to support tests
***************************************

.. note:: Custom scripts are not available in an :term:`inline` definition,
   *unless* the definition itself downloads the script, adds any
   dependencies and makes the script executable.

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

https://git.linaro.org/lava-team/refactoring.git/tree/functional/dispatcher-unittests.sh

The script is simply called directly from the test shell definition:

https://git.linaro.org/lava-team/refactoring.git/tree/functional/server-unit-tests-stretch.yaml

Example V2 job using this support:

https://git.linaro.org/lava-team/refactoring.git/tree/functional/server-jessie-stretch-debian.yaml

.. note:: Make sure that your custom scripts output some useful information,
   including some indication of progress, in all test jobs but control the
   total amount of output to make the logs easier to read.

Advantages of custom scripts
============================

.. seealso:: :ref:`test_definition_portability`

Detailed knowledge of the output
--------------------------------

Custom scripts can be written to take advantage of detailed knowledge
of the expected output and the test environment. They don't have to be
generic (i.e. they can be specifically targeted to one test
suite). They can use a variety of tools or programming language
support to parse the test output.

Increased portability
---------------------

Custom scripts can also allow test writers to make the Test Shell
Definition more portable, to be run outside LAVA. It is recommended
to do this wherever possible and not rely on LAVA-specific helper
scripts. This allows developers who do not have access to the test
framework to reproduce bugs found by the test framework whilst
retaining the benefits of scripts which are specific to particular
test output styles.

Problem reports can be difficult for developers to debug if they
cannot reproduce the bug manually, without using the complete CI
system. Every effort should be made to support running the test action
instructions on a DUT which has been manually deployed so that
developers can add specialized debug tools and equipment which are not
available within the CI.

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
   python dependencies necessary for your script. Remember that Python2 is
   end-of-life and ``python3-`` alternative dependencies may be required.

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

.. seealso:: :ref:`best_practices`, :ref:`custom_scripts` and
   :ref:`test_writer_scripts` for recommended ways to use this in practice.

Use subshells instead of backticks to execute a command as an argument to
another command:

.. code-block:: yaml

  - lava-test-case pointless-example --shell ls $(pwd)

For more details on the contents of the YAML file and how to construct YAML for
your own tests, see the :ref:`test_developer`.

.. _recording_test_results:

Recording test case results
***************************

``lava-test-case`` can also be used with a parser with the extra support for
checking the exit value of the call:

.. code-block:: yaml

  run:
     steps:
      - "lava-test-case fail-test --shell false"
      - "lava-test-case pass-test --shell true"

This syntax will result in extra test results:

.. code-block:: yaml

  fail-test -> fail
  pass-test -> pass

Alternatively, the ``--result`` command can be used to output the
result directly:

.. code-block:: yaml

  run:
     steps:
        - lava-test-case test5 --result pass
        - lava-test-case test6 --result fail

This syntax will result in the test results:

.. code-block:: yaml

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
        - lava-test-case test5 --result pass --measurement 99 --units bottles
        - lava-test-case test6 --result fail --measurement 0 --units mugs

This syntax will result in the test results:

.. code-block:: yaml

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

``lava-test-reference`` has similar support as ``lava-test-case`` except that
``--measurement`` and ``--unit`` options are **not** supported.

.. note:: Unlike the metadata in the test shell definition itself, the reference URL,
          result and the test case name are stored as part of the job metadata in
          the test job results. See also :ref:`job_metadata`.

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

.. index:: lava-target-ip, lava-target-mac, lava-target-storage

.. _test_device_info:

Obtaining information about the device
**************************************

.. seealso:: :ref:`device_dictionary_exported_parameters` for details of how
   this support is described in the device dictionary.

Some elements of the static device configuration are exposed to the test shell,
where it is safe to do so and where the admin has explicitly configured the
information. The information is exposed using test shell helpers which
currently include:

* ``lava-target-ip`` - Devices with a fixed IPv4 address will populate this
  field. Test writers are able to use this in an LXC to connect to the device,
  providing that the test shell has correctly raised a network connection and
  suitable services are configured and running on the device::

   ping -c4 $(lava-target-ip)

* ``lava-target-mac`` - An alternative to ``lava-target-ip``, declaring the
  MAC address of the device. Depending on the use case, this may be useful to
  lookup the IP address of the device::

   echo `lava-target-mac`

* ``lava-target-storage`` - Where devices have alternative storage media
  fitted, the id of the block device can be exported. For example, this can
  help provide temporary storage on the device when the test shell is running
  a ramdisk or NFS. Some devices may provide a USB mass storage device which
  could also be exported in this way.

  .. note:: This provision is designed to support temporary storage on devices
     which typically boot over NFS or ramdisk etc. It is intended to allow test
     writers to run operations which would typically fail without a local
     filesystem or would block network traffic such that NFS would time out.

  Only a **single** block device is supported per method. The ``method`` itself
  is simply a label specified by the admin. Often it will relate to the interface
  used by the block device, e.g. ``SATA`` or ``USB`` but it could be any string.
  In the example below, ``UMS`` is the label used by the device (as an
  abbreviation for USB Mass Storage).

  .. seealso:: :ref:`extra_device_configuration` and :ref:`persistence` -
     test writers are responsible for handling persistence issues. The
     recommendation is that a new filesystem is created on the block device
     each time it is to be used.

  The output format contains one line per device, and each line contains
  the method and the ID for the storage using that method, separated
  by a TAB character::

    $ lava-target-storage
    UMS     /dev/disk/by-id/usb-Linux_UMS_disk_0_WaRP7-0xac2400d300000054-0:0
    SATA    /dev/disk/by-id/ata-ST500DM002-1BD142_W3T79GCW

  Usage: ``lava-target-storage method``

  The output format contains one line per device assigned to the specified
  ID, with no whitespace. The matched method is not output.::

    $ lava-target-storage UMS
    /dev/disk/by-id/usb-Linux_UMS_disk_0_WaRP7-0xac2400d300000054-0:0

  If there is no matching method, exit non-zero and output nothing.

.. seealso:: :ref:`Exporting information into the test shell from the device
   dictionary <device_dictionary_exported_parameters>`

.. _test_attach:

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
     path: lava-test-shell/smoke-tests-basic.yaml
     repository: git://git.linaro.org/lava-team/lava-functional-tests.git
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

.. seealso:: :ref:`best_practices`, :ref:`custom_scripts` and
   :ref:`test_writer_scripts` for recommended ways to use this in practice.

.. index:: test shell - best practices, best practice

.. _best_practices:

Best practices for writing a LAVA test job
##########################################

A test job may consist of several LAVA test definitions and multiple
deployments, but this flexibility needs to be balanced against the complexity
of the job and the ways to analyze the results.

As with all things in automation, the core principles of best practice
can be summarized as:

#. Start small

#. Build slowly

#. Change only one thing at a time

#. Test every change

.. index:: test shell - portability

.. _test_definition_portability:

Write portable test definitions
*******************************

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

**Avoid using test definitions patterns**

Test definitions which can use ``lava-test-case`` should not also use
test definition patterns like:

.. code-block:: python

 "(?P<test_case_id>.*-*):\\s+(?P<result>(pass|fail))"

Test shell definition patterns are difficult to debug and almost
impossible to make portable. If you have access to ``lava-test-case``,
there is no need to also use a pattern because you already have a shell
on the DUT which is capable of much better pattern matching and
parsing. Start by copying the relevant part of the test output and see
how parsing can be improved:

* Is any kind of pattern needed at all? Can the process generating the
  output be called by a script which already understands the output?

* If you do need a pattern, put the pattern handling inside the test
  shell definition scripts and use copies of different sections of
  output to debug the pattern matching before submitting anything to
  LAVA.

.. note:: If the DUT does not support a POSIX shell then
   ``lava-test-case`` will not be available either. In some cases, the
   test operation is executed from an LXC and this will provide the
   necessary shell support.

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

.. seealso:: :ref:`custom_scripts` and :ref:`portability_terminology`

.. _less_reliance_on_install:

Rely less on install: steps
***************************

To make your test portable, the goal of the ``install`` block of any test
definition should be to get the raw LAVA environment up to the point where a
developer would be ready to start test-specific operations. For example,
installing package dependencies. Putting the operations into the ``run:`` steps
also means that the test writer can report results from these operations.

Whilst compatibility with V1 has been retained in most areas of the test shell,
there can be differences in how the install steps behave between V1 and V2.
Once V1 is removed, other changes are planned for the test shell to make it
easier for test writers to create portable tests. It is possible that the
``install:`` behavior of the test shell could be restricted at this time.

Consider moving ``install: git-repos:`` into a run step or directly into a
:ref:`custom_script <custom_scripts>` along with the other setup (for example,
switching branches or compiling the source tree). Then, when debugging the test
job, a test writer can setup a similar environment and simply call exactly the
same script.

.. _best_practice_one_thing:

Use different test definitions for different test areas
*******************************************************

Follow the standard UNIX model of *Make each program do one thing well*. Make a
set of separate test definitions. Each definition should concentrate on one
area of functionality and test that one area thoroughly.

Use different jobs for different test environments
**************************************************

While it is supported to reboot from one distribution and boot into a different
one, the usefulness of this is limited. If the first environment fails, the
subsequent tests might not run at all.

Use a limited number of test definitions per job
************************************************

While LAVA tries to ensure that all tests are run, adding more and more test
repositories to a single LAVA job increases the risk that one test will fail in
a way that prevents the results from all tests being collected.

Overly long sets of test definitions also increase the complexity of the log
files, which can make it hard to identify why a particular job failed.

Splitting a large job into smaller chunks also means that the device can run
other jobs for other users in between the smaller jobs.

Retain at least some debug output in the final test definitions
***************************************************************

Information about which commit or version of any third-party code is
and will remain useful when debugging failures. When cloning such code,
call a script in the code or use the version control tools to output
information about the cloned copy. You may want to include the most
recent commit message or the current commit hash or version control tag
or branch name.

If an item of configuration is important to how the test operates,
write a test case or a custom script which reports this information.
Even if this only exists in the test job log output, it will still be
useful when comparing the log files of other similar jobs.

Mock up the device output to test the scripts
*********************************************

Avoid waiting for a device to deploy and boot for each iteration in the
development of test support scripts. Copy the output of a working
device and use that as the input to the scripts which process the logs
to identify results and cut out the noise.

Where possible, include such mock ups as tests which can be run in
another CI process, triggered each time the scripts are modified.

Use functional tests to validate common functionality
*****************************************************

Use the principles of :ref:`functional_testing` to test common code
used by the test jobs. For example, if a shell library is used, ensure
that your smoke tests definitions are changed to use the shell library
so that all health checks and functional tests provide test coverage
for the shell library.

.. index:: test shell - check for support

.. _best_practice_check_support:

Check for specific support as a test case
*****************************************

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

.. index:: test shell - side effects

.. _custom_script_side_effects:

Check custom scripts for side-effects
*************************************

Subtle bugs can be introduced in custom scripts, so it is important to
make the scripts :ref:`portable <test_definition_portability>` so that
bugs can be reproduced outside LAVA.

When interacting directly with LAVA, for example calling
``lava-test-case``, it is possible to introduce control flow bugs.
These can cause the output of ``lava-test-case`` to be received
**after** the end of a test run and this can generate TestError
exceptions. This section covers one example when using Python, there
may be others.

This example checks for ``lava-test-case`` in ``$PATH`` to determine
whether to use the LAVA helpers.

.. code-block:: python

    import os
    import subprocess


    def _which_check(path, match):
        """
        Simple replacement for the `which` command found on
        Debian based systems. Allows ordinary users to query
        the PATH used at runtime.
        """
        paths = os.environ['PATH'].split(':')
        if os.getuid() != 0:
            # avoid sudo - it may ask for a password on developer systems.
            paths.extend(['/usr/local/sbin', '/usr/sbin', '/sbin'])
        for dirname in paths:
            candidate = os.path.join(dirname, path)
            if match(candidate):
                return candidate
        return None


    if _which_check(path='lava-test-case', match=os.path.isfile):
        subprocess.Popen([
             'lava-test-case', 'probe-results', '--result', 'pass',
             '--measurement', str(average), '--units', 'volts'])

The error is in this line:

.. code-block:: python

        subprocess.Popen([

``Popen`` calls ``fork`` but returns immediately. Unless the script
also calls ``wait``, then the output of the subprocess can occur after
the above function has returned. It is easy for this to happen at the
end of a test definition, leading to intermittent bugs where some tests
fail.

The solution is to use the existing ``subprocess`` functions which
already use ``wait`` internally. For ``lava-test-case``, this would be
``check_call`` which waits for the process to execute and checks the
return value.

The fixed example looks like:

.. code-block:: python

    import os
    import subprocess


    def _which_check(path, match):
        """
        Simple replacement for the `which` command found on
        Debian based systems. Allows ordinary users to query
        the PATH used at runtime.
        """
        paths = os.environ['PATH'].split(':')
        if os.getuid() != 0:
            # avoid sudo - it may ask for a password on developer systems.
            paths.extend(['/usr/local/sbin', '/usr/sbin', '/sbin'])
        for dirname in paths:
            candidate = os.path.join(dirname, path)
            if match(candidate):
                return candidate
        return None


    if _which_check(path='lava-test-case', match=os.path.isfile):
        subprocess.check_call([
             'lava-test-case', 'probe-results', '--result', 'pass',
             '--measurement', str(average), '--units', 'volts'])

.. index:: lava-test-raise, setup commands, test shell - setup

.. _call_test_raise:

Call lava-test-raise if setup fails
***********************************

Most test jobs have setup routines which ensure that dependencies
are available or that the directory layout is correct etc. In most
cases, these routines are called early and a failure in the setup
function would undermine all subsequent test operations.

The return code of some operations can be used to trigger an early
failure.

.. _setup_inline:

Inline
======

If you are using an inline definition, the syntax can be a bit awkward:

.. code-block:: yaml

  run:
     steps:
         - apt-get update -q && lava-test-case "apt-update" --result pass || lava-test-raise "apt-update"

An alternative is to put the definition into a file on a remote
fileserver, use ``wget`` to download it and then execute it:

.. code-block:: yaml

        run:
          steps:
            - apt -y install wget
            - wget http://people.linaro.org/~neil.williams/setup-test.sh
            - sh -x setup-test.sh

.. caution:: The download step is itself a setup command and could
  fail, so whilst this is useful in development, using scripts from a
  git repository is preferable.

.. _setup_repository:

Using a repository
==================

Shell library
-------------

A local shell library and a shell script can be easily used from a test
shell repository:

.. code-block:: shell

    # saved, committed and pushed as ./testdefs/lava-common

    command(){
        if [ -n "$(which lava-test-case || true)" ]; then
            echo $2
            $2 && lava-test-case "$1" --result pass || lava-test-raise "$1"
        else
            echo $2
            $2
        fi
    }

This snippet is also :ref:`portable <test_definition_portability>`
because if ``lava-test-case`` is not in the ``$PATH``, the setup
command is executed without needing ``lava-test-case`` or
``lava-test-raise``. The calling script is responsible for handling the
return code, typically by using ``set -e``.

The above snippet is just an example to show the principle. The
function itself continues to develop as ``lava-common`` - a small shell
library which also supports a ``testcase`` function which reports a
failed test case instead of ``lava-test-raise``. Use ``testcase`` for
non-fatal checks and ``command`` for fatal checks.

.. code-block:: shell

    command(){
        # setup command - will abort the test job upon failure.
        # expects two quoted arguments
        # $1 - valid lava test case name (no spaces)
        # $2 - the full command line to execute
        # Note: avoid trying to set environment variables.
        # use an explicit export.
        CMD=""
        PREFIX=$1
        shift
        while [ "$1" != "" ]; do
          CMD="${CMD} $1" && shift;
        done;
        if [ -n "$(which lava-test-case || true)" ]; then
            echo "${CMD}"
            $CMD && lava-test-case "${PREFIX}" --result pass || lava-test-raise "${PREFIX}"
        else
            echo "${CMD}"
            $CMD
        fi
    }


.. seealso:: https://git.lavasoftware.org/lava/functional-tests/blob/master/testdefs/lava-common

Calling shell script
--------------------

.. code-block:: shell

 #!/bin/sh

 # saved, committed and pushed as ./testdefs/local-run.sh

 . ./lava-common

 command 'setup-apt' "apt-get update -q"

If the shell script is saved to a different directory, the path to
the shell library will have to be updated.

.. seealso:: :ref:`setup_custom_scripts` - the language used for these
   scripts is entirely up to the test writer to choose. Remember that
   some language interpreters will themselves need to be installed
   before scripts can be executed, requiring an initial setup shell script.
   That does not mean that all setup needs to be done in shell; there
   are key advantages to using other languages, including test writer
   familiarity and ease of triage.

Test shell definition
---------------------

Execute using a Lava Test Shell Definition:

.. code-block:: yaml

  run:
      steps:
        ./testdefs/local-run.sh


.. seealso:: :ref:`Deploying to recovery <deploy_to_recovery>`

.. index:: test shell - custom scripts

.. _setup_custom_scripts:

Custom scripts
==============

Custom scripts should check the return code of setup operations and use
``lava-test-raise`` to halt the test job immediately if a setup error
occurs. This makes triage much easier as it puts the failure much
closer to the actual cause within the log file.

.. code-block:: python

    import os
    import subprocess


    def _which_check(path, match):
        """
        Simple replacement for the `which` command found on
        Debian based systems. Allows ordinary users to query
        the PATH used at runtime.
        """
        paths = os.environ['PATH'].split(':')
        if os.getuid() != 0:
            # avoid sudo - it may ask for a password on developer systems.
            paths.extend(['/usr/local/sbin', '/usr/sbin', '/sbin'])
        for dirname in paths:
            candidate = os.path.join(dirname, path)
            if match(candidate):
                return candidate
        return None


    values = []
    # other processing populates the values list
    if not values:
        if _which_check(path='lava-test-raise', match=os.path.isfile):
            subprocess.check_call(['lava-test-raise', 'setup failed'])
        else:
            print("setup failed")
        return 1

Example of lava-test-raise
==========================

This is an example of using lava-test-raise from a python custom script

https://staging.validation.linaro.org/scheduler/job/246700/definition

https://git.lavasoftware.org/lava/functional-tests/blob/master/testdefs/arm-probe.yaml

https://git.lavasoftware.org/lava/functional-tests/blob/master/testdefs/aep-parse-output.py

.. index:: test shell - control output

.. _controlling_tool_output:

Control the amount of output from scripts and tools
***************************************************

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
==============

Progress bars, in general, are a particular problem. Instead of overwriting a
single line of output, every iteration of the bar creates a complete new line
over the serial connection and in the logs. Wherever possible, disable the
progress bar behavior of all operations.

* **apt** - When calling ``apt update`` or ``apt-get update``, **always** use
  the ``-q`` option to avoid filling the log file with repeated progress output
  during downloads. This option still gives output but formats it in a way that
  is much more useful when reading log files compared to an interactive
  terminal.

* **wget** - **always** use the ``-S --progress=dot:giga`` options for
  downloads as this reduces the total amount of progress information during the
  operation.

* **git clone** - consider using ``-q`` on git clone operations to silence the
  progress bars.

.. _large_output_issues:

Problems with output
====================

LAVA uses ``pexpect`` to monitor the output over the serial connection for
patterns which are used to pick up test cases and other test shell support.
Each time a match is found, the buffer is cleared. If there is a lot of output
with no pattern matches, the processing can slow down.

By default ``pexpect`` uses a buffer of 2000 bytes for the input used
for pattern matches. In order to improve performance, LAVA uses a limit
of 4092 bytes. This is intended to limit problems with processing
slowing down but best practice remains to manage the test job output to
make the logs more useful during later triage.

Large log files also have a few implications for the user interface and triage.
More content makes loading links to a test job take longer and finding the
right line to make that link becomes more and more difficult. Eventually, very
large log files can be disabled by the admin, so that the log file can only be
downloaded.

.. seealso:: :ref:`log_size_limit`

The size of the log output needs to be balanced against the need to have enough
information in the logs to be able to triage the test successfully.

Although the total size of the test job log file is important, there can also
be issues when a smaller log file contains large sections where none of the
patterns match and this can cause the test to run more slowly.

.. important:: It is **only** the content sent over the serial connection which
   needs to be managed. Redirecting to files will be unaffected, subject to
   filesystem performance on the DUT or LXC. However, remember that at least
   some of the content of such files will be useful in triage or contain
   results directly. Therefore, it is important to manage the output of test
   operations to achieve the balance of sufficient information for triage and
   avoiding a flood of too much information causing performance issues.

   Very large amounts of output can also be :ref:`published
   <publishing_artifacts>` for later analysis, e.g. if the original output is
   redirected to a file. Consider using ``tee`` here (or similar functionality)
   to retain some output into the logs because if the test operation fails
   early for any reason, the file might not be uploaded at all.

When performance is important, for example benchmarking, use a wrapper script
to optimize your test shell output.

* If a progress bar is used and cannot be turned off without losing other
  useful content, wrap the output of the command in a script which omits the
  lines generated by the progress bar. Check existing test logs for example
  lines and print all the other lines. Avoid the simplistic approach of
  redirecting to ``/dev/null``.

  For a progress bar which outputs lines looking like: ``[ 98%]
  /data/art-test/arm64/core.oat: 95%``

  Use something like this:

  .. code-block:: python

    #!/usr/bin/env python

    import fileinput

    def main(args):
        for line in fileinput.input('-'):
            line = line.strip()
            if line.startswith('[') and line.endswith('%'):
                continue
            print(line)
        return 0

    if __name__ == '__main__':
        import sys
        sys.exit(main(sys.argv))

  Adapted from https://git.linaro.org/lava-team/refactoring.git/tree/functional/unittests.py

  The same script can be used to drop other noise from the output.

* Add LAVA Test Cases - avoid the habit of reporting results at the very end of
  a test operation or (worse) test job. This risks getting no results at all
  when things go wrong, as well as creating large amounts of output without any
  pattern matches. Most tests run many small test operations, it can be helpful
  to have records of which tests completed. Remember that a :term:`test set`
  can be used to identify groups of test cases, isolating them from later test
  cases.

  Example: :ref:`less_reliance_on_install` means that after all of the output
  of installing dependencies, a lava-test-case should be reported that the
  dependencies installed correctly which also clears the buffer of the extra
  output.

  Example: If the test operation involves iterations over a test condition,
  report a lava test case every few iterations.

.. _too_many_test_cases:

Control the number of test cases reported
*****************************************

Creating a lava-test-case involves a database operation on the master. LAVA
tries to optimize these calls to allow test jobs to report several tens of
thousands of test cases per test job, including supporting streaming of test
cases exported through the API. However, there will always be a practical limit
to the total number of test cases per test job.

Groups of test cases should be separated into :term:`test sets <test set>` and
then into test suites (by using separate LAVA Test Shell Definition paths) to
make it easier to find the relevant test case.

When writing the test shell definition, always try to report results on-the-fly
instead of waiting until the test operation has written all the data to a file.
This insulates you from early failures where the file is not written or cannot
be parsed after being written. Wrapper scripts can be used to report LAVA test
cases during the creation of the file.

.. seealso:: https://git.linaro.org/lava-team/refactoring.git/tree/functional/unittests.py
