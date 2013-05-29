import os

class InstancePath(object):

    def __init__(self, buildout, name, options):
        self.buildout = buildout
        self.options = options
        if 'instance-name' not in options:
            if 'LAVA_INSTANCE' in os.environ:
                options['instance-name'] = os.environ["LAVA_INSTANCE"]
        if 'instance-name' in options:
            options['instance-path'] = os.path.join(
                '/srv/lava/instances', options['instance-name'])
        elif 'instance-path' in options:
            options['instance-name'] = os.path.basename(
                options['instance-path'])
        else:
            options['instance-path'] = find_instance(name)
            options['instance-name'] = os.path.basename(
                options['instance-path'])
        options['django-debian-settings-template'] = os.path.join(
            options['instance-path'], "etc/lava-server/{filename}.conf")

    def install(self):
        return []
