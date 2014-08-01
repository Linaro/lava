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


import yaml


class DeviceTypeParser(object):

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
        device = Device(data)
        return device


class Device(object):

    def __init__(self, target):
        self.target = target
        self.__parameters__ = None
        dev_parser = DeviceTypeParser()
        self.parameters = dev_parser.parse(open("./lava_dispatcher/pipeline/devices/%s.conf" % target))
        self.parameters = dev_parser.parse(open("./lava_dispatcher/pipeline/device_types/%s.conf" % dev_parser['device_type']))

    @property
    def parameters(self):
        return self.__parameters__

    def __set_parameters__(self, data):
        self.__parameters__.update(data)

    @parameters.setter
    def parameters(self, data):
        self.__set_parameters__(data)

    def check_config(self, job):
        """
        Validates the combination of the job and the device
        *before* the Deployment actions are initialised.
        """
        pass
