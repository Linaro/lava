.. index:: using favorite jobs in LAVA

.. _using_favorite_jobs:

Favorite jobs in LAVA
*********************

LAVA supports the concept of ``favorite jobs``, to help users navigate to their
point of focus in a streamlined manner. One can mark individual LAVA jobs as favorite; and be able to review the list of their favorite jobs in a dedicated web page.
In addition, users can overview other users' favorite jobs by using a simple auto-complete user search.

.. note:: Favorite jobs feature are not available via XMLRPC nor REST API in LAVA. It is only available in the web user interface.

Marking job as your favorite
============================

In the job detail page, i.e. ``${host}/scheduler/job/4066005`` navigate to the ``Actions`` dropdown and select ``Add to favorites``. This will mark this particular job as you favorite and reload the page. Subsequently, if the job is already in your favorite list, you can remove it from your favorites by selecting ``Remove from favorites`` on the same page in the same ``Actions`` dropdown.


My favorite jobs page
=====================

In the upper right corner in the header of the page, click the dropdown with your username. A list of options appear and you can navigate to the ``Favorite jobs`` page. If you have selected some jobs as you favorite, a list of jobs will be displayed. You can access any job details page from this table, as well as overview jobs details in the list.


Other users' favorite jobs
==========================

In the ``Favorite jobs`` page you can see the link ``Favorite jobs by user``. When you click it, a dialog appears with a username field which is auto-complete and filrters the users in you LAVA server. Start typing the username of the user which faorite jobs you'd like to see and select that user. Upon clicking ``Save`` button, a page will be reloaded showing the list of the favorite jobs of this user.


