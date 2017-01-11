.. index:: results introduction

.. _results_intro:

Introduction to Results in LAVA
###############################

.. seealso:: :ref:`test_definition_yaml`

Results in LAVA
***************

At the lowest level, a result in LAVA is called a Test Case and is a simple
flag:

* pass
* fail
* skip
* unknown

In addition, each test case can include a measurement (integer or floating
point), with units.

Test cases are aggregated into a Test Suite. Multiple test suites can be
generated for each submitted test job.

.. seealso:: :ref:`recording_test_result_data`

.. _results_rest_api:

Accessing results
*****************

LAVA exposes a REST API to provide access to the results from test jobs. The
URL is built from the following components:

#. The instance name
#. The ``results`` directory.
#. The test job ID

From this point, all the results for the test job can be downloaded as
:abbr:`CSV (Comma Separated Values)` or YAML.

There are also CSV and YAML download links for the complete set of results for
the job. The export includes details of the test definition names. For example,
if a test job on ``validation.linaro.org`` has the job ID ``1109234``, the CSV
download link for all results would be
``https://validation.linaro.org/results/1109234/csv``. The YAML download link
for all results would be
``https://validation.linaro.org/results/1109234/yaml``.

Accessing specific test results
===============================

Within the results for the entire test job, results are split into test suites,
optionally into test sets and finally into test cases.

Test Suite
----------

The name of the Test Suite is determined by the test job definition.

.. include:: examples/test-jobs/qemu-pipeline-first-job.yaml
   :code: yaml
   :start-after: prompts: ["root@debian:"]

In this test job definition, there are two entries in the ``definitions`` list,
so two test suites. The first test suite in the list has the prefix ``0_`` and
the prefix increments for subsequent test suites in the list. The ``name``
element is then appended to create the test suite name.

* ``0_smoke-tests``
* ``1_singlenode-advanced``

The test suite can then be appended to the REST API URL for the results to
limit the results to just that test suite:
``/results/1109234/0_smoke-tests/csv`` or:
``/results/1109234/0_smoke-tests/yaml``.

In addition, every test job has a ``lava`` test suite which holds results for
the processing of the pipeline itself. This set of results can hold useful
information like the commit hash of the test definition when it was cloned to
create the overlay, the duration of all actions (including the kernel boot) and
other information.

.. note:: Test definitions will be rejected if the test suite name is set to
   ``lava`` to prevent conflicts with the internal results.

.. _test_set_results:

Test Set
--------

Test Set is optional but allows test writers to subdivide individual results
within a single Lava Test Shell Definition using an arbitrary label.

Some test definitions run the same test with different parameters. To
distinguish between these similar tests, it can be useful to use a test set::

 lava-test-set start syscalls
 lava-test-case syscalls
 # ....
 lava-test-set stop syscalls
 # change parameters
 lava-test-case start math
 lava-test-case math
 # ....
 lava-test-set stop math

This adds a set around those test cases by adding the test set to the URL.
``/results/JOB_ID/2_smoke-tests/syscall_one_test`` becomes
``/results/JOB_ID/2_smoke-tests/syscalls/syscall_one_test``

Test Case
---------

A Test Case can be generated in a number of ways:

* by calling ``lava-test-case`` from a Lava Test Shell.
* during operation of an Action within the pipeline
* by parsing patterns in the test

Each test case has a name and a result. Optionally, test cases can have
measurements and units. The name of the test case **must** be valid as part of
the REST API so whitespace is not allowed.

Accessing the test job logs from results
****************************************

There is a chevron in the test case detail page, directly after the test case
name, which links to the point in the log where that test was reported. The
same URL can also be determined in advance by knowing the job ID, the sequence
of test definitions in the test job definition and the name of the test case.

Once you know the result and the URL of the testjob, you can generate the URL
of the point in the test job log where that result was created.
``https://validation.linaro.org/results/1109234/1_lamp-test/mysql-show-databases``
links to
``https://validation.linaro.org/scheduler/job/1109234#results_1_lamp-test_mysql-show-databases_pass``

In the log file this section looks like:

.. code-block:: none

 Received signal: <TESTCASE> TEST_CASE_ID=mysql-show-databases RESULT=pass
 case: mysql-show-databases
 definition: 1_lamp-test
 result: pass

.. note:: The test shell does not wait until the test case entry has been
   created before moving on, so there can be an offset between the point linked
   from the result (where the test case entry was created) to the point
   slightly earlier in the log where the test itself was executed. This wait
   behaviour caused various bugs as it needs to block at the shell read command
   which gets confused by other messages on the serial console.

There is a REST API using the name of the test definition and the name of the
test case.

The name of the test definition comes from the test job definition:

.. code-block:: yaml

 - repository: http://git.linaro.org/lava-team/lava-functional-tests.git
      from: git
      path: lava-test-shell/single-node/singlenode03.yaml
      name: singlenode-advanced

The digit comes from the sequence of definitions in the list in the test action
of the test job definition. For example, a test job with three definitions may
result in the test actions: 0_env-dut-inline, 1_smoke_tests and
2_singlenode_advanced.

The test case name comes directly from the call to lava-test-case.

When an inline test definition does not report any test cases (by not calling
lava-test-case anywhere, just doing setup or diagnostic calls to put data into
the logs) then the metadata shows that test definition as "omitted" and it has
no entry in the results table.

omitted.0.inline.name: env-dut-inline

In addition, each test job gets a set of LAVA results containing
useful information like the commit hash of the test definition when it
was cloned for this test job.

Multiple occurrences
********************

If a test suite or test case occurs more than one in a set of results, those
occurrences will show up in the results table. If each occurrence is within the
same test definition, there will be one page showing both results (as the test
case name is the same, there can only be one URL). Each occurrence links to a
different point in the job log.
