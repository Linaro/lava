.. index:: export

.. _data_export:

Exporting data out of LAVA
##########################

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
