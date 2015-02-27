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

from lava_dispatcher.pipeline.action import Action
from lava_dispatcher.pipeline.logical import RetryAction
from lava_dispatcher.pipeline.connection import wait_for_prompt
from lava_dispatcher.pipeline.utils.constants import AUTOLOGIN_DEFAULT_TIMEOUT


class BootAction(RetryAction):
    """
    Base class for all actions which control power-on
    and boot behaviour of a device under test.
    The subclass selected to do the work will be the
    subclass returning True in the accepts(device_type, image)
    function.
    Each new subclass needs a unit test to ensure it is
    reliably selected for the correct job and not
    selected for an invalid job or a job
    accepted by a different subclass.

    Boot and Test are closely related - a fail error in Boot
    will cause subsequent Test actions to be skipped.
    """

    name = 'boot'


# FIXME: needs a unit test to check YAML parameter syntax
class AutoLoginAction(Action):
    """
    Automatically login on the device.
    If 'auto_login' is not present in the parameters, this action does nothing.
    """
    def __init__(self):
        super(AutoLoginAction, self).__init__()
        self.name = 'auto-login-action'
        self.description = "automatically login after boot using job parameters"
        self.summary = "Auto-login after boot"
        # FIXME: self.timeout.duration = AUTOLOGIN_DEFAULT_TIMEOUT

    def validate(self):
        super(AutoLoginAction, self).validate()
        # Skip auto login if the configuration is not found
        params = self.parameters.get('auto_login', None)
        if params is None:
            return

        if not isinstance(params, dict):
            self.errors = "'auto_login' should be a dictionary"
            return

        if 'login_prompt' not in params:
            self.errors = "'login_prompt' is mandatory for auto_login"
        if 'username' not in params:
            self.errors = "'username' is mandatory for auto_login"

        if 'password_prompt' in params:
            if 'password' not in params:
                self.errors = "'password' is mandatory if 'password_prompt' is used in auto_login"

    def run(self, connection, args=None):
        # Skip auto login if the configuration is not found
        params = self.parameters.get('auto_login', None)
        if params is None:
            self.logger.debug("Skipping auto login")
            return connection

        self.logger.debug("Waiting for the login prompt")
        wait_for_prompt(connection.raw_connection, params['login_prompt'], self.timeout.duration)
        connection.sendline(params['username'])

        if 'password_prompt' in params:
            self.logger.debug("Waiting for password prompt")
            wait_for_prompt(connection.raw_connection, params['password_prompt'], self.timeout.duration)
            connection.sendline(params['password'])
        return connection
