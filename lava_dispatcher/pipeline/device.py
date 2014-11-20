# Copyright (C) 2014 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
#
# This file is part of LAVA Dispatcher.
#
# LAVA Dispatcher is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# LAVA Dispatcher is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along
# with this program; if not, see <http://www.gnu.org/licenses>.

import os
import yaml
from yaml.composer import Composer
from yaml.constructor import Constructor


class DeviceTypeParser(object):
    """
    Very simple (too simple) parser for Device configuration files
    """

    # FIXME: design a schema and check files against it.

    loader = None

    def compose_node(self, parent, index):
        # the line number where the previous token has ended (plus empty lines)
        node = Composer.compose_node(self.loader, parent, index)
        return node

    def construct_mapping(self, node, deep=False):
        mapping = Constructor.construct_mapping(self.loader, node, deep=deep)
        return mapping

    def parse(self, content):
        self.loader = yaml.Loader(content)
        self.loader.compose_node = self.compose_node
        self.loader.construct_mapping = self.construct_mapping
        data = self.loader.get_single_data()
        return data


class NewDeviceDefaults(object):
    """
    Placeholder for an eventual schema based on the current device config schema
    but adapted to the new device parameter structure.
    Ideally, use an external file as the schema
    """

    # TODO! this should be a YAML file on the filesystem & only certain strings for specific distros
    def __init__(self):
        test_image_prompts = [r"\(initramfs\)",  # check if the r prefix breaks matching later & remove \.
                              "linaro-test",
                              "/ #",
                              "root@android",
                              "root@linaro",
                              "root@master",
                              "root@debian",
                              "root@linaro-nano:~#",
                              "root@linaro-developer:~#",
                              "root@linaro-server:~#",
                              "root@genericarmv7a:~#",
                              "root@genericarmv8:~#"]
        self.parameters = {
            'test_image_prompts': test_image_prompts
        }


class NewDevice(object):
    """
    YAML based Device class with clearer support for the pipeline overrides
    and deployment types.
    """
    # FIXME: replace the current Device class with this one.

    def __init__(self, target):
        self.target = target
        self.__parameters__ = {}
        dev_parser = DeviceTypeParser()
        # development paths are within the working directory
        # FIXME: system paths need to be finalised.
        # possible default system_config_path = "/usr/share/lava-dispatcher"
        # FIXME: change to default-config once the old files are converted.
        default_config_path = os.path.join(os.path.dirname(__file__))
        if not os.path.exists(os.path.join(default_config_path, 'devices', "%s.conf" % target)):
            raise RuntimeError("Unable to use new devices: %s" % default_config_path)

        defaults = NewDeviceDefaults()
        # parameters dict will update if new settings are found, so repeat for customisation files when those exist
        self.parameters = defaults.parameters
        device_file = os.path.join(default_config_path, 'devices', "%s.conf" % target)
        if not os.path.exists(device_file):
            raise RuntimeError("Could not find %s" % device_file)
        try:
            self.parameters = dev_parser.parse(open(device_file))
        except TypeError:
            raise RuntimeError("%s could not be parsed" % device_file)
        type_file = os.path.join(default_config_path, 'device_types', "%s.conf" % self.parameters['device_type'])
        if not os.path.exists(type_file):
            raise RuntimeError("Could not find %s" % type_file)
        try:
            self.parameters = dev_parser.parse(open(type_file))
        except TypeError:
            raise RuntimeError("%s could not be parsed" % type_file)
        self.parameters = {'hostname': target}  # FIXME: is this needed?

    @property
    def parameters(self):
        return self.__parameters__

    @parameters.setter
    def parameters(self, data):
        self.__parameters__.update(data)

    def check_config(self, job):
        """
        Validates the combination of the job and the device
        *before* the Deployment actions are initialised.
        """
        raise NotImplementedError("check_config")
