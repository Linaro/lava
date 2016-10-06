.. _debugging_test_failures:

.. index:: debug, debugging test failures

Debugging LAVA test failures
############################

There are many potential reasons why tests running in LAVA might fail,
or produce unexpected behaviour. Some of them can be easy to track
down, but others may be more difficult. The devices, software and test
suites can vary massively from one test job to the next, but
nonetheless a few common ideas may help you to work out what's going
wrong.

.. _read_the_logs:

.. index:: read the logs

Read the logs
*************

This may seem obvious, but it is all too easy to miss real problems in
the test logs! For people not used to diagnosing failures, it is worth
reading all the way from deployment through test device boot to the
end of the logfile. If a test job fails to complete successfully, it
can often be caused by a problem much earlier in the test - don't
assume that the final few lines of the logfile will tell the whole
story:

* A kernel message about failing to load a module or a device failing
  to initialise may be very easily missed in a long stream of kernel
  boot messages. Equally, check that the expected device and module
  messages are present.

* A 'syntax error' from a shell script early in the test run could
  easily propagate errors to later test results.

* A test shell may timeout due to an earlier 'Command not found' or
  'No such file or directory'.

When writing tests, :ref:`make things verbose<make_tests_verbose>` to
give yourself more useful logs in case they fail.

.. _boot_failure:

.. index:: boot failure

Boot failure
************

If the test system does not (seem to) boot at all, there are a few
things worth checking:

* Did the LAVA dispatcher manage to download and deploy the correct
  files that were specified in the test job? Check that all the files
  downloaded OK, and that any additional work needed on them worked OK
  (e.g. deploying any overlays). You can also specify the expected
  checksum for each file your test job deploys, to guard against
  download corruption (see `_deploy_action`).

* Did you specify the correct files in your test job? It's quite easy
  to make a mistake and use the wrong kernel build, or cut and paste
  the wrong URL from a directory listing.

* (Where needed) Did you use the correct :term:`DTB` for the test
  device? Symptoms here could include apparent boot failure, as the
  kernel will either not boot or boot but not provide any useful boot
  messages.

.. _rootfs_failure:

.. index:: rootfs failure, fails to mount root

Failure to find/mount the rootfs
********************************

Did the kernel boot OK but then fail to find the root filesystem? This
is a common failure mode, and there are quite a few possible
causes. Here are some of the more common failure cases.

* Again, check that the LAVA dispatcher could download and deploy the
  correct rootfs as specified in the test job.

* Make sure that your kernel has the right drivers available that it
  needs to support the rootfs. Depending on your particular setup,
  they may need to be built-in, or your kernel may need modules to be
  supplied by an initramfs. Typical modules that may be needed will be
  for disk devices (e.g. ``sd_mod``), filesystems (e.g. ``ext4``) or
  network interfaces (e.g. ``e1000e``) if you're using NFS for the
  rootfs. You should be able to see what devices are found by the
  kernel by reading the boot messages; check that the device you are
  expecting to use does show up there.

* Make sure that you have specified the correct root device on the
  kernel command line, using the ``root=`` parameter.

* Make sure that the rootfs includes a working ``init`` program, in
  the correct location. In an initramfs, the default location is
  ``/init``; this can be over-ridden on the kernel command line using
  the ``init=`` parameter.

.. _start_simple:

Start simple
************

This is a common theme throughout the suggested workflow for
developing tests in LAVA. Start with simple test jobs and verify they
work as expected. Add complexity one step at a time, ensuring that
each new option or test suite added behaves as expected. It's much
easier to work out what has broken in a test job if you've made just
one small change to a previous test job that worked fine.

Similarly, if you have a complex test job that's not working
correctly then often the easiest way to find the problem is to
simplify the job - remove some of the complexity and re-test. By
removing the complex setup in the test, it should be possible to
identify the cause of the failure.

If there are standard test jobs available for the device type in
question, it might be useful to compare your test job to one of those
standard jobs, or even start with one and append your test
definitions.

.. _change_one_thing:

Change one thing at a time
**************************

When developing a test, resist the urge to make too many changes at
once - test one element at a time. Avoid changing the deployed files
and the test definition in the same job. When the deployed files
change, use an older test definition and an inline definition to
explicitly check for any new support your test will want to use from
those new files. If you change too many variables at once, it may
become impossible to work out what change caused things to break.

.. _make_tests_verbose:

Make your tests and setup verbose
*********************************

Especially when developing a new test, add plenty of output to explain
what is going on. If you are starting with a new test device or new
boot files, make it easy to diagnose problems later by adding
diagnostics early in the process. In general, it is much easier to
debug a failed test when it is clear about what it expects to be
happening than one which just stops or says "error" in the middle of a
test.

* If your test configures a network interfaces, add the output of
  ``ifconfig`` or ``ip a show`` afterwards to show that it worked.

* If your test uses a specific block device or filesystem, add the
  output of ``df`` or ``mount`` to show what devices and filesystems
  are available.

.. _set_x:

If you are writing shell scripts to wrap tests, try using ``set -x`` -
this will tell the shell to log all lines of your script as it runs
them. For example:

.. code-block:: shell

 #!/bin/sh
 set -e
 set -x
 echo "foo"
 a=1
 if [ $a -eq 1 ]; then
   echo "yes"
 fi

will give the following output::

 + echo foo
 foo
 + a=1
 + [ 1 -eq 1 ]
 + echo yes
 yes

.. index:: pitfalls

.. _common_pitfalls:

Common pitfalls
***************

There are some common mistakes using LAVA which can cause issues. If
you are experiencing weird problems with your test job, maybe
considering these will help.

.. _shell_operators_yaml:

Avoid using shell operators in YAML lines
=========================================

Pipes, redirects and nested sub shells will not work reliably when put
directly into the YAML. Use a wrapper script (with :ref:`set -x
<set_x>`) instead for safety:

.. code-block:: shell

 #!/bin/sh

 set -e
 set -x
 ifconfig|grep "inet addr"|grep -v "127.0.0.1"|cut -d: -f2|cut -d' ' -f1

Un-nested sub-shells do work, though::

 - lava-test-case multinode-send-network --shell lava-send network hostname=$(hostname) fqdn=$(hostname -f)

.. _parsers:

Test your result parsers
========================

If you use a custom result parser, configure one of your YAML files to
output the entire test result output to stdout so that you can
reliably capture a representative block of output. Test your proposed
result parser against the block using your favourite language.

Comment out the parser from the YAML if there are particular problems,
just to see what the default LAVA parsers can provide.

.. note:: Parsers can be difficult to debug after being parsed from
	  YAML into shell. LAVA developers used to recommend the use
	  of custom parsers, but experience has shown this to be a
	  mistake. Instead, it is suggested that new test definitions
	  should use :ref:`custom scripts<custom_scripts>`. This
	  allows the parsing to be debugged outside LAVA, as well as
	  making the test itself more portable.

.. _paths:

Be obsessive about paths and scripts
====================================

* If you use ``cd`` in your YAML, always store where you were and
  where you end up using ``pwd``.

* Output your location prior to calling local wrapper scripts.

* Ensure that all wrapper scripts are executable in your VCS

* Ensure that the relevant interpreter is installed. e.g. python is
  not necessarily part of the test image.

* Consider installing ``realpath`` and use that to debug your
  directory structure.

* Avoid the temptation of using absolute paths - LAVA may need to
  change the absolute locations.

.. _debugging_multinode:

.. index:: MultiNode, debugging MultiNode tests

Debugging MultiNode tests
*************************

MultiNode tests are necessarily more complex than jobs running on
single test devices, and so there are extra places where errors can
creep in and cause unexpected failuures.

.. _simplify_multinode:

Simplify your MultiNode test
============================

This may seem obvious, but one of the most common causes of MultiNode
test failure is nothing to do with MultiNode. If your MultiNode tests
are failing to boot correctly, check that the basics of each of the
desired roles works independently. Remove the MultiNode pieces and
just check that the specifiied deploy and boot actions work alone in a
single-node test with the right device-type. Then add back the
MultiNode configuration, :ref:`changing one thing at a
time<change_one_thing>` and ensuring that things still work as you
build up complexity.

.. _check_messageid:

Check that your message ID labels are consistent
================================================

A :ref:`lava_wait` must be preceded by a :ref:`lava_send` from at
least one other device in the group, or the waiting device will
:ref:`timeout <timeouts>`

This can be a particular problem if you remove test definitions or
edit a YAML file without checking other uses of the same file. The
simplest (and hence recommened) way to use the MultiNode
synchronisation calls is using :ref:`inline
definitions<inline_test_definitions>`.

.. _failed_tests:

A failed test is not necessarily a bug in the test
==================================================

Always check whether the test result came back as a failure due to
some cause other than the test definition itself. Particularly with
MultiNode test jobs, a test can fail for other reasons like an
unrelated failure on a different board within the group.

