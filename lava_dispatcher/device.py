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

import yaml

from lava_dispatcher.action import ConfigurationError


class PipelineDevice(dict):
    """
    Dictionary Device class which accepts data rather than a filename.
    This allows the scheduler to use the same class without needing to write
    out YAML files from database content.
    """

    def __init__(self, config):
        super().__init__()
        self.update(config)

    def check_config(self, job):
        """
        Validates the combination of the job and the device
        *before* the Deployment actions are initialised.
        """
        raise NotImplementedError("check_config")

    @property
    def hard_reset_command(self):
        return self.get('commands', {}).get('hard_reset', '')

    @property
    def soft_reset_command(self):
        return self.get('commands', {}).get('soft_reset', '')

    @property
    def pre_os_command(self):
        return self.get('commands', {}).get('pre_os_command')

    @property
    def pre_power_command(self):
        return self.get('commands', {}).get('pre_power_command')

    @property
    def power_command(self):
        return self.get('commands', {}).get('power_on', '')

    @property
    def connect_command(self):
        if 'connect' in self['commands']:
            return self['commands']['connect']
        elif 'connections' in self['commands']:
            for hardware, value in self['commands']['connections'].items():
                if 'connect' not in value:
                    return ''
                if 'tags' in value and 'primary' in value['tags']:
                    return value['connect']
        return ''

    def get_constant(self, const, prefix=None, missing_ok=False):
        if 'constants' not in self:
            raise ConfigurationError("constants section not present in the device config.")
        if prefix:
            if not self['constants'].get(prefix, {}).get(const, {}):
                if missing_ok:
                    return None
                raise ConfigurationError("Constant %s,%s does not exist in the device config 'constants' section." % (prefix, const))
            else:
                return self['constants'][prefix][const]
        if const not in self['constants']:
            if missing_ok:
                return None
            raise ConfigurationError("Constant %s does not exist in the device config 'constants' section." % const)
        return self['constants'][const]


class NewDevice(PipelineDevice):
    """
    YAML based PipelineDevice class with clearer support for the pipeline overrides
    and deployment types. Simple change of init whilst allowing the scheduler and
    the dispatcher to share the same functionality.
    """

    def __init__(self, target):
        super().__init__({})
        # Parse the yaml configuration
        try:
            if isinstance(target, str):
                with open(target) as f_in:
                    data = f_in.read()
                data = yaml.load(data)
            elif isinstance(target, dict):
                data = target
            else:
                data = target.read()
                data = yaml.load(data)
            if data is None:
                raise ConfigurationError("Missing device configuration")
            self.update(data)
        except yaml.parser.ParserError:
            raise ConfigurationError("%s could not be parsed" % target)

        self.setdefault('power_state', 'off')  # assume power is off at start of job

    def check_config(self, job):
        """
        Validates the combination of the job and the device
        *before* the Deployment actions are initialised.
        """
        raise NotImplementedError("check_config")
