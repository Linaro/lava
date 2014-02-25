.. _lava_test_shell:

LAVA Test Shell
***************

The ``lava_test_shell`` action provides a way to employ a more black-box style
testing appoach with the target device. The test definition format is quite
flexible and allows for some interesting things.

Quick start
===========

A minimal test definition looks like this::

  metadata:
    name: passfail
    format: "Lava-Test-Shell Test Definition 1.0"
    description: "A simple passfail test for demo."
    os:
      - ubuntu
      - openembedded
    devices:
      - origen
      - panda
    environment:
      - lava-test-shell

  params:
    TEST_1: pass

  run:
    steps:
      - echo "test-1: $TEST_1"
      - echo "test-2: fail"

  parse:
    pattern: "(?P<test_case_id>.*-*):\\s+(?P<result>(pass|fail))"

**NOTE:** The parse pattern has similar quoting rules as Python, so
\\s must be escaped as \\\\s and similar.

However, the parameters such as os, devices, environment are optional in
the metadata section. On the other hand parameters such as name, format,
description are mandatory in the metadata section.

If your test definition is not part of a bzr or git repository then it
is mandatory to have a 'version' parameter in metadata section. The
following example shows how a test definition metadata section will
look like for a test definition which is not part of bzr or git
repository::

  metadata:
    name: passfail
    format: "Lava-Test-Shell Test Definition 1.0"
    version: "1.0"
    description: "A simple passfail test for demo."
    os:
      - ubuntu
      - openembedded
    devices:
      - origen
      - panda
    environment:
      - lava-test-shell

**NOTE:** Only if the test definition is referred from a URL the
version parameter should be explicit.

A lava-test-shell is run by:

* "compiling" the above test defintion into a shell script.

  - Note that this shell script will have a ``set -x`` at the top, so a
    failing step will abort the entire test run. If you need to specify
    a step that might fail, but should not cause the run to be aborted,
    make sure you finish the command with ``|| true``.

* copying this script onto the device and arranging for it to be run
  when the device boots
* booting the device and letting the test run
* retrieving the output from the device and turning it into a test
  result bundle

Writing a test for lava-test-shell
==================================

For the majority of cases, the above approach is the easiest thing to
do: write shell code that outputs "test-case-id: result" for each test
case you are interested in.  This is similar to how the lava-test
parsing works, so until we get around to writing documentation here,
see
http://lava-test.readthedocs.org/en/latest/usage.html#adding-results-parsing.

The advantage of the parsing approach is that it means your test is
easy to work on independently from LAVA: simply write a script that
produces the right sort of output, and then provide a very small
amount of glue to wire it up in LAVA.  However, when you need it,
there is also a more powerful, LAVA-specific, way of writing tests.
When a test runs, ``$PATH`` is arranged so that some LAVA-specific
utilities are available:

 * ``lava-test-case``
 * ``lava-test-case-attach``
 * ``lava-test-run-attach``

You need to use ``lava-test-case`` (specifically, ``lava-test-case
--shell``) when you are working with `hooks, signals and external
measurement`_.

.. _`hooks, signals and external measurement`: external_measurement.html

lava-test-case
--------------

lava-test-case records the results of a single test case.  For example::

  steps:
    - "lava-test-case simpletestcase --result pass"

It has two forms.  One takes arguments to describe the outcome of the
test case and the other takes the shell command to run -- the exit
code of this shell command is used to produce the test result.

Both forms take the name of the testcase as the first argument.

The first form takes these additional arguments:

 * ``--result $RESULT``: $RESULT should be one of pass/fail/skip/unknown
 * ``--measurement $MEASUREMENT``: A numerical measurement associated with the test result
 * ``--units $UNITS``: The units of $MEASUREMENT

``--result`` must always be specified.  For example::

  run:
    steps:
      - "lava-test-case bottle-count --result pass --measurement 99 --units bottles"

:ref:`custom_scripts` allows preparation of LAVA results from other
sources, complete with measurements by calling ``lava-test-case``
from scripts executed in the YAML file::

 #!/usr/bin/env python

 from subprocess import call

 def main():
     call(
         ['lava-test-case',
          'bottle-count',
          '--result', 'pass',
          '--measurement', '99',
          '--units', 'bottles'])
     return 0

 if __name__ == '__main__':
     main()

The second form is indicated by the --shell argument, for example::

  run:
    steps:
      - "lava-test-case fail-test --shell false"
      - "lava-test-case pass-test --shell true"

The --shell form also sends the start test case and end test case
signals that are described in `hooks, signals and external
measurement`_.

lava-test-case-attach
---------------------

This attaches a file to a test result with a particular ID, for example::

  steps:
    - "echo content > file.txt"
    - "lava-test-case test-attach --result pass"
    - "lava-test-case-attach test-attach file.txt text/plain"

The arguments are:

 1. test case id
 2. the file to attach
 3. (optional) the MIME type of the file (if no MIME type is passed, a
    guess is made based on the filename)

lava-test-run-attach
--------------------

This attaches a file to the overall test run that lava-test-shell is
currently executing, for example::

  steps:
    - "echo content > file.txt"
    - "lava-test-run-attach file.txt text/plain"

The arguments are:

 1. the file to attach
 2. (optional) the MIME type of the file (if no MIME type is passed, a
    guess is made based on the filename)


Handling Dependencies (Ubuntu)
==============================

If your test requires some packages to be installed before its run it can
express that in the ``install`` section with::

  install:
      deps:
          - linux-libc-dev
          - build-essential

Adding Git/BZR Repositories
===========================

If your test needs code from a shared repository, the action can clone this
data on your behalf with::

  install:
      bzr-repos:
          - lp:lava-test
      git-repos:
          - git://git.linaro.org/people/davelong/lt_ti_lava.git

  run:
      steps:
          - cd lt_ti_lava
          - echo "now in the git cloned directory"

This repository information will also be added to resulting bundle's software
context when the results are submitted to the LAVA dashboard.

default parameters
==================

The "params" section is optional. If your test definition file includes
shell variables in "install" and "run" sections, you can use a ``params``
section to set the default parameters for those variables.

The format should be like this::

    params:
      VARIABLE_NAME_1: value_1
      VARIABLE_NAME_2: value_2

    run:
        steps:
        - echo $VARIABLE_NAME_1


The JSON would override these defaults using the syntax::

        {
            "command": "lava_test_shell",
            "parameters": {
                "testdef_repos": [
                    {
                        "git-repo": "http://git.linaro.org/git-ro/people/neil.williams/temp-functional-tests.git",
                        "testdef": "params.yaml",
                        "parameters": {"VARIABLE_NAME_1": "eth2"}
                    }
                ],
                "timeout": 900
            }
        }

Always set default values for all variables in the test definition file to
allow for missing values in the JSON file. In the example above, ``$VARIABLE_NAME_2``
is not defined in the JSON snippet, so the default would be used.

**NOTE:** The format of default parameters in yaml file is below, please note that
there is **not** a hyphen at the start of the line and **not** quotes around either
the variable name or the variable value ::

    VARIABLE_NAME_1: value_1

**NOTE:** The code which implements this parameter function will put variable
name and value at the head of test shell script like below::

    VARIABLE_NAME_1='value_1'

So please make sure you didn't put any special character(like single quote) into value or
variable name. But Spaces and double quotes can be included in value.
Because we use two single quote marks around value strings, if you put any variable into
value strings, that will **not** be expanded.


Examples:

http://git.linaro.org/people/neil.williams/temp-functional-tests.git/blob/HEAD:/kvm-parameters.json

http://git.linaro.org/people/neil.williams/temp-functional-tests.git/blob/HEAD:/params.yaml

Install Steps
=============

Before the test shell code is executed, it will optionally do some install
work if needed. For example if you needed to build some code from a git repo
you could do::

  install:
      git-repos:
          - git://git.linaro.org/people/davelong/lt_ti_lava.git

      steps:
          - cd lt_ti_lava
          - make

**NOTE:** The repo steps are done in the dispatcher itself. The install steps
are run directly on the target.

Advanced Parsing
================

You may need to incorporate an existing test that doesn't output results in
in the required pass/fail/skip/unknown format required by LAVA. The parse
section has a fixup mechanism that can help::

  parse:
      pattern: "(?P<test_case_id>.*-*)\\s+:\\s+(?P<result>(PASS|FAIL))"
      fixupdict:
          PASS: pass
          FAIL: fail

Adding dependent test cases
===========================

If your test depends on other tests to be executed before you run the
current test, the following definition will help::

  test-case-deps:
    - git-repo: git://git.linaro.org/qa/test-definitions.git
      testdef: common/passfail.yaml
    - bzr-repo: lp:~stylesen/lava-dispatcher/sampletestdefs-bzr
      testdef: testdef.yaml
    - url: http://people.linaro.org/~senthil.kumaran/deps_sample.yaml

The test cases specified within 'test-case-deps' section will be
fetched from the given repositories or url and then executed in the
same specified order. Following are valid repository or url source
keys that can be specified inside the 'test-case-deps' section::

 1. git-repo
 2. bzr-repo
 3. tar-repo
 4. url

NOTE: For keys such as git-repo, bzr-repo and tar-repo testdef name
within this repo must be specfied with 'testdef' parameter else
lavatest.yaml is the name assumed.

CAUTION: lava-test-shell does not take care of circular dependencies
within these test definitions, ie., if a test definition say tc1.yaml
is specified within test-case-deps section of tc-main.yaml and in
tc1.yaml there is a test-case-deps section which refers to
tc-main.yaml then this will create a circular dependency. This will
result in lava-test-shell fetching these test definitions tc1.yaml and
tc-main.yaml indefinitely and failing after timeout. But the user is
adviced to avoid this kind of situation, which could be easily
identified by many number of (more than the user thinks is fair for
the current test that is running) "loading ttest definition..."
messages in the job log file.
