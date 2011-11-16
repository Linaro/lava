Adding Extensions to LAVA Server
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

LAVA Server can be used as the base for further extensions.  Extensions
currently exist for things like adding scheduler support, a dashboard
interface, and additional views of test data.  Extensions can add
further data models, menus, and views, and even APIs to the existing LAVA Server framework.

Extensions are essentially just a django app.  It hooks into LAVA Server
using an entry point called *extensions*.

For a simple example of adding an extension, see the 'demo' subdirectory
in the lava-server source repository.

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

LavaServerExtension
*******************
The other thing your django extension to LAVA Server will need is a
class that inherits LavaServerExtensions.  This class defines properties
that are needed for LAVA Server to include your extension.

.. literalinclude:: ../demo/demo_app/extension.py

Extending the API
*****************
As previously mentioned, the LAVA Server xmlrpc API can be extended with
new methods using LAVA Server extensions.  In the *demo_app* example we
have been looking at, a new method called *demoMethod()* is added to the
API and is automatically added under a namespace called *demo*.  It uses
*ExposedAPI* from *linaro_django_xmlrpc.models* to do this.

.. literalinclude:: ../demo/demo_app/models.py
