.. _debugging:

Debugging LAVA test definitions
*******************************

.. _singlenode:

Convert Multi-Node jobs to single node
======================================

The scripts available in the :ref:`multinode_api` are not installed for
test jobs which are not part of a MultiNode group, so the job will simply
fail that test as a ``command not found``.

Other calls which may require communication with other devices may need
to be removed from your YAML. This can be extended to retain a set of
singlenode YAML files in which new wrapper scripts and new builds are
tested.

The Job Definition of one job within a MultiNode group may be a good
starting point for creating a singlenode equivalent.

.. _set_x:

Always use set -x in wrapper scripts
====================================

By viewing the complete log, the complete processing of the wrapper script
becomes obvious.

::

 #!/bin/sh
 set -e
 set -x

.. _shell_operators:

Avoid using shell operators in YAML lines
=========================================

Pipes, redirects and nested sub shells will not work reliably when put
directly into the YAML. Use a wrapper script (with :ref:`set -x <set_x>`).

::

 #!/bin/sh

 set -e
 set -x
 ifconfig|grep "inet addr"|grep -v "127.0.0.1"|cut -d: -f2|cut -d' ' -f1

Un-nested sub-shells do work::

 - lava-test-case multinode-send-network --shell lava-send network hostname=$(hostname) fqdn=$(hostname -f)

.. _check_messageid:

Check that your message ID labels are consistent
================================================

A :ref:`lava_wait` must be preceded by a :ref:`lava_send` from at least
one other device in the group or the waiting device will :ref:`timeout <timeouts>`

This can be a particular problem if you remove test definitions from the
JSON or edit a YAML file without checking other uses of the same file.

.. _parsers:

Test your result parsers
========================

If the YAML uses a custom result parser, configure one of your YAML files
to output the entire test result output to stdout so that you can
reliably capture a representative block of output. Test your proposed
result parser against the block using your favourite language.

Comment out the parser from the YAML if there are particular problems,
just to see what the default LAVA parsers can provide.

.. _paths:

Be obsessive about paths and scripts
====================================

* If you use ``cd`` in your YAML, always store where you were and where you end up using ``pwd``.
* Output your location prior to calling local wrapper scripts.
* Ensure that all wrapper scripts are executable in your VCS
* Ensure that the relevant interpreter is installed. e.g. python is not necessarily part of the test image.
* Consider installing ``realpath`` and use that to debug your directory structure.
  * Avoid the temptation of using absolute paths - LAVA may need to change the absolute locations.

.. _failed_tests:

A failed test is not necessarily a bug in the test
==================================================

Always check whether the test result came back as failed due to some
cause other than the test definition itself. Particularly with MultiNode,
a test result can fail due to some problem on a different board within
the group.
