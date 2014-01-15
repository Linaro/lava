.. index:: export

.. _data_export:

Exporting data out of LAVA
##########################

A :term:`result bundle` from running a particular LAVA test job becomes
aggregated into a :term:`bundle stream` which forms the basis of data
analysis and reporting in LAVA, using :ref:`filter` and :ref:`image_reports`.

In each case, the structure of the data complies with the current
Dashboard Bundle Format and the details of this format are visible
in the Bundle Viewer tab when viewing the bundle in LAVA.

lava-tool
*********

``lava_tool`` can download any :term:`result bundle` and instructions
are given on each bundle page giving the command to use for that
bundle. Bundles are downloaded as JSON and can be analyzed using any
tool which can parse JSON, including python and perl.

See the :ref:`lava_tool`

Once the bundle has been downloaded, data from the bundle can be used
with other export calls to obtain more detail.

XML-RPC
*******

LAVA uses XML-RPC to communicate between dispatchers and the server
and `methods <../../api/help>`_ are available to query various information
in LAVA.

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

Example
=======

This query returns a list of all bundle streams on the validation.linaro.org::

 import xmlrpclib
 import simplejson

 server = xmlrpclib.ServerProxy("http://validation.linaro.org/RPC2")
 print server.dashboard.streams()

Assuming that you are interested in a :term:`bundle stream` which is
public and anonymous and has a pathname of ``/anonymous/codehelp/``, the
bundles within that stream can also be queried::

 import xmlrpclib
 import simplejson

 server = xmlrpclib.ServerProxy("http://validation.linaro.org/RPC2")
 stream_path="/anonymous/codehelp/"
 bundles = server.dashboard.bundles(stream_path)

A specific bundle is addressed using the ``content_sha1`` value which
returns a JSON string::

 latest = len(bundles) - 1
 sha1 = bundles[latest]['content_sha1']
 bundle = simplejson.loads(server.dashboard.get(sha1)['content'])

At this point, you have the same information as would be obtained using
``lava-tool`` already in memory, indeed you could use ``lava-tool`` to
download any bundle when you know the bundle stream path and the bundle
``content_sha1``.

To output just the data about test runs which are included in the bundle,
use this python snippet::

 for test in bundle['test_runs']:
     print test['test_results']

CSV
***

LAVA also supports Comma Separated Value exports directly from the LAVA
page for the bundle or bundle stream.

CSV data can also be downloaded by using a simple ``export`` URL:

https://validation.linaro.org/dashboard/streams/anonymous/codehelp/bundles/export

Specific bundles can be exported using the ``content_sha1``:

https://validation.linaro.org/dashboard/streams/anonymous/codehelp/bundles/795d8b77493e3a0507af1a7160368fb53b2823df/export

Within a bundle, test runs can be exported using the Test Run UUID 
(which is the same as the analyzer_assigned_uuid in the previous export)

https://validation.linaro.org/dashboard/streams/anonymous/codehelp/bundles/795d8b77493e3a0507af1a7160368fb53b2823df/97cb22fb-73eb-4e08-90a6-317c0ad5e63a/export
