import os
import textwrap

from zc.buildout import UserError

CANNOT_FIND_INSTANCE_TEXT = """\
Could not find LAVA instance. You can specify an instance by passing -o
{name}:instance-name=$name or -o {name}:instance-path=$path when invoking
buildout.
"""

def find_instance(section_name):
    d = os.path.dirname(__file__)
    while not os.path.exists(os.path.join(d, 'etc')):
        d = os.path.dirname(d)
        if d == '/':
            wrapped = textwrap.fill(
                CANNOT_FIND_INSTANCE_TEXT.format(name=section_name),
                width=75,
                subsequent_indent=' '*7, break_on_hyphens=False)
            raise UserError(wrapped)
    return d


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
