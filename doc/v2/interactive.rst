.. index:: writing test - interactive

.. _writing_tests_interactive:

Writing an interactive test action
##################################

.. seealso:: :ref:`Interactive test action reference <interactive_test_action>`

Parsing test output will always involve some amount of pattern
matching. The test action creates a stream of output, (typically
ASCII), and this needs to be turned into test results either using
scripts on the DUT or after transmission over a serial connection.

Interactive test actions move all of the parsing to the test writer
commands by setting a sequence of strings with expected output and
support for determining failures.

.. note:: All interactive test actions need to specify all possible
   failure strings for each command, as well as the type of exception
   to raise when a string is matched. Interactive test actions must
   always have a start and end to the parsing or the entire job will
   simply time out because none of the expected matches exist.

Interactive test actions cannot provide support for monitoring kernel
boot messages or :ref:`lava_test_helpers`, all pattern matching is done
solely by the strings set by the test writer. This rules out support
like :ref:`MultiNode <multinode>` and :ref:`Lava-Test Test Definition
1.0 <writing_tests_1_0>`.

.. seealso:: :ref:`test_definition_portability`

.. _interactive_advantages:

Advantages of interactive pattern matching
******************************************

#. Keeps pattern matches tightly wrapped around limited sections of
   predictable test action output, not across the entire test job or
   even the complete test action output.

#. Provides methods to execute complex instructions (including
   regular expressions) without mangling the syntax due to the
   constraints of the submission format (in the case of LAVA, YAML
   strings).

#. Avoids issues with needing to deploy a set of POSIX scripts to the
   :term:`DUT`, e.g. when the filesystem is inaccessible or read-only
   or has access controls like SELinux.

#. Allowing test writers to use any arbitrary test output style.

#. Includes ability for test writers to raise exceptions based on
   specific matches, controlled by the test writer.

#. Encourages test writers to create :ref:`portable
   <test_definition_portability>` custom scripts which are idempotent.
   this can make it easier to reproduce failures when reporting bugs
   to upstream developers who do not have access to the CI system.

.. _interactive_limits:

Limits of interactive pattern matching
**************************************

#. Lacks support for optimizations when specific sections of the test
   output comply with a known and strictly enforced format.

#. Can be difficult to convert into test action methods which aid
   portability. CI becomes difficult for the developers receiving the
   bug reports if the developers cannot reproduce the bug without
   using the same CI.

#. Supporting test jobs with multiple, different, test action
   behaviors for each stage of the test operation. For example,
   dependency resolution and setup commands could be done with an
   overlay and Lava Test Shell Definition whilst running the test to
   output a known result format could use a parser specific to that
   format.

#. Lacks support for versioning of test action components. Test writers
   need to implement their own versioning system and ensure that
   versions are output into the LAVA test job log file and/or as a
   test result.

.. _example_interactive_job:

Example interactive test job
****************************

.. literalinclude:: examples/test-jobs/bbb-uboot-interactive.yaml
   :language: yaml
   :linenos:
   :lines: 1-39
   :emphasize-lines: 19-24, 28-39

Download or view example interactive test job:
`examples/test-jobs/bbb-uboot-interactive.yaml
<examples/test-jobs/bbb-uboot-interactive.yaml>`_

.. index:: writing test - combining actions

.. _combining_test_actions:

Combining different test actions
################################

In some situations, there can be a need to combine two or more
different types of test action in a single test job. For example,
a POSIX overlay test action to do initial setup, then a ``monitors`` or
``interactive`` test action to parse the output of a specific task.

It is very important to understand that Lava-Test Test Definition 1.0
**cannot** occur more than once in a single test job once any other
test action type is used. If further test actions are required via the
POSIX shell, an interactive test action must be used.

A single Lava-Test Test Definition 1.0 test action can already include
multiple different tests, potentially from different repositories:

.. literalinclude:: examples/test-jobs/qemu-pipeline-first-job.yaml
   :language: yaml
   :linenos:
   :lines: 49-60
   :emphasize-lines: 5, 7, 9, 11

It is fully supported to then add an interactive test action:

.. literalinclude:: examples/test-jobs/bbb-uboot-interactive.yaml
   :language: yaml
   :linenos:
   :lines: 25-39

However, until Test Definition 2.0 is fully scoped and delivered, it
is not possible to add another Lava-Test Test Definition 1.0 action.

.. note:: This applies within any one :term:`namespace`, it does not
   apply between different :ref:`namespaces <namespaces_with_lxc>`.
