.. index:: writing test - monitors

.. _writing_tests_monitor:

Writing a monitors test action
##############################

.. seealso:: :ref:`monitor_test_action` and :ref:`test_developer`

:ref:`writing_tests_1_0` involves adding an overlay of POSIX scripts to
the DUT but some devices cannot support an overlay. The ``monitors``
test action supports IoT devices using pattern matching against
non-interactive output streams. As with :ref:`pattern matching  in the
Lava-Test Test Definition 1.0 <parse_patterns_1_0_deprecated>`, this
can be difficult at times.

The IoT application needs to be specially written to create output
which is compatible with automation. Test actions for IoT devices tend
to be short and specific to one dedicated application executing on the
DUT. Applications need to be written to emit a ``START`` and ``STOP``
message which have to be unique across all test job output, not just
the test action. Test writers then need to correlate specific pattern
match expressions in the test job with the behavior of the application
deployed in that test job. This puts the work of creating a parser into
the hands of the writers of the test application and can thus interfere
with development of the test application.

Restrictions
************

Test jobs using Monitors must:

* Use carefully designed applications which are designed to
  automatically execute after boot.

* Emit a unique start string:

  * Only once per boot operation.
  * Before any test operation starts.

* Emit a unique end string:

  * Only once per boot operation.
  * After all test operations have completed.

* Provide a regular expression which matches all expected test output
  and maps the output to results without leading to excessively long
  test case names.

* start and end strings will match part of a line but make sure that
  each string is long enough that it can only match once per boot.

If start does not match, the job will timeout with no results.

If end does not match, the job will timeout but the results (of the
current boot) will already have been reported.

.. _example_monitors_job:

Example test monitors job
*************************

.. literalinclude:: examples/test-jobs/frdm-kw41z-zephyr.yaml
   :language: yaml
   :linenos:
   :lines: 1-39
   :emphasize-lines: 32-39

Download or view example test monitors job:
`examples/test-jobs/frdm-kw41z-zephyr.yaml
<examples/test-jobs/frdm-kw41z-zephyr.yaml>`_
