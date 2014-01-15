#!/usr/bin/python

import lava.recipes.wsgi

application = lava.recipes.wsgi.handler('lava_server.settings.distro', '/etc/lava-server/{filename}.conf')
