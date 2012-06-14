import os

import zc.recipe.egg


def get_symlink_location(options):
    return os.path.join(options['directory'], 'server_code')


class ServerSymlink(object):
    def __init__(self, buildout, name, options):
        self.buildout = buildout
        self.egg = zc.recipe.egg.Egg(buildout, options['recipe'], options)
        self.options = options
        options['directory'] = self.buildout['buildout']['directory']

    def make_link(self):
        reqs, ws = self.egg.working_set()
        lava_server_code = os.path.join(ws.require('lava-server')[0].location, 'lava_server')
        assert os.path.exists(lava_server_code)
        symlink_location = get_symlink_location(self.options)
        if os.path.exists(symlink_location):
            os.unlink(symlink_location)
        os.symlink(lava_server_code, symlink_location)
        return symlink_location

    def install(self):
        symlink_location = self.make_link()
        return [symlink_location]

    def update(self):
        symlink_location = self.make_link()
        return [symlink_location]

def uninstall_server_symlink(name, options):
    symlink_location = get_symlink_location(options)
    os.unlink(symlink_location)
