Version History
***************

.. _version_0_10_1:

Version 0.10.1
==============

*  Fix sorting on bundle_list

.. _version_0_10_0:

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

