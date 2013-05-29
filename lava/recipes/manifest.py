import os

class ManifestRecipe(object):
    def __init__(self, buildout, name, options):
        self.buildout = buildout
        self.options = options
        options['directory'] = self.buildout['buildout']['directory']
        self.egg_dir = os.path.realpath(options['eggs-directory']) + '/'
        self.manifest_path = os.path.join(
            options['directory'], options['manifest-file'])

    def install(self):
        pass
