.. _job_help:

LAVA job failures, errors, comments and tags
############################################

LAVA jobs and LAVA test cases may fail for a number of reasons, including:

* Errors in the JSON, YAML, parser or custom scripts:

  * Files expected to be downloaded are absent or have been moved or deleted

  * YAML files copied from a repository to a location outside VCS without
    adding a Version to the YAML

  * Custom scriptsfailing, not available or not executable - see
    :ref:`custom_scripts`

  * missing dependencies

  * parser errors

* Errors in the deployed image or kernel

* Errors in LAVA

* Failures on the device

See :ref:`writing_tests`

Dispatcher error or test failure
********************************

If LAVA detected an error during the job, that error will be highlighted at the
top of the job output. Some errors can be due to bugs in LAVA and should be
reported to LAVA using the link at the bottom of each LAVA page. Other errors
may be LAVA detecting an error in the job data (JSON, YAML, parser or scripts)
which need to be fixed by the test writer.

See :ref:`best_practices`

When LAVA detects an error, the job will be marked as ``Incomplete`` and will
show up in the failure reports for the device type and the device.

.. _failure_tags:

Job failure tags
****************

Failure tags allow the same failure reason to be marked on a variety of
different jobs which may otherwise be unrelated. If a particular failure starts
to become common with a particular piece of hardware or due to a specific
cause, a tag can be created by the lab aministrators.

Failure tags can be used whether the job was marked as ``Incomplete`` in LAVA
or not. The tags will show on the job output but only ``Incomplete`` jobs will
show failure tags in the reports.

.. _failure_comments:

Job failure comment
*******************

Failure comments can be used when a failure is unique, rare or to add more
detail to an existing tag as it relates to this specific job.

Failure comments can be used whether the job was marked as ``Incomplete`` in
LAVA or not. The comments will show on the job output but only ``Incomplete``
jobs will show failure comments in the reports.

.. _lava_failure_messages:

LAVA Failure messages
*********************

This list will be expanded over time.

.. _missing_method_failures:

Missing methods
===============

Errors in test job submissions and errors in admin setup can show up as a
failure comment of no deployment or boot method being available. First, attempt
to reproduce the failure with one of the :ref:`standard test jobs
<using_gold_standard_files>`. If the error is reproduced, the admin can use the
:ref:`admin_triage` guidelines to identify the problem.

.. _python_traceback_failures:

Python traceback messages
=========================

These messages relate to code errors which should either have been caught as
invalid input or handled gracefully within the test job. Failure messages
containing a traceback should be reported as bugs.

.. seealso:: :ref:`getting_support`

.. _compatibility_failure:

Compatibility failures
======================

Some updates of the LAVA packages can introduce new code support or changes to
the code support. The master and the worker need to be running the same code
version of ``lava-dispatcher`` for the test job to run correctly. For example,
a deprecated option in a test job submission could be removed in an update. If
the master is running an older version of code than the worker, the test job
could fail as the worker would be unable to handle the removed option.

To prevent this, the master and the worker calculate a compatibility number for
each test job. If this number does not match, the test job will fail. So a
compatibility failure indicates that the ``lava-dispatcher`` code on the worker
is out of date with respect to the master. This is a problem which needs to be
reported to the admins.

.. seealso:: :ref:`compatibility_failures` for more information on how
   developers set the compatibility for test jobs.

.. _commenting on failures:

Commenting on or tagging a job failure
**************************************

If you have permission to add or edit failure tags and comments, a button will
be displayed on the job output page ``Comment on failure``.

The button displays a form where the current tag(s) or comment(s) are
displayed. Additional tags can be selected and the comment (if any) can be
edited.

Viewing reports of job failures
*******************************

Incomplete jobs will show up in the reports. Reports are generated which cover
all jobs, all jobs on a specified :term:`device type` and all jobs on a
specific device.

Reports show two graphs of the number of complete jobs against the number of
incomplete jobs over time, separating health checks from other test jobs.
Clicking on the time / day link shows the failure tags and failure comments for
the incomplete jobs during that timeframe.

Unreported test failures
************************

Not all test failures will show as incomplete jobs and a ``Complete`` job can
still have failure tags and failure comments assigned.

If a test failed due to a problem outside the test definition or supporting
files and scripts, use the link at the bottom of each page to report a bug.
