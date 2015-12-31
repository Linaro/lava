.. _result_queries:

LAVA result visualization
#########################

LAVA Queries
************

This is documentation for the new queries app, still in **development** stage.

It is part of the new :ref:`dispatcher_design`.

Current features include querying following object sets:

* Test jobs

* Test cases

* Test suites

Cached queries:

Queries can be live or cached. Cached queries data can be refreshed either
through UI or via the XMLRPC API call by creator or someone in group assigned
to the query.
Please keep in mind, live queries are executed whenever someone visits the
query page or refreshes it. Viewing a live query will usually take longer than
a cached query, sometimes markedly longer. Live queries can stress the LAVA
server which can cause the query to timeout.

When adding/updating and removing conditions, query is **not** automatically
updated. This needs to be done either through UI after updating the conditions
or via XMLRPC.

Authorization and admin
=======================

Queries which are not published are visible exclusively to the query owner.
When query is published, it's results are generally visible to all users,
permitting the user has access to the jobs which provide the results.
All the authorization is managed through test jobs visibility rules,  meaning
that individual results will be omitted in the query display list depending on
user authorization to see the specific jobs.

Besides owner of the specific query, administration of the query can be allowed
to a group in the system as well, through the 'Group edit permission' option.
Note that this can be done only after the query is published.

Queries can be organized in 'query groups' which is visible only in the query
listing page, via 'query group label' option.

Conditions
==========

You can add multiple conditions to each query where the query results must
satisfy **all** conditions in order to be displayed.
Conditions can span through multiple object sets so for example user can query
the Jobs that have test cases in which particular field satisfies a condition.
List of supported fields which can be used as condition field is available
as autocomplete list in the condition 'Field name' field.
You can also add conditions with fields in the object set which is queried
(i.e. if test jobs are query object set user can add conditions such as
submitter, device, priority, status...).

It is also possible to add conditions using custom metadata. Since metadata can
contain custom field names, keep in mind that the query might not return
desired results since those field names are not validated when adding
conditions.
This also means you can add the condition even if the field in the metadata is
is not yet present in the system.

.. _query_by_url:

Query by URL
============

The ability to add conditions through URL is now enabled. User can add as many
conditions as possible through URL but must also specify the object set which
is to be queried.

The query string format looks like this::

  entity=$(object_name)&conditions=$(object_name)__$(field_name)__$(operator)__$value,$(object_name)__$(field_name)__$(operator)__$value,...

.. note:: object_name can be omitted if it's the same as the query object set.
	  Operator is one of the following - exact, iexact, contains, gt, lt.


`Example Query by URL <https://playground.validation.linaro.org/results/query/+custom?entity=testjob&conditions=testjob__priority__exact__Medium,testjob__submitter__contains__code>`_

Once the query by URL results are displayed, user can create saved query from
these conditions, which will be automatically added to the new query.

LAVA Charts
***********

This is documentation for the new charts app, still in **development** stage.

It is part of the new :ref:`dispatcher_design`.

LAVA charts represent the visual representation for the Queries app.
