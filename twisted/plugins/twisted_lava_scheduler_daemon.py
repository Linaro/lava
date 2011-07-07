import os

from twisted.python import usage
from twisted.plugin import IPlugin
from twisted.application.service import IServiceMaker

from zope.interface import implements

from lava_scheduler_daemon.service import BoardSet

class MyServiceMaker(object):
    implements(IServiceMaker, IPlugin)
    tapname = "lava-scheduler-daemon"
    description = "Run the LAVA Scheduler Daemon"
    options = usage.Options

    def makeService(self, options):
        """
        Construct a TCPServer from a factory defined in myproject.
        """
        os.environ['DJANGO_SETTINGS_MODULE'] = 'lava_server.settings.development'
        from lava_scheduler_daemon.dbjobsource import DatabaseJobSource
        from twisted.internet import reactor
        source = DatabaseJobSource()
        return BoardSet(source, 'lava-dispatch', reactor)


# Now construct an object which *provides* the relevant interfaces
# The name of this variable is irrelevant, as long as there is *some*
# name bound to a provider of IPlugin and IServiceMaker.

serviceMaker = MyServiceMaker()
