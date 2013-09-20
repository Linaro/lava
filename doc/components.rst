LAVA Components
===============

`LAVA Server <http://lava-server.readthedocs.org/>`_
----------------------------------------------------

The server is the core framework used by LAVA web apps.  It's based on
Django and provides the main web interface to LAVA via extensions.

`LAVA Dashboard <http://lava-dashboard.readthedocs.org/>`_
----------------------------------------------------------

The dashboard is the primary UI for storing and viewing results. It accepts
results as defined by a well-defined
`JSON format <http://linaro-dashboard-bundle.readthedocs.org/en/latest/index.html>`_.
The dashboard takes these results and stores them in a normalized
database to provide efficient access for its UI views.


`LAVA Scheduler <http://lava-scheduler.readthedocs.org/>`_
----------------------------------------------------------

The dcheduler is responsible for understanding what test targets are available
to LAVA and what state they are in (running, idle, offline, etc). It accepts
job requests in a
`JSON format <http://lava-dispatcher.readthedocs.org/en/latest/jobfile.html>`_ [1].
After accepting a job, the scheduler will find an available target to
execute it on.

1\. **NOTE**: *This is a different format than the dashboard's JSON result format.*

`LAVA Dispatcher <http://lava-dispatcher.readthedocs.org/>`_
------------------------------------------------------------

The dispatcher is used by the scheduler to perform the actual job. Its
responsible for talking directly to the target being tested normally over
a serial console interface.

`LAVA Test <http://lava-test.readthedocs.org/>`_
------------------------------------------------

LAVA Test is a simple test execution framework for Ubuntu based images.
It's primary function is to provide a consistent interface for installing
testsuites, running them, and parsing their results into a form
that can be consumed by the LAVA Dashboard.

This component is in the process of being deprecated in favor of using
`lava-test-shell <http://lava-dispatcher.readthedocs.org/en/latest/jobfile.html#using-lava-test-shell>`_.

`LAVA Android Test <http://lava-android-test.readthedocs.org/>`_
----------------------------------------------------------------

This component was developed to provide a testing harness for Android based
images. Its quite similar to lava-test but uses Android's ADB.

This component is also in the process of being deprecated in favor of using
`lava-test-shell <http://lava-dispatcher.readthedocs.org/en/latest/jobfile.html#using-lava-test-shell>`_.

