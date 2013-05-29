#!/usr/bin/python

import lava.recipes.wsgi

application = lava.recipes.wsgi.handler('lava_server.settings.debian', '/etc/lava-server/{filename}.conf')
