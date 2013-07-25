import os
import yaml

search_path = [
    '/etc/lava-server/crowd.yaml'
]

if "VIRTUAL_ENV" in os.environ:
    search_path.insert(0, os.path.join(os.environ["VIRTUAL_ENV"],
                                       'etc/lava-server/crowd.yaml'))

config_file = None

for f in search_path:
    if os.path.exists(f):
        config_file = f
        break

enabled = (config_file is not None)

settings = {}

if config_file:
    settings = yaml.load(open(config_file))
