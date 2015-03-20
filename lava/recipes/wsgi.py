import os
import yaml
from django.core.wsgi import get_wsgi_application


def create_environ(env_file):
    """ Generate the env variables for the server, same as the dispatcher """
    conf = yaml.load(open(env_file))
    if conf.get('purge', False):
        environ = {}
    else:
        environ = dict(os.environ)

    # Remove some variables (that might not exist)
    for var in conf.get('removes', {}):
        try:
            del environ[var]
        except KeyError:
            pass

    # Override
    environ.update(conf.get('overrides', {}))
    return environ


def handler(settings, ddst):
    import django.core.handlers.wsgi

    env_file = "/etc/lava-server/env.yaml"
    if os.path.exists(env_file):
        os.environ = create_environ(env_file)

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
