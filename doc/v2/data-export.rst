.. index:: export

.. _data_export:

Exporting data out of LAVA
##########################

LAVA supports two methods of extracting data: the :ref:`rest_api` and
:ref:`xml_rpc`. Results are made available while the job is running;
this is a new feature compared to LAVA V1 where results were only
published at the end of a job.

In addition to these methods of pulling data out of LAVA, there are
also two methods for pushing information about its activity:
notifications and :ref:`publishing events <publishing_events>`.

.. index:: rest api

.. _rest_api:

REST API
********

.. include:: restapi.rsti

.. index:: xmlrpc

.. _xml_rpc:

XML-RPC
*******

Lots of `methods <../../api/help>`_ are available to query various
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

  import xmlrpclib
  import simplejson

  config = simplejson.dumps({ ... })
  server=xmlrpclib.ServerProxy("http://username:API-Key@localhost:8001/RPC2/")
  jobid=server.scheduler.submit_job(config)

XML-RPC can also be used to query data anonymously:

.. code-block:: python

  import xmlrpclib

  server = xmlrpclib.ServerProxy("http://sylvester.codehelp/RPC2")
  print server.system.listMethods()

Individual XML-RPC commands are documented on the `API Help
<../../api/help>`_ page.

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

Example metadata
================

* Date and time
* Topic (for example ``org.linaro.validation.staging.device``)
* Message UUID
* Username

The ``topic`` field is configurable by lab administrators. Its
intended use is to allow receivers of events to filter incoming
events.

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

Event notifications are disabled by default and **must** be configured
before being enabled.

.. seealso:: :ref:`configuring_event_notifications`

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
runs. Recent versions of :ref:`lava_tool` support this directly - look
at its `source code <https://git.linaro.org/lava/lava-tool.git/>`_ if
you want to do something similar in your own code.
