#!/usr/bin/env python

from jinja2 import Environment, FileSystemLoader
import yaml

import os
import sys


def main():
  # Check command line
  if len(sys.argv) != 2:
    print("Usage: render-template.py device")
    sys.exit(1)

  device = sys.argv[1]

  env = Environment(loader=FileSystemLoader(
                    [os.path.join(os.path.dirname(__file__), 'jinja2/devices'),
                     os.path.join(os.path.dirname(__file__), 'jinja2/device_types')]),
                    trim_blocks=True)
  template = env.get_template("%s.yaml" % device)
  ctx = {}
  config = template.render(**ctx)

  print "YAML config"
  print "==========="
  print config
  print "Parsed config"
  print "============="
  print yaml.load(config)


if __name__ =='__main__':
  main()
