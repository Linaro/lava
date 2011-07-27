from ConfigParser import ConfigParser
import os
from StringIO import StringIO

#from xdg.BaseDirectory import load_config_paths

defaults = {
    'logging': StringIO(
'''
[logging]
level = INFO
destination = -
'''),
    }

# python xdg isn't installable via pip, so...
def load_config_paths(name):
    for directory in os.path.expanduser("~/.config"), '/etc/xdg':
        path = os.path.join(directory, name)
        if os.path.isdir(path):
            yield path


def get_config(name):
    config_files = []
    for directory in load_config_paths('lava-scheduler'):
        path = os.path.join(directory, '%s.conf' % name)
        if os.path.exists(path):
            config_files.append(path)
    config_files.reverse()
    fp = ConfigParser()
    if name in defaults:
        fp.readfp(defaults[name])
    fp.read(config_files)
    return fp
