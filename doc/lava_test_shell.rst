LAVA Test Shell
***************

The ``lava_test_shell`` action provides a way to employ a more black-box style
testing appoach with the target device. The test definition format is quite
flexible and allows for some interesting things.

Quick start
===========

A minimal test definition looks like this::

  metadata:
      format: Lava-Test Test Definition 1.0
      name: passfail

  run:
      steps:
          - echo "test-1: pass"
          - echo "test-2: fail"

  parse:
      pattern: "(?P<test_case_id>.*-*):\\s+(?P<result>(pass|fail))"

Note that the parse pattern has similar quoting rules as Python, so
\\s must be escaped as \\\\s and similar.

A lava-test-shell is run by:

 * "compiling" the above test defintion into a shell script
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

There is also a more involved, LAVA-specific, way of writing tests.
When a test runs, ``$PATH`` is arranged so that some LAVA-specific
utilities are available:

 * ``lava-test-case-attach``

lava-test-case-attach
---------------------

This attaches a file to a test result with a particular ID, for example::

  steps:
    - "echo content > file.txt"
    - "echo test-attach: pass"
    - "lava-test-case-attach test-attach file.txt text/plain"

The arguments are:

 1. test case id
 2. the file to attach
 3. (optional) the MIME type of the file (if no MIME type is passed, a
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


