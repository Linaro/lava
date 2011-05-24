from lava_server.extension import ILavaServerExtension


class DemoExtension(ILavaServerExtension):
    """
    Demo extension that shows how to integrate third party
    components into LAVA server.
    """
    
    def contribute_to_settings(self, settings):
        settings['INSTALLED_APPS'] += ["demo_app"]
