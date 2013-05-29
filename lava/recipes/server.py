import os

import zc.recipe.egg


def get_symlink_location(options):
    return os.path.join(options['directory'], 'server_code')


class ServerSymlink(object):
    def __init__(self, buildout, name, options):
        pass

    def install(self):
        pass

    def update(self):
        pass
