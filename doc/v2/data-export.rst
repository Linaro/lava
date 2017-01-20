.. index:: export

.. _data_export:

Exporting data out of LAVA
##########################

LAVA supports two methods of extracting data and results are available whilst
the job is running, XML-RPC and the REST API.

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

LAVA uses XML-RPC to communicate between dispatchers and the server and
`methods <../../api/help>`_ are available to query various information in LAVA.

.. warning:: When using XML-RPC to communicate with a remote server, check
   whether ``https://`` can be used to protect the token. ``http://``
   connections to a remote XML-RPC server will transmit the token in plaintext.
   Not all servers have ``https://`` configured. If a token becomes
   compromised, log in to that LAVA instance and delete the token before
   creating a new one.

The general structure of an XML-RPC call can be shown in this python snippet::

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

.. index:: notifications_summary

.. _notification_summary:

User specified notifications
****************************

Users can have notifications about submitted test jobs by adding a notify block
to the test job submission.

The basic setup of the notifications in job definitions will have **criteria**,
**verbosity**, **recipients** and **compare** blocks.

**Criteria** tells the system when the notifications should be sent and

**verbosity** will tell the system how detailed the email notification should
be.

Recipient methods accept **email** and **irc** options.

Here's the example notification setup. For more information please go to
:ref:`notifications`.

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

Write your own event notification client
========================================

It is quite straight forward to get events from ``lava-publisher``.

Users can embed this example piece code in their own local client app to
listen to the job and/or device events and act according to the return data.

This script can also be used standalone from command line but is otherwise only
an example.

.. code-block:: bash

 python zmq_client.py -j 357 -p tcp://127.0.0.1:5500 -t 1200


zmq_client.py script:

.. literalinclude:: examples/source/zmq_client.py
   :language: python
   :start-after: # START_CLIENT
   :end-before: # END_CLIENT

`Download or view zmq_client.py <examples/source/zmq_client.py>`_

If you are interested in using event notifications for a custom :term:`frontend`,
you might want also to look at the code for the ReactOWeb example website:
https://github.com/ivoire/ReactOWeb

Extending the client to submit and wait
---------------------------------------

You may want to expand this example to use the :ref:`XML-RPC <xml_rpc>` API to
submit a testjob and retrieve the publisher port at the same time. It is up to
you to decide how to protect the token used for the submission:

.. code-block:: python

  import xmlrpclib

  username = "USERNAME"
  token = "TOKEN_STRING"
  hostname = "HOSTNAME"
  scheme = "https"  # or http if https is not available for this instance.
  server = xmlrpclib.ServerProxy("%s://%s:%s@%s/RPC2" % (scheme, username, token, hostname))
  port = server.scheduler.get_publisher_event_socket()

At this point, ``port`` will be ``5500`` or whatever the instance has
configured as the port for event notifications. The publisher details can then
be constructed as:

.. code-block:: python

  publisher = "tcp://%s:%s" % (hostname, port)

If the YAML test job submission is in a file called ``job.yaml``, the example
can be continued to load and submit this test job:

.. code-block:: python

    with open('job.yaml', 'r') as filedata:
        data = filedata.read()
    job_id = server.scheduler.submit_job(data)

If the job uses :ref:`multinode` then ``job_id`` will be a list and you will
need to decide which job to monitor.
