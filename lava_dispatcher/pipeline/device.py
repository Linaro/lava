# Copyright (C) 2014 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
#         Remi Duraffort <remi.duraffort@linaro.org>
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

from lava_dispatcher.pipeline.action import ConfigurationError


class PipelineDevice(dict):
    """
    Dictionary Device class which accepts data rather than a filename.
    This allows the scheduler to use the same class without needing to write
    out YAML files from database content.
    """

    def __init__(self, config, hostname):
        super(PipelineDevice, self).__init__()
        self.update(config)

        self.target = hostname

        self['hostname'] = hostname

    def check_config(self, job):
        """
        Validates the combination of the job and the device
        *before* the Deployment actions are initialised.
        """
        raise NotImplementedError("check_config")

    @property
    def hard_reset_command(self):
        if 'commands' in self and 'hard_reset' in self['commands']:
            return self['commands']['hard_reset']
        return ''

    @property
    def soft_reset_command(self):
        if 'commands' in self and 'soft_reset' in self['commands']:
            return self['commands']['soft_reset']
        return ''

    @property
    def pre_os_command(self):
        if 'commands' in self and 'pre_os_command' in self['commands']:
            return self['commands']['pre_os_command']
        return None

    @property
    def pre_power_command(self):
        if 'commands' in self and 'pre_power_command' in self['commands']:
            return self['commands']['pre_power_command']
        return None

    @property
    def power_command(self):
        if 'commands' in self and 'power_on' in self['commands']:
            return self['commands']['power_on']
        return ''

    @property
    def connect_command(self):
        if 'connect' in self['commands']:
            return self['commands']['connect']
        return ''

    def get_constant(self, const):
        if 'constants' not in self:
            raise ConfigurationError("constants section not present in the device config.")
        if const not in self['constants']:
            raise ConfigurationError("Constant %s does not exist in the device config 'constants' section." % const)
        return self['constants'][const]


class NewDevice(PipelineDevice):
    """
    YAML based PipelineDevice class with clearer support for the pipeline overrides
    and deployment types. Simple change of init whilst allowing the scheduler and
    the dispatcher to share the same functionality.
    """

    def __init__(self, target):
        super(NewDevice, self).__init__({}, None)
        # Parse the yaml configuration
        try:
            with open(target) as f_in:
                self.update(yaml.load(f_in))
        except yaml.parser.ParserError:
            raise ConfigurationError("%s could not be parsed" % target)

        # Get the device name (/path/to/kvm01.yaml => kvm01)
        self.target = os.path.splitext(os.path.basename(target))[0]

        self['hostname'] = self.target
        self.setdefault('power_state', 'off')  # assume power is off at start of job

    def check_config(self, job):
        """
        Validates the combination of the job and the device
        *before* the Deployment actions are initialised.
        """
        raise NotImplementedError("check_config")
