Version History
***************

See also:

* ..  :ref:`_lava_dashboard_history` (obsolete)
* ..  :ref:`_lava_scheduler_history` (obsolete)

.. _lava_server_0_20:

Version 0.20
============
* remove "project" concept

.. _lava_server_0_19:

Version 0.19
============
* Improve user experience for 403 errors

.. _lava_server_0_18_1:

Version 0.18.1
==============
* Set the postgresql statement timeout to 30s.

.. _lava_server_0_18:

Version 0.18
============
* Documentation updates.
* Make token page clearer about what the token actually is.
* Enable devserver if it is available (i.e. if an instance is using
  buildout-development.cfg)
* If a table is queryset backed but not ajax enabled, render all the
  data.
* Load font css over https.

.. _lava_server_0_17:

Version 0.17
============
* Fixed some column sorting options
* Added a "me" extension for preferences

.. _lava_server_0_16:

Version 0.16
============
* Set the DJANGO_SETTINGS_MODULE env variable for sub processes

.. _lava_server_0_15:

Version 0.15
============

* Allow settings.conf to define OPENID_LAUNCHPAD_TEAMS_MAPPING.
* Added configurable OpenID redirect domain support for login.

.. _lava_server_0_14:

Version 0.14
============
* Allow the creating of DataTablesTables backed by sequences rather
  than querysets.

.. _lava_server_0_13:

Version 0.13
============
* Work with Django 1.4
* Only offer to log in with openid if openid is enabled.
* Read SERVER_EMAIL from the settings.conf file.
* Fix a template bug encountered during the password reset process.

.. _lava_server_0_12:

Version 0.12
============

* Merge 0.11.1 release branch
* django-tables2 dependency fix
* ajex_table.html dependency fix

.. _lava_server_0_11_1:

Version 0.11.1
==============

* Drop a copy of lava-utils-interface and add a dependency on the external
  module. This makes lava-server co-installable with lava-utils-interface

.. _lava_server_0_11:

Version 0.11
============
* Add code developed in lava-scheduler for super easy ajax-based pagination of
  tables.

.. _lava_server_0_10_1:

Version 0.10.1
==============

* Enable OPENID_LAUNCHPAD_TEAMS_MAPPING_AUTO
* Avoid evaluating the full queryset when handling request for the
  data in a server-side driven table.

.. _lava_server_0_10:

Version 0.10
============
Add scaffolding for server side pagination of tables
improve error 500 handler page
Merge HeadlesExtension and documentation update
add initial support for data-tables server side code

.. _lava_server_0_9_1:

Version 0.9.1
=============

* Add :class:`lava_server.extension.HeadlessExtension`. This class is helpful
  for writing GUI-less extensions for LAVA.
* Small documentation cleanup
* Initial code reference

.. _lava_server_0_9:

Version 0.9
===========

* Added support for data-tables serverside code
* LAVA Server now depends on django-1.3
* Fixed bugs 915314, 915293

.. _lava_server_0_8_2:

Version 0.8.2
=============

* Fix the default mount point to be ""
* Make extensions aware of mount points

.. _lava_server_0_7_2:

Version 0.7.2
=============

* Fix width of output in scheduler app
* fix wrapping issue with code blocks
* Add some documenation for lava-server
* Make the user menu stay inside the window on FF 3.6
* Use user nickname when real name is empty
* Better compatibility with older firefox
* Add .svg files to manifes
* Fix sign-in/sign-out menu

.. _lava_dashboard_history:

Version History - lava-dashboard
********************************

.. _lava_dashboard_0_29:

Version 0.29
============
* Removed some useless and incomplete functionality
* Added a powermgmt view
* Added abiltiy to compare filter matches
* Fix regression in bundle notifications on filters

.. _lava_dashboard_0_28:

Version 0.28
============
* added Filter's API via XMLRPC

.. _lava_dashboard_0_27:

Version 0.27
============
* say "pass" rather than "Test passed" etc in a few places

.. _lava_dashboard_0_26:

Version 0.26
============
* redo UI related to test results and attachments

.. _lava_dashboard_0_25_2:

Version 0.25.2
==============
* Add the filter subscription mail template to the sdist.

.. _lava_dashboard_0_25_1:

Version 0.25.1
==============
* Add some log messages around sending filter subscription mail.
* Fix a bug with subscribing to filters that do not specify any tests.

.. _lava_dashboard_0_25:

Version 0.25
============
* UI fixes to our filter views

.. _lava_dashboard_0_24:

Version 0.24
============
* Improved user experience when not logged in
* Support 1.4 and 1.5 bundle formats

.. _lava_dashboard_0_23_1:

Version 0.23.1
==============
* Fix filter form media loading.

.. _lava_dashboard_0_23:

Version 0.23
============
* Added XML-RPC call to retrieve test names.
* A better way of basing image reports on filters.
* Somewhat split up the sprawling views.py.

.. _lava_dashboard_0_22_1:

Version 0.22.1
==============
* Urgent release week hacks to base image reports on filters.

.. _lava_dashboard_0_22:

Version 0.22
============
* Add the ability to group and order filter matches by a build number.
* Allow filters to match multiple tests and test cases.

.. _lava_dashboard_0_21:

Version 0.21
============
* Add the concept of a test run filter.

.. _lava_dashboard_0_20:

Version 0.20
============

* make the bundle page robust against the bundle not existing on disk
* ensure table row heights match up in image status view
* few fixes for image status views
* import bundle cleanup

.. _lava_dashboard_0_19:

Version 0.19
============
* Add image status views and models for use by the QA services team.
* Allow linking test runs to launchpad bugs from the image status view.

.. _lava_dashboard_0_18:

Version 0.18
============

* Add link to job details for bundles

.. _lava_dashboard_0_17:

Version 0.17
============

* Fix sorting by column on the test runs in bundle view.
* Display passes & fails in the test run view of a bundle.

.. _lava_dashboard_0_16:

Version 0.16
============

* Make test_result.message respect newlines (bug #850633, Chris
  Johnston)
* Allow viewing images in bundles (bug #877984)

.. _lava_dashboard_0_15:

Version 0.15
============

* Remove the image status view.

.. _lava_dashboard_0_14:

Version 0.14
============

* Convert some tables to use AJAX pagination.
* Add an admin function to support deleting an entire bundle, including
  referenced test runs and results

.. _lava_dashboard_0_13:

Version 0.13
============

* Add :meth:`dashboard_app.BundleStream.can_upload()` that checks if user can
  upload bundles to a specific stream.
* Fix bug that allowed unauthorised users to upload data to any bundle stream
  they could see https://bugs.launchpad.net/lava-dashboard/+bug/955669

.. _lava_dashboard_0_12:

Version 0.12
============

* Remove outdated installation documentation and replace it with basic
  instructions for using pip or direct source code (Thanks to Adam Konarski)
* Built documentation will now include TODO markers (Thanks to Adam Kornacki)
* Add a link to the launchpad FAQ to the documentation
* Fix test suite failing due to fixtures being out of date.

.. _lava_dashboard_0_11:

Version 0.11
============

.. _lava_dashboard_0_10_1:

Version 0.10.1
==============

*  Fix sorting on bundle_list

.. _lava_dashboard_0_10:

Version 0.10.0
==============

*  Fix breadcrumb + titlebar system after moving this responsibilty to lava-server
*  do not limit the lengths of strings in attribute keys and values

.. _lava_dashboard_0_9_3:

Version 0.9.3
=============

* Some minor improvements to the bundle list template

.. _lava_dashboard_0_9_2:

Version 0.9.2
=============
*  Require latest lava-server
*  Make all lava-dashboard views associated with lava-server index breadcrumb
*  Remove the context processor, use front page data feeder and start using application menu
*  Merge fix for database migration dependencies

.. _lava_dashboard_0_9_1:

Version 0.9.1
=============

*  Merge for bug LP:#877859: add measurement information to the json output.
   This change is used by the Android build service.

.. _lava_dashboard_0_6:

Version 0.6
===========

This version was released as 2011.07 in the Linaro monthly release process.

Release highlights:

* New UI synchronized with lava-server, the UI is going to be changed in the
  next release to be more in line with the official Linaro theme. Currently
  most changes are under-the-hood, sporting more jQuery UI CSS.
* New test browser that allows to see all the registered tests and their test
  cases.
* New data view browser, similar to data view browser.
* New permalink system that allows easy linking to bundles, test runs and test results.
* New image status views that allow for quick inspection of interesting
  hardware pack + root filesystem combinations.
* New image status detail view with color-coded information about test failures
  affecting current and historic instances of a particular root filesystem +
  hardware pack combination.
* New image test history view showing all the runs of a particular test on a
  particular combination of root filesystem + hardware pack.
* New table widget for better table display with support for client side
  sorting and searching.
* New option to render data reports without any navigation that is suitable for
  embedding inside an iframe (by appending &iframe=yes to the URL)
* New view for showing text attachments associated with test runs.
* New view showing test runs associated with a specific bundle.
* New view showing the raw JSON text of a bundle.
* New view for inspecting bundle deserialization failures.
* Integration with lava-server/RPC2/ for web APIs
* Added support for non-anonymous submissions (test results uploaded by
  authenticated users), including uploading results to personal (owned by
  person), team (owned by group), public (visible) and private (hidden from
  non-owners) bundle streams.
* Added support for creating non-anonymous bundle streams with
  dashboard.make_stream() (for authenticated users)

.. _lava_dashboard_0_5:

Version 0.5
===========

This version was released as 2011.06 in the Linaro monthly release process.

Release highlights:

* The dashboard has been split into two components, a generic host for server
  side applications (now called the lava-server) and a test result repository
  and browser (now called the lava-dashboard).
* A big dependency revamp has made it possible to install the dashboard (as
  lava-dashboard) straight from the python package index (pypi.python.org).
  This simplifies deployment in certain environments.
* There is now a :ref:`installation` manual that describes how to deploy the
  dashboard from a PPA.
* It is now possible to browse and discover available data views directly form
  the web interface. This makes it easier to create additional reports.

.. _lava_scheduler_history:

Version History - lava-scheduler
********************************

.. _lava_scheduler_0_28:

Version 0.28
============
* remove oob-fd hack

.. _lava_scheduler_0_27:

Version 0.27
============
* prevent offline admin action from touching RETIRED boards
* add a re-submit button

.. _lava_scheduler_0_26:

Version 0.26
============
* Added ability to annotate failures

.. _lava_scheduler_0_25:

Version 0.25
============
* proper remote worker support (without celery)

.. _lava_scheduler_0_24_1:

Version 0.24.1
==============
* Reject jobs with invalid server urls at submission time

.. _lava_scheduler_0_24:

Version 0.24
============
* Added job priority support

.. _lava_scheduler_0_23:

Version 0.23
============
* device version support
* show more than 10 device types in main view

.. _lava_scheduler_0_22_1:

Version 0.22.1
==============
* A little more logging to try to diagnose #1043059.

.. _lava_scheduler_0_22:

Version 0.22
============
* Fix the tests.
* Improve logging in scheduler daemon.
* Make a few fkeys ON DELETE SET NULL.
* Fix job page for jobs with no log file (as opposed to a missing log file).
* update usage doc

.. _lava_scheduler_0_21:

Version 0.21
============
* Ability to hide a device type
* Don't throw errors when job files are missing

.. _lava_scheduler_0_20:

Version 0.20
============
* improved jobs report charting visualization

.. _lava_scheduler_0_19:

Version 0.19
============

* make health job creation more like regular job creation
* updates to support running jobs via celery
* make admin page load faster for editing devices
* add a link on job page to actual device it ran on
* add a report for 5 longest running jobs

.. _lava_scheduler_0_18:

Version 0.18
============

* support linking job details to dashboard bundles

.. _lava_scheduler_0_17_1:

Version 0.17.1
==============

* version .17 didn't have the proper flot libraries in place for the new report

.. _lava_scheduler_0_17:

Version 0.17
============

* Use a more efficient query for the device type overview.
* Add a reports page, with the first reports showing passing/failing
  health jobs & all jobs.

.. _lava_scheduler_0_16:

Version 0.16
============

* Add a RETIRED status for boards.
* Return a HTTP 403 not 404 when accessing a job that the logged in
  user does not have permission to see.

.. _lava_scheduler_0_15:

Version 0.15
============

* Add a view showing the status of each device type.

.. _lava_scheduler_0_14:

Version 0.14
============

* Add resubmit_job to the API
* Add support for looping of health care jobs

.. _lava_scheduler_0_13:

Version 0.13
============

* Allow job files to specify addresses to email on completion
  (possibly only unsuccessful completion).

.. _lava_scheduler_0_12_1:

Version 0.12.1
==============

* Enforce limits on how long jobs can run for and how large log files
  can grow to in the scheduler monitor.
* When killing off a process, escalate through SIGINT, SIGTERM,
  SIGKILL signals.

.. _lava_scheduler_0_12:

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

.. _lava_scheduler_0_11:

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

.. _lava_scheduler_0_10.1:

Version 0.10.1
==============
* fix duplicate names for some views

.. _lava_scheduler_0_10:

Version 0.10
============
* Introduce health check jobs
  * These are defined on the device type and run when a board is put
    online or when no health check job has run for 24 hours
  * There are also views to just look at the health status of a board
    or the lab as a whole.
* The scheduler monitor is more reliably told where to log.
* Make all tables paginated via server-side ajax magic.

.. _lava_scheduler_0_9:

Version 0.9
===========
* Make alljobs paginated so that it will load very quickly
* handle invalid values for start in job_output
* record device status transitions
* ask for a reason when offlining/onlining a board
* display transitions on the device page

.. _lava_scheduler_0_8:

Version 0.8
===========
* improvements to the docs from Adam Konarski
* make submit_job give slightly more useful permission errors
* restore code to allow submission of results to a private bundle
* reject unknown jobs at submit time

.. _lava_scheduler_0_7_3:

Version 0.7.3
=============
* Don't assume dispatcher log files contain valid unicode (#918954)
* Include static assets in the sdist (multiply reported as: #919079,
  #919047, #917393)

.. _lava_scheduler_0_7_2:

Version 0.7.2
=============
* Revert 'allow results to be submitted to non-anonymous bundle streams' as it
  caused the entire job to be deleted when it completed.

.. _lava_scheduler_0_7_1:

Version 0.7.1
=============
* Allow results to be submitted to non-anonymous bundle streams
* Improved job view when log files are missing
* Fixed some issues with device tags and postgres

.. _lava_scheduler_0_7_0:

Version 0.7.0
=============

*  Add support for device tags in the scheduler
*  Overhaul of the job view
*  Fix unit tests

.. _lava_scheduler_0_5_5:

Version 0.5.5
=============

* Add some docs for lava-scheduler
