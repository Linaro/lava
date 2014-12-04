Using tables in LAVA
********************

LAVA presents much of the data about jobs, devices, results and tasks
inside tables. The length of a table can be controlled, the table
can be sorted by selected columns and the data itself can be searched.
All options can be controlled from the query string in the browser
address bar. This allows particular views of a table to be shared as
links. See :ref:`time_queries`.

For pages which only contain a single table, the number of rows displayed
in each page of data is controlled via the **length** parameter. For
convenience, there is a drop down box on the left of each table where the
table length can be selected.

Table search support
====================

Unless specified explicitly, all searches are case-sensitive.

Simple text search
------------------

The search box above each table allows arbitrary text strings to be
used as filters on the data within the table. Each table has support for
matching simple text strings against certain columns within the table
and these searches are additive - the data in the row will be included
in the results if the text matches any of the search fields.

The fields which support text search are listed above each table.

.. _time_queries:

Custom table queries
--------------------

Some tables also support customised queries on specific fields, typically
these will be **time based fields** like *submit_time*, *end_time* and
*duration*. These queries allow a specific function to be called within
the filter to match only results where the timestamp occurred within
the specified number of minutes, hours or days, relative to the current
time on the server.

The queries supported by a table are listed above the table, along with
details of whether that query is based on minutes, hours or days.

.. note:: Time based queries will always take the current time on the
   server into account, so links containing such queries may not give the
   same results when viewed at a later time.

Time based queries can take calculations in the query string as well,
e.g. ``end_time`` is based on hours, so ``?end_time=4*24`` matches
``end_time`` within the last 4 days (the search summary will still show
the ``4*24``.)

.. _discrete_queries:

Exclusive table searches
------------------------

Fields used in simple text searches can also be used as exclusive searches
by adding the exclusive search field to the querystring. The data in
the row will be included in the results only if the text matches all of the
search fields::

 ?device=mx5&length=25&description=ARMMP&status=Incom

This querystring would only show rows where the *device hostname* contains
``mx5`` **and** the *description* contains ``ARMMP`` **and** the *status* of
the job contains ``Incom``, therefore showing up to 25 results for jobs
on such devices with that description which finished with a status of
Incomplete.

.. note:: Exclusive searches are not supported via the search box in
          the table header. Add to the querystring directly. Exclusive
          text search cannot be combined with simple text search. Replace
          the **search** variable in the querystring with the closest
          discrete query term, e.g. description.

The fields which support exclusive search are listed above each table.

Other filters
-------------

Individual tables may also provide filters via javascript or other
support.

Resetting a table
-----------------

The breadcrumb link should take you back to the default table. Alternatively,
clear the querystring in the browser address bar manually.

Unavailable entries
-------------------

Certain tables may contain data relating to a :term:`hidden device type`
which would show as ``Unavailable`` if the user viewing the table does
not own a device of this type. It is not possible to search these tables
for details of the hidden type and the ``Unavailable`` label itself does
not match as a search term.
