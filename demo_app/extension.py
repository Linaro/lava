from lava_server.extension import LavaServerExtension


class DemoExtension(LavaServerExtension):
    """
    Demo extension that shows how to integrate third party
    components into LAVA server.
    """

    @property
    def app_name(self):
        return "demo_app"

    @property
    def description(self):
        return "Demo extension for LAVA server"
