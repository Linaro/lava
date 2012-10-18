LAVA Test Shell
***************

The ``lava_test_shell`` action provides a way to employ a more black-box style
testing appoach with the target device. The test definition format is quite
flexible allows for some interesting things.

Minimal Test Definition
=======================

::

  {
      "format": "Lava-Test Test Definition 1.0",
      "test_id": "pass_fail"
      "run": {
          "steps": ["echo test-1: pass", "echo test-2: fail"]
      "parse": {
          "pattern": "(?P<test_case_id>.*-*):\\s+(?P<result>(pass|fail))"
      }
  }

The main thing to note is that the parse pattern requires regex expressions
like \\s to be escaped, so it must be \\\\s

Handling Dependencies (Ubuntu)
==============================

If your test requires some packages to be installed before its run it can
express that in the ``install`` section with::

  "install": {
    "deps": ["linux-libc-dev", "build-essential"]
  },

Adding Git/BZR Repositories
===========================

If your test needs code from a shared repository, the action can clone this
data on your behalf with::

  "install": {
      "bzr-repos": ["lp:lava-test"],
      "git-repos": ["git://git.linaro.org/people/davelong/lt_ti_lava.git"]
  },
  "run": {
      "steps": ["cd lt_ti_lava", "echo now in the git cloned directory"]
  }

This repository information will also be added to resulting bundle's software
context when the results are submitted to the LAVA dashboard.

Install Steps
=============

Before the test shell code is executed, it will optionally do some install
work if needed. For example if you needed to build some code from a git repo
you could do::

  "install": {
      "git-repos": ["git://git.linaro.org/people/davelong/lt_ti_lava.git"],
      "steps": ["cd lt_ti_lava", "make"]
  },

**NOTE:** The repo steps are done in the dispatcher itself. The install steps
are run directly on the target.

Advanced Parsing
================

You may need to incorporate an existing test that doesn't output results in
in the required pass/fail/skip/unknown format required by LAVA. The parse
section has a fixup mechanism that can help::

  "parse": {
    "pattern": "(?P<test_case_id>.*-*)\\s+:\\s+(?P<result>(PASS|FAIL))",
    "fixupdict": {
        "PASS": "pass",
        "FAIL": "fail"
    }
  }
