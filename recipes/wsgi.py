import os

import django.core.handlers.wsgi

import zc.buildout.easy_install
import zc.recipe.egg

from lava.recipes.instance_path import instance_path

wsgi_template = """
%(relative_paths_setup)s
import sys
sys.path[0:0] = [
%(path)s,
]
%(initialization)s
import %(module_name)s

application = %(module_name)s.%(attrs)s(%(arguments)s)
"""

def handler(settings, instance_path):
    os.environ['DJANGO_SETTINGS_MODULE'] = settings
    os.environ['DJANGO_DEBIAN_SETTINGS_TEMPLATE'] = os.path.join(
        instance_path, "etc/lava-server/{filename}.conf")
    return django.core.handlers.wsgi.WSGIHandler()

class WSGIRecipe(object):
    def __init__(self, buildout, name, options):
        self.egg = zc.recipe.egg.Egg(buildout, options['recipe'], options)
        self.options = options

    def make_wsgi_file(self):
        scripts = []
        _script_template = zc.buildout.easy_install.script_template
        reqs, ws = requirements, ws = self.egg.working_set()
        try:
            zc.buildout.easy_install.script_template = \
                zc.buildout.easy_install.script_header + wsgi_template
            scripts.extend(
                zc.buildout.easy_install.scripts(
                    [(self.options['name'] + '.wsgi',
                      'lava.recipes.wsgi',
                      'handler')],
                    ws,
                    self.options['executable'],
                    self.options['bin-directory'],
                    arguments='%r,%r'%(self.options['settings'], instance_path)
                    ))
        finally:
            zc.buildout.easy_install.script_template = _script_template
        return scripts

        pass

    def install(self):
        return self.make_wsgi_file()

    def update(self):
        pass
