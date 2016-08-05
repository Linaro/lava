.. _results_intro:

Introduction to Results in LAVA
*******************************

What do you mean by a result?

Do you want to track measurements or simple pass:fail

Mapping of the results is determined by the lava test shell definition.

include data_export

Introduction to Queries in LAVA

to identify interesting results out of the full set of test jobs
to extract results based on metadata provided by the test writers or bots.
    build numbers / sequences
    branch names
    teams

to provide data for comparison in notifications

What you get out of queries is based on how well the incoming test job
submission data is organised.

Introduction to Charts in LAVA

* generic
* overviews

Use data export for customised handling which can deliver:

* useful tooling
    * git bisect support
* customised charts
* feeds into existing interfaces via transforms.


.. toctree::
   :hidden:
   :maxdepth: 1

   lava-queries-charts.rst
