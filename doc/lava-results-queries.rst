.. _result_queries:

Lava Queries
############

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

Conditions:

You can add multiple conditions to each query where the query results must
satisfy **all** conditions in order to be displayed.
Conditions can span through multiple object sets so for example user can query
the Jobs that have test cases in which particular field satisfies a condition.
You can also add conditions with fields in the object set which is queried
(i.e. if test jobs are query object set user can add conditions such as
submitter, device, priority, status...).

It is also possible to add conditions using custom metadata. Since metadata can
contain custom field names, keep in mind that the query might not return
desired results since those field names are not validated when adding
conditions.
This also means you can add the condition even if the field in the metadata is
is not yet present in the system.

Query by URL
************

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
