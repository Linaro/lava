Version History
***************

.. _version_0_17:

Version 0.17
============

* Unreleased.

.. _version_0_16:

Version 0.16
============

* Add a RETIRED status for boards.
* Return a HTTP 403 not 404 when accessing a job that the logged in
  user does not have permission to see.

.. _version_0_15:

Version 0.15
============

* Add a view showing the status of each device type.

.. _version_0_14:

Version 0.14
============

* Add resubmit_job to the API
* Add support for looping of health care jobs

.. _version_0_13:

Version 0.13
============

* Allow job files to specify addresses to email on completion
  (possibly only unsuccessful completion).

.. _version_0_12_1:

Version 0.12.1
==============

* Enforce limits on how long jobs can run for and how large log files
  can grow to in the scheduler monitor.
* When killing off a process, escalate through SIGINT, SIGTERM,
  SIGKILL signals.

.. _version_0_12:

Version 0.12
============
* Two fixes around job privacy:
  * Display ValueErrors raised by from_json_and_user nicely to API users.
  * Allow submission to anonymous streams again.
* Job view improvements:
  * Show all dispatcher logs.
  * Highlight action lines.
  * Add link to download log file in summary page.
  * If the job log view is scrolled to the bottom when new output arrives, keep
    the view at the bottom.

.. _version_0_11:

Version 0.11
============
* Improvements to the magic ajax tables -- render the initial content
  of the table in the html to avoid requiring several requests to load
  one page.
* Make TestJob a restricted resource, and update views to reflect
  restrictions.
* Add admin action to set the health_status of all boards with pass
  status to unknown status -- for use after a rollout.
* Update to use the version of the ajax tables code that has been
  moved to lava-server.
* Validate the job file much more thoroughly when it is submitted.
* Allow for the creation of private jobs by copying the access data
  from the target bundle stream over to the created job at submit
  time.

.. _version_0_10.1:

Version 0.10.1
==============
* fix duplicate names for some views

.. _version_0_10:

Version 0.10
============
* Introduce health check jobs
  * These are defined on the device type and run when a board is put
    online or when no health check job has run for 24 hours
  * There are also views to just look at the health status of a board
    or the lab as a whole.
* The scheduler monitor is more reliably told where to log.
* Make all tables paginated via server-side ajax magic.

.. _version_0_9:

Version 0.9
===========
* Make alljobs paginated so that it will load very quickly
* handle invalid values for start in job_output
* record device status transitions
* ask for a reason when offlining/onlining a board
* display transitions on the device page

.. _version_0_8:

Version 0.8
===========
* improvements to the docs from Adam Konarski
* make submit_job give slightly more useful permission errors
* restore code to allow submission of results to a private bundle
* reject unknown jobs at submit time

.. _version_0_7_3:

Version 0.7.3
=============
* Don't assume dispatcher log files contain valid unicode (#918954)
* Include static assets in the sdist (multiply reported as: #919079,
  #919047, #917393)

.. _version_0_7_2:

Version 0.7.2
=============
* Revert 'allow results to be submitted to non-anonymous bundle streams' as it
  caused the entire job to be deleted when it completed.

.. _version_0_7_1:

Version 0.7.1
=============
* Allow results to be submitted to non-anonymous bundle streams
* Improved job view when log files are missing
* Fixed some issues with device tags and postgres

.. _version_0_7_0:

Version 0.7.0
=============

*  Add support for device tags in the scheduler
*  Overhaul of the job view
*  Fix unit tests

.. _version_0_5_5:

Version 0.5.5
=============

* Add some docs for lava-scheduler
