import os

import zc.recipe.egg

class ServerSymlink(object):
    def __init__(self, buildout, name, options):
        self.buildout = buildout
        self.egg = zc.recipe.egg.Egg(buildout, options['recipe'], options)
        self.options = options


    def install(self):
        reqs, ws = self.egg.working_set()
        lava_server_code = os.path.join(ws.require('lava-server')[0].location, 'lava_server')
        assert os.path.exists(lava_server_code)
        symlink_location = os.path.join(self.buildout['buildout']['directory'], 'server_code')
        os.symlink(lava_server_code, symlink_location)
        return [symlink_location]

    def update(self):
        pass
