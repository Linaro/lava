import os


def instance_name():
    if 'LAVA_INSTANCE' in os.environ:
        return os.environ['LAVA_INSTANCE']
    else:
        d = os.path.dirname(__file__)
        while not os.path.exists(os.path.join(d, 'etc')):
            d = os.path.dirname(d)
            assert d != '/'
        return os.path.basename(d)


def instance_path():
    if 'LAVA_INSTANCE' in os.environ:
        d = os.path.join('/srv/lava/instances', os.environ['LAVA_INSTANCE'])
    else:
        d = os.path.dirname(__file__)
        while not os.path.exists(os.path.join(d, 'etc')):
            d = os.path.dirname(d)
            assert d != '/'
    return d


class InstancePath(object):

    def __init__(self, buildout, name, options):
        self.buildout = buildout
        self.options = options
        path = instance_path()
        options['instance-path'] = path
        options['instance-name'] = os.environ.get(
            "LAVA_INSTANCE", os.path.basename(path))
        options['django-debian-settings-template'] = os.path.join(
            path, "etc/lava-server/{filename}.conf")

    def install(self):
        return []
