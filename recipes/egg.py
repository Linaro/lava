import os

import zc.buildout.easy_install
import zc.recipe.egg


def ddst():
    if 'LAVA_INSTANCE' in os.environ:
        d = os.path.join('/srv/lava/instances', os.environ['LAVA_INSTANCE'])
    else:
        d = os.path.dirname(__file__)
        while not os.path.exists(os.path.join(d, 'etc')):
            d = os.path.dirname(d)
            assert d != '/'
    return os.path.join(d, "etc/lava-server/{filename}.conf")


class ScriptRecipe(zc.recipe.egg.Scripts):
    def __init__(self, buildout, name, options):
        zc.recipe.egg.Scripts.__init__(self, buildout, name, options)
        our_init = "import os; os.environ['DJANGO_DEBIAN_SETTINGS_TEMPLATE'] = %r"
        our_init = our_init % ddst()
        init = self.options.get('initialization', '')
        self.options['initialization'] = init + '\n' + our_init
