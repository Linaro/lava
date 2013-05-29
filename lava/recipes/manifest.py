import os

import zc.recipe.egg


class ManifestRecipe(object):
    def __init__(self, buildout, name, options):
        self.buildout = buildout
        self.egg = zc.recipe.egg.Egg(buildout, options['recipe'], options)
        self.options = options
        options['directory'] = self.buildout['buildout']['directory']
        self.egg_dir = os.path.realpath(options['eggs-directory']) + '/'
        self.manifest_path = os.path.join(
            options['directory'], options['manifest-file'])

    def make_manifest(self):
        reqs, ws = self.egg.working_set()
        distributions = []
        for egg in ws:
            location = egg.location
            if location.startswith(self.egg_dir):
                location = "EGG: " + location[len(self.egg_dir):]
            distributions.append((egg.key, egg.version, location))
        distributions.sort()
        with open(self.manifest_path, 'w') as manifest:
            for n, v, l in distributions:
                manifest.write('# from %s:\n' % (l,))
                manifest.write('%s == %s\n' % (n, v))

    def install(self):
        self.make_manifest()
        return [self.manifest_path]

    update = install
