.. index:: export

.. _data_export:

Exporting data out of LAVA
##########################

LAVA supports two methods of extracting data and results are available
whilst the job is running, XML-RPC and the REST API.

In addition, LAVA has two methods of pushing notifications about activity
within LAVA, notifications and publishing events.

.. index:: rest api

.. _rest_api:

REST API
********

.. include:: restapi.rsti

.. index:: xmlrpc

.. _xml_rpc:

XML-RPC
*******

LAVA uses XML-RPC to communicate between dispatchers and the server
and `methods <../../api/help>`_ are available to query various information
in LAVA.

.. warning:: When using XML-RPC to communicate with a remote server,
             check whether ``https://`` can be used to protect the token.
             ``http://`` connections to a remote XML-RPC server will
             transmit the token in plaintext. Not all servers have
             ``https://`` configured. If a token becomes compromised,
             log in to that LAVA instance and delete the token before
             creating a new one.

The general structure of an XML-RPC call can be shown in this python
snippet::

  import xmlrpclib
  import json

  config = json.dumps({ ... })
  server=xmlrpclib.ServerProxy("http://username:API-Key@localhost:8001/RPC2/")
  jobid=server.scheduler.submit_job(config)

XML-RPC can also be used to query data anonymously::

  import xmlrpclib
  server = xmlrpclib.ServerProxy("http://sylvester.codehelp/RPC2")
  print server.system.listMethods()

Individual XML-RPC commands are documented on the `API Help <../../api/help>`_
page.

.. index:: notifications

.. _notifications:

User specified notifications
****************************

Users can have notifications about submitted test jobs by adding a notify
block to the test job submission.

To use IRC notifications, the user of the notification **must** have already
configured the ``IRC settings`` in their own profile on the instance, by
logging in and following the **Profile** link from the menu:

.. image:: images/profile-menu.png

.. FIXME: more content needed.

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

Event notifications are handled by the ``lava-publisher`` service on the
master. By default, event notifications are disabled.

.. note:: ``lava-publisher`` is distinct from the :ref:`publishing API
   <publishing_artifacts>`. Publishing events covers status changes for devices
   and test jobs. The publishing API covers copying files from test jobs to
   external sites.

http://ivoire.dinauz.org/linaro/bus/ is an example of the status change
information which can be made available using ``lava-publisher``. Events
include:

* metadata on the instance which was the source of the event
* description of a status change on that instance.

Example metadata
================

* Date and time
* Topic, for example ``org.linaro.validation.staging.device``
* the uuid of the message
* Username

The topic is intended to allow receivers of the event to use filters on
incoming events and is configurable by the admin of each instance.

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

Event notifications are disabled by default and **must** be configured before
being enabled.

.. seealso:: :ref:`configuring_event_notifications`

Work is ongoing to create a simple ``lava-client`` library which can be used to
connect to the push notifications and replace the need to poll on XML-RPC. In
the meantime, if you are interested in using event notifications for a custom
:term:`frontend`, you might want to look at the code for the example website:
https://github.com/ivoire/ReactOWeb

