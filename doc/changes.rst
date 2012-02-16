Version History
***************

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
