Version History
***************

.. _version_0_29:

Version 0.29
============
* Unreleased

.. _version_0_28:

Version 0.28
============
* added Filter's API via XMLRPC

.. _version_0_27:

Version 0.27
============
* say "pass" rather than "Test passed" etc in a few places

.. _version_0_26:

Version 0.26
============
* redo UI related to test results and attachments

.. _version_0_25_2:

Version 0.25.2
==============
* Add the filter subscription mail template to the sdist.

.. _version_0_25_1:

Version 0.25.1
==============
* Add some log messages around sending filter subscription mail.
* Fix a bug with subscribing to filters that do not specify any tests.

.. _version_0_25:

Version 0.25
============
* UI fixes to our filter views

.. _version_0_24:

Version 0.24
============
* Improved user experience when not logged in
* Support 1.4 and 1.5 bundle formats

.. _version_0_23_1:

Version 0.23.1
==============
* Fix filter form media loading.

.. _version_0_23:

Version 0.23
============
* Added XML-RPC call to retrieve test names.
* A better way of basing image reports on filters.
* Somewhat split up the sprawling views.py.

.. _version_0_22_1:

Version 0.22.1
==============
* Urgent release week hacks to base image reports on filters.

.. _version_0_22:

Version 0.22
============
* Add the ability to group and order filter matches by a build number.
* Allow filters to match multiple tests and test cases.

.. _version_0_21:

Version 0.21
============
* Add the concept of a test run filter.

.. _version_0_20:

Version 0.20
============

* make the bundle page robust against the bundle not existing on disk
* ensure table row heights match up in image status view
* few fixes for image status views
* import bundle cleanup

.. _version_0_19:

Version 0.19
============
* Add image status views and models for use by the QA services team.
* Allow linking test runs to launchpad bugs from the image status view.

.. _version_0_18:

Version 0.18
============

* Add link to job details for bundles

.. _version_0_17:

Version 0.17
============

* Fix sorting by column on the test runs in bundle view.
* Display passes & fails in the test run view of a bundle.

.. _version_0_16:

Version 0.16
============

* Make test_result.message respect newlines (bug #850633, Chris
  Johnston)
* Allow viewing images in bundles (bug #877984)

.. _version_0_15:

Version 0.15
============

* Remove the image status view.

.. _version_0_14:

Version 0.14
============

* Convert some tables to use AJAX pagination.
* Add an admin function to support deleting an entire bundle, including
  referenced test runs and results

.. _version_0_13:

Version 0.13
============

* Add :meth:`dashboard_app.BundleStream.can_upload()` that checks if user can
  upload bundles to a specific stream.
* Fix bug that allowed unauthorised users to upload data to any bundle stream
  they could see https://bugs.launchpad.net/lava-dashboard/+bug/955669

.. _version_0_12:

Version 0.12
============

* Remove outdated installation documentation and replace it with basic
  instructions for using pip or direct source code (Thanks to Adam Konarski)
* Built documentation will now include TODO markers (Thanks to Adam Kornacki)
* Add a link to the launchpad FAQ to the documentation
* Fix test suite failing due to fixtures being out of date.

.. _version_0_11:

Version 0.11
============

.. _version_0_10_1:

Version 0.10.1
==============

*  Fix sorting on bundle_list

.. _version_0_10:

Version 0.10.0
==============

*  Fix breadcrumb + titlebar system after moving this responsibilty to lava-server
*  do not limit the lengths of strings in attribute keys and values

.. _version_0_9_3:

Version 0.9.3
=============

* Some minor improvements to the bundle list template

.. _version_0_9_2:

Version 0.9.2
=============
*  Require latest lava-server
*  Make all lava-dashboard views associated with lava-server index breadcrumb
*  Remove the context processor, use front page data feeder and start using application menu
*  Merge fix for database migration dependencies

.. _version_0_9_1:

Version 0.9.1
=============

*  Merge for bug LP:#877859: add measurement information to the json output.
   This change is used by the Android build service.

.. _version_0_6:

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

.. _version_0_5:

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

