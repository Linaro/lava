.. _result_queries:

Lava Queries
############

This is documentation for the new queries app, still in **development** stage.

It is part of the new :ref:`dispatcher_design`.

Current features include querying following object sets:

* Test jobs

* Test cases

* Test sets

* Test suites

One can add multiple conditions to each query where the query results must
satisfy **all** conditions in order to be displayed.
Conditions are currently limited only to fields in the object set which is
queried (i.e. if test jobs are query object set user can add conditions such
as submitter, device, priority, status..., but not fields from other objects).

Query by URL
************

The ability to add conditions through URL is now enabled. User can add as many
conditions as possible through URL but must also specify the object set which
is to be queried.

The query string format looks like this::

  entity=$(object_name)&conditions=$(object_name)__$(field_name)__$(operator)__$value,$(object_name)__$(field_name)__$(operator)__$value,...

.. note:: object_name can be ommited if it's the same as the query object set.
	  Operator is one of the following - exact, iexact, contains, gt, lt.


`Example Query by URL <https://playground.validation.linaro.org/results/query/+custom?entity=testjob&conditions=testjob__priority__exact__Medium,testjob__submitter__contains__code>`_

Once the query by URL results are displayed, user can create saved query from
these conditions, which will be automatically added to the new query.
