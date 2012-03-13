Version History
***************

.. _version_0_11:

Version 0.11 (UNRELEASED)
=========================
* Improvements to the magic ajax tables -- render the initial content
  of the table in the html to avoid requiring several requests to load
  one page.
* Make TestJob a restricted resource, and update views to reflect
  restrictions.
* Add admin action to set the health_status of all boards with pass
  status to unknown status -- for use after a rollout.


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
