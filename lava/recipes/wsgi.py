import os
from django.core.wsgi import get_wsgi_application


def handler(settings, ddst):
    import django.core.handlers.wsgi
    os.environ['DJANGO_SETTINGS_MODULE'] = settings
    os.environ['DJANGO_DEBIAN_SETTINGS_TEMPLATE'] = ddst
    return get_wsgi_application()


class WSGIRecipe(object):
    def __init__(self, buildout, name, options):
        self.options = options
        self.options['lava-server-settings-template'] = buildout[
            'instance']['lava-server-settings-template']

    def make_wsgi_file(self):
        pass

    def install(self):
        pass

    def update(self):
        pass
