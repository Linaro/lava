Adding Extensions to LAVA Server
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

LAVA Server can be used as the base for further extensions. Extensions
currently exist for things like adding scheduler support, a dashboard
interface, and additional views of test data. Extensions can add further data
models, menus, and views, and even APIs to the existing LAVA Server framework.

Extensions are essentially just a django app. They hook into LAVA Server using
an pkg_resources entry points machinery. For a simple example of adding an
extension, see the 'demo' subdirectory in the lava-server source repository.

setup.py
********

Your setup.py will need to add entry points for lava_server.extensions
for the extension you wish to add

.. code-block:: python

    entry_points="""
    [lava_server.extensions]
    demo = demo_app.extension:DemoExtension
    """,

The *DemoExtension* class will be defined below.

The extension class
*******************

The other thing your django extension to LAVA Server will need is a class that
implements the :class:`~lava_server.extension.IExtension` interface. This class
defines the properties and methods that are needed for LAVA Server to include
your extension.

You may find a small demo extension in the source tree. You can use that as a
base for your own code.

.. literalinclude:: ../../demo/demo_app/extension.py

Adding new XML-RPC methods
**************************

As previously mentioned, the LAVA Server XML-RPC API can be extended with new
methods using LAVA Server extensions.  In the *demo_app* example we have been
looking at, a new method called *demoMethod()* is added to the API and is
automatically added under a namespace called *demo*.  It uses *ExposedAPI* from
*linaro_django_xmlrpc.models* to do this.

.. literalinclude:: ../../demo/demo_app/models.py
