.. index:: export

.. _data_export:

Exporting data out of LAVA
##########################

LAVA supports two methods of extracting data: the :ref:`rest_api` and
:ref:`xml_rpc`. Results are made available while the job is running via
the results API. Direct links from the test log UI are not populated
until after the job completes, due to performance issues.

In addition to these methods of pulling data out of LAVA, there are
also two methods for pushing information about its activity:
:ref:`notifications <notification_summary>` and :ref:`publishing events
<publishing_events>`.

.. index:: rest api

.. _rest_api:

REST API
********

.. include:: restapi.rsti

.. index:: xmlrpc

.. _xml_rpc:

XML-RPC
*******

Lots of `methods <../../../api/help>`_ are available to query various
information in LAVA.

.. warning:: When using XML-RPC to communicate with a remote server,
   check whether ``https://`` can be used to protect the
   token. ``http://`` connections to a remote XML-RPC server will
   transmit the token in plain-text. Not all servers have ``https://``
   configured. If a token becomes compromised, log in to that LAVA
   instance and delete the token before creating a new one.

The general structure of an XML-RPC call can be shown in this python
snippet:

.. code-block:: python

  # Python3
  import json
  import xmlrpc.client

  config = json.dumps({ ... })
  server=xmlrpc.client.ServerProxy("http://username:API-Key@localhost:8001/RPC2/")
  jobid=server.scheduler.submit_job(config)

XML-RPC can also be used to query data anonymously:

.. code-block:: python

  # Python3
  import xmlrpc.client

  server = xmlrpc.client.ServerProxy("http://sylvester.codehelp/RPC2")
  print server.system.listMethods()

Individual XML-RPC commands are documented on the `API Help
<../../../api/help>`_ page.

.. index:: notifications - summary

.. _notification_summary:

User specified notifications
****************************

Users can request notifications about submitted test jobs by adding a
notify block to their test job submission.

The basic setup of the notifications in job definitions will have
**criteria**, **verbosity**, **recipients** and **compare** blocks.

* **Criteria** tell the system when the notifications should be sent

* **Verbosity** tells the system how much detail should be included in
  the notification

* **Recipients** tells the system where to send the notification, and
  how

* **Compare** is an optional block that allows the user to request
  comparisons between results in this test and results from previous
  test

Here is an example notification setup. For more detailed information
see :ref:`notifications`.

Example test job notification
=============================

.. include:: examples/test-jobs/qemu-notify.yaml
   :code: yaml
   :start-after: # notify block
   :end-before: # ACTION_BLOCK


.. index:: publishing events, event notifications

.. _publishing_events:

Event notifications
*******************

Event notifications are handled by the ``lava-publisher`` service on
the master. By default, event notifications are disabled.

.. note:: ``lava-publisher`` is distinct from the :ref:`publishing API
   <publishing_artifacts>`. Publishing **events** covers status
   changes for devices and test jobs. The publishing API covers
   copying **files** from test jobs to external sites.

http://ivoire.dinauz.org/linaro/bus/ is the home of ``ReactOWeb``. It
shows an example of the status change information which can be made
available using ``lava-publisher``. Events include:

* metadata on the instance which was the source of the event; and
* description of a status change on that instance.

Event notifications are disabled by default and **must** be configured
before being enabled.

.. seealso:: :ref:`configuring_event_notifications`


.. _example_event_metadata:

Example metadata
================

* Date and time
* Topic (for example ``org.linaro.validation.staging.device``)
* Message UUID
* Username

The ``topic`` field is configurable by lab administrators. Its
intended use is to allow receivers of events to filter incoming
events.

.. _event_types:

Event notification types
========================

* :ref:`Device event <example_device_event>` notifications are emitted
  automatically when a device changes state (e.g. Idle to Running) or
  health (e.g. Bad to Unknown). Some events are related to testjobs,
  some are due to admin action.

* :ref:`Testjob event <example_testjob_event>` notifications are
  emitted automatically when a testjob changes state (e.g. Submitted to
  Running).

* :ref:`System event <example_log_event>` notifications are emitted
  automatically when workers change state.

* :ref:`Test Shell event <example_testshell_event>` notifications are
  emitted only when requested within a Lava Test Shell by a test writer
  and contain a customized message.

.. _example_device_event:

Example device notification
===========================

.. code-block:: python

 {
    "device": "staging-qemu05",
    "device_type": "qemu",
    "health_status": "Pass",
    "job": 156223,
    "pipeline": true,
    "status": "Idle"
 }

.. _example_testjob_event:

Example testjob notification
============================

.. code-block:: python

    {
        'health_check': False,
        'description': 'QEMU pipeline, first job',
        'state': 'Scheduled',
        'visibility': 'Publicly visible',
        'priority': 50,
        'submitter': 'default',
        'job': 'http://calvin.codehelp/scheduler/1995',
        'health': 'Unknown',
        'device_type': 'qemu',
        'submit_time': '2018-05-17T11:49:56.336847+00:00',
        'device': 'qemu01'
    }

.. _example_log_event:

Example log event notification
==============================

::

 2018-05-17T12:12:15.238331 .codehelp.calvin.worker lavaserver - [worker01] state=Online health=Active

.. _example_testshell_event:

Example test event notification
===============================

.. FIXME: this needs to be much more like the test job event.

Test writers can cause event notifications to be emitted under the
control of a Lava Test Shell. This example uses an inline test
definition.

.. include:: examples/test-jobs/qemu-test-events.yaml
     :code: yaml
     :start-after:       name: smoke-tests
     :end-before:    - repository: https://git.linaro.org/lava-team/lava-functional-tests.git

.. FIXME: change the output to what would be shown by lavacli wait

::

 2018-05-17T11:51:22.542416 org.linaro.validation.event lavaserver - {"message": "demonstration", "job": "1995"}

.. _example_event_notification_client:

Write your own event notification client
========================================

It is quite straightforward to communicate with ``lava-publisher`` to
listen for events. This example code shows how to connect and
subscribe to ``lava-publisher`` job events. It includes a simple
main function to run on the command line if you wish:

.. code-block:: shell

 python zmq_client.py -j 357 --hostname tcp://127.0.0.1:5500 -t 1200

zmq_client.py script:

.. literalinclude:: examples/source/zmq_client.py
   :language: python
   :start-after: # START_CLIENT
   :end-before: # END_CLIENT

Download or view the complete example:
`examples/source/zmq_client.py
<examples/source/zmq_client.py>`_

If you are interested in using event notifications for a custom
:term:`frontend`, you may want also to look at the code for the
ReactOWeb example website: https://github.com/ivoire/ReactOWeb

Submit a job and wait on notifications
======================================

A common request from LAVA users is the ability to submit a test job,
wait for the job to start and then monitor it directly as it
runs. Recent versions of :ref:`lavacli` support this directly.
