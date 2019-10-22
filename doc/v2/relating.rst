.. index:: results - correlation

.. _linking_results_to_code:

Correlating a test result with the source code
##############################################

As part of a CI loop, the results of the LAVA test job may indicate a
bug or regression in the source code which initiated the CI loop. These
issues would be distinct from infrastructure or job errors and
reporting these issues is a customized process for each team involved.

The details of how and why the test failed will typically be essential
to identifying how to fix the issue, so developers need help from test
writers and from LAVA to provide information, logs and build artefacts
to be able to reproduce the issue.

However, it is common for a test failure to occur due to an earlier
failure in the test job, e.g. changes in dependencies. It is also
common for tests to report the error briefly at one point within the
log and then provide more verbose content at another point.

So the first problem can be correlating the test output with the actual
failure. Test writers often need to modify how the original test
behaves, to be able to identify which pieces of output are relevant to
any particular test failure. Each test is different and uses different
ways to describe, summarize, report and fail test operations. Test
writers already need to write customized wrappers to run different
tests in similar ways. To be able to relate the failures back to the
source code, a lot more customization is likely to be required.

Overall, LAVA can only be one part of the effort to triage test
failures and debug the original source code. Results need to be
presented to developers using a :term:`frontend`, test writers need to
write scripts to wrap test suites and there needs to be enough other
tests being run that developers have a reliable way of knowing all the
details leading up to the failure.

.. seealso:: :ref:`custom_result_handling`, :ref:`setup_custom_scripts`
   and :ref:`continuous_integration`

Problems within test suites
***************************

Avoid reliance on the total count
=================================

Test suites which discover the list of tests automatically can be a
particular problem. Each test job could potentially add, remove or skip
test results differently to previous test jobs, based on the same
source code changes that triggered the test in the first place. Test
writers may need to take control of the list of tests which will be
executed, adding new tests individually and highlighting tests which
were run in previous jobs but which are now missing.

For example, if a developer is waiting for a large number of CI
results, automated test suites which add one test whilst removing
another could easily mislead the developer into thinking that a
particular test passed when it was actually omitted. This is made worse
if the test suite has wide coverage as the developer might not be aware
of the context or purpose of the added test result.

The LAVA :term:`Charts <chart>` are only intended as a generic summary
of the results, it is all too easy to miss a test being replaced if the
report sent to the developer is only tracking the number of passes over
time.

Control the test operations
===========================

* Keep the test itself stable, this includes the wrappers and the
  reporting.

* Use staging instances for all components, including LAVA and any
  :term:`frontends <frontend>` where each and every change is tested
  against known working components.

* Avoid downloading from third-party URLs. Use tools from the existing
  base system or build known working versions of the tools into the
  base system so that every test always uses the same tools.

  * Use checksums on all downloaded content if this is not implemented
    by the base system itself. (For example, ``apt`` and ``dpkg`` use
    checksums and other cryptographic methods extensively, to ensure
    that downloads are from verified locations and of verified
    content.)

* Push your changes upstream. Avoid the burden of forks by working with
  each upstream to improve the tools and test scripts themselves.

* Split the test operations into logical blocks. A combined test job
  can still be run separately but there are advantages to running more
  test jobs, each of shorter duration:

  * test jobs can be run in parallel across a pool of devices.

  * logs are smaller and easier to triage.

  * failures are easier to reproduce.

  * shorter test jobs can make it easier to build and run the full
    matrix of jobs which results from only changing one element at a
    time. Not all tests need to be run to know that the firmware is
    working correctly.

* Use descriptive commit messages in the test shell version control and
  use code review.

* Consider formal bug tracking for the test shell scripts, distinct
  from other bugs.

* Implement ways to resubmit after infrastructure failures, using the
  same automated submitter, metadata, artefacts and tests.

Control the output
==================

Established test suites often lack any standard way of outputting the
process of running the results, the format of errors and the layout of
the result summary.

Each of these elements may need to be taken over by the test writer to
allow the developer a way to identify a specific test and the section
of the LAVA logs to which it relates.

This can cause issues if, for example, a wrapper has to wait until the
end of the test process to obtain the relevant information. The test
job may appear to stall and later produce a flood of output. If the
wrapper or the underlying test fail in an unexpected way, it is very
easy to produce a LAVA test job with no useful output for any of the
results.

To be able to properly correlate the test results to the source code,
it may become necessary to rewrite the test suite itself and then
consider pushing the changes upstream.

LAVA is investigating ways to help test writers standardize the ways
of running tests to be able to provide more benefit from automated
log files. :ref:`Talk to us <getting_support>` if you have ideas for or
experience of such changes.

Control the base system
=======================

Most tests require some level of system to be executing and some level
of dependencies within that system. The choice of which system to use
can impact the triage of the results obtained.

* If the system is continuously changing (at the source code level),
  then results from last month may be completely invalid for comparing
  with the most recent failure.

* If the system is based on a distribution which supports reproducing
  an identical system at a later time, this may make it much simpler
  to triage failures and bisect regressions.

Consider the impact of the base system carefully - triage and bisection
may require weeks of historical data to be able to identify the root of
any reported issues. Test one thing at a time.

Control the build system
========================

* Avoid changing the name of files between builds unless those files
  have actually changed.

* Avoid reliance on build numbers when not everything in the build has
  changed.

  * Use version strings which relate directly to the versions used by
    the source code for that binary.

* Make changelogs available for the components that have changed
  between builds.

* Always publish checksums for all build artefacts.

This is to make it easier, during triage, to use known working versions
of each component whilst changing just one component. It can be very
difficult to relate a build number from a URL to an upstream code
change, especially if the build system removes build URLs after a
period of time.

Remember that every component has it's own upstream team and it's own
upstream source code versioning. If a bug is found in one component,
locating the source code for that component will involve knowing the
exact upstream version string that was actually used in the test.

Control the list of tests
=========================

It may be necessary to remove the auto-detection support within the
test suite and explicitly set which tests are to be run and which are
skipped.

Avoid executing tests which are known to fail. Developers reading the
final report need to be able to pick out which tests have failed
without the distraction of then filtering out tests which have never
passed.

Avoid hiding the list of tests inside test scripts. Ensure that the
report sent to developers discloses the tests which were submitted and
the tests which were skipped. Provide changelogs when the lists are
changed.

Review the list of skipped tests regularly. This can be done by
submitting LAVA test jobs which only execute tests which are skipped in
other test jobs. Again, ensure that only one element is changed at a
time, so choose the most stable kernel, root filesystem and firmware
available as the base for executing these skipped tests on an
occasional basis.

Distinguish between CI tests and functional tests
=================================================

CI tests need to use lots of support to relate the results back to the
reason for running the test in the first place.

Functional tests exist to test the elements outside the test job and
include things like :term:`health checks <health check>` and sample
jobs used for unit tests.

The objective of a CI test job is to test the changes made by
developers.

The objective of a functional test job is to test the functionality of
the CI system.

Health checks are not the only functional tests - sometimes there is
functionality which cannot be put into a health check. For example, if
additional hardware is available on some devices of a particular
:term:`device type`, the health check may report a failure when run on
the devices without that hardware. This may need to be taken into
account when deciding what qualifies as a new :ref:`device type
<device_types>`. Functional tests can be submitted automatically, using
notifications to alert admins to failures of additional hardware.

Manage testing of complete software stacks
==========================================

It is possible to test a complete software stack in automation,
however, unpicking that stack to isolate a problem can consume very
large amounts of engineering time. This only gets worse when the
problem itself is intermittent due to the inherent complexity of
identifying which component is at fault.

Wherever possible, break up the stack and test each change
independently, building the stack vertically from the lowest base able
to run a test.

* Boot test the kernel with an unchanging root filesystem and a known
  working build of firmware. Ensure that each kernel build is boot
  tested before functional tests are submitted.

* Test the modified root filesystem with a known working kernel and
  known working firmware.

  * Test with and without installing the dependencies required for the
    later tests. Check that the system works reliably to be able to
    prepare the dependencies.

* Break the test into components and test each block separately.

* Only change the "gold standard" files when absolutely essential,
  this includes firmware, kernel, root filesystem and any dependencies
  required by the test as well as the code running the test itself.

Metadata
********

.. seealso:: :ref:`job_metadata`.

Any link between a test result in LAVA and a line of source code will
rely on metadata.

* Pre-installed dependencies of the test, including versions and
  original source. Using a reproducible distribution for this can
  provide confidence that the test result arises from the tests and
  not the base operating system.

* the git commit hash of the source code used in the build

* the git commit hash of the test code executing the tests as this
  is often external to the source code being tested. LAVA provides the
  commit hash of the Lava Test Shell Definition but scripts executed
  by LAVA will need to be tracked separately.

* the filename of the code running the test. (Remember that the result
  of any test may be due to a bug in the function running the test, as
  well as a bug in the code being executed outside the test function.)

* the filename(s) within the source code for each error produced by the
  test. (Most test suites do not have this support or may only infer it
  via the name of the test function. The affected code could easily be
  moved to a different file without changing the test function name.)

* the location of the source code

  * how to construct a URL to the file at the specified version at
    the location. This differs according to the chosen web service
    for the repository.

* control the metadata and the queries which use it. Users and admins
  will frequently copy and paste job submissions to retry particular
  issues. Always ensure that queries and reports look at the metadata
  only from a known automated submitter.

Reproducing test jobs
*********************

LAVA can support developers who want to reproduce a test job locally
but the details depend a lot on the actual device being used. Some
devices will need significant amounts of (sometimes expensive or
difficult to obtain) support hardware. However, once an alternative
rig is assembled, developers can use ``lava-run`` to re-run the test
job locally.

.. seealso:: :ref:`running_lava_run`

Other options include:

* **emulation** - depending on the nature of the failure, it may be
  possible to emulate the test job locally and in LAVA.

* **local workers** - if devices are available locally, a
  :term:`worker` can be configured to run test jobs using a remote
  master.

* **portability** - the best option is when the issue can be reproduced
  without needing the original hardware. If the scripts used in LAVA
  are portable, developers can run the test process without needing
  automation.

  .. seealso:: :ref:`test_definition_portability`
