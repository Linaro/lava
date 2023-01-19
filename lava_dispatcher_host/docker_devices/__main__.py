import argparse
import sys

from . import Device, DeviceFilter

parser = argparse.ArgumentParser()
parser.add_argument("container")
parser.add_argument("major")
parser.add_argument("minor")
args = parser.parse_args(sys.argv[1:])

container, major, minor = args.container, args.major, args.minor
device_filter = DeviceFilter(container)
device_filter.add(Device(int(major), int(minor)))
device_filter.apply()
