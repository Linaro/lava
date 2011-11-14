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

.. code-block:: python

    import versiontools
    from lava_server.extension import LavaServerExtension
    
    import demo_app
    
    
    class DemoExtension(LavaServerExtension):
        """
        Demo extension that shows how to integrate third party
        components into LAVA server.
        """
    
        @property
        def app_name(self):
            return "demo_app"
    
        @property
        def name(self):
            return "Demo"
    
        @property
        def api_class(self):
            from demo_app.models import DemoAPI
            return DemoAPI
    
        @property
        def main_view_name(self):
            return "demo_app.views.hello"
    
        @property
        def description(self):
            return "Demo extension for LAVA server"
    
        @property
        def version(self):
            return versiontools.format_version(demo_app.__version__)

Extending the API
*****************
As previously mentioned, the LAVA Server xmlrpc API can be extended with
new methods using LAVA Server extensions.  In the *demo_app* example we
have been looking at, a new method called *demoMethod()* is added to the
API and is automatically added under a namespace called *demo*.  It uses
*ExposedAPI* from *linaro_django_xmlrpc.models* to do this.

.. code-block:: python

    from django.db import models
    from linaro_django_xmlrpc.models import ExposedAPI
    
    
    class Message(models.Model):
        text = models.TextField()
    
    
        class DemoAPI(ExposedAPI):
            def demoMethod(self):
                return 42

