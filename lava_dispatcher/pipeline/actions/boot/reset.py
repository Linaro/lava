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

# List just the subclasses supported for this base strategy
# imported by the parser to populate the list of subclasses.


from lava_dispatcher.pipeline.action import Action, Pipeline
from lava_dispatcher.pipeline.shell import ExpectShellSession


class ResetDevice(Action):
    """
    Used within a RetryAction - first tries 'reboot' then
    tries PDU
    """
    # FIXME: extend to know the power state of the device
    # FIXME: extend to use PDU classes if reboot command fails
    def __init__(self):
        super(ResetDevice, self).__init__()
        self.name = "reboot-device"
        self.description = "reboot or power-cycle the device"
        self.summary = "reboot the device"

    def populate(self, parameters):
        self.internal_pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        # FIXME: decide how to use PDU if reboot fails.
        self.internal_pipeline.add_action(ExpectShellSession())
        self.internal_pipeline.add_action(RebootDevice())


class RebootDevice(Action):
    """
    Issues the reboot command on the board
    """
    def __init__(self):
        super(RebootDevice, self).__init__()
        self.name = "soft-reboot"
        self.summary = "reboot command sent to device"
        self.description = "attempt to reboot the running device"

    def run(self, connection, args=None):
        if not connection:
            raise RuntimeError("Called %s without an active Connection" % self.name)
        connection.sendline("reboot")
        connection.wait()
        return connection

        # Looking for reboot messages or if they are missing, the U-Boot
        # message will also indicate the reboot is done.
        # match_id = connection.expect(
        #     [pexpect.TIMEOUT, 'Restarting system.',
        #      'The system is going down for reboot NOW',
        #      'Will now restart', 'U-Boot'], timeout=120)


class PDUReboot(Action):
    """
    Issues the PDU power cycle commands on the dispatcher
    """
    def __init__(self):
        super(PDUReboot, self).__init__()
        self.name = "pdu-reboot"
        self.summary = "hard reboot"
        self.description = "issue commands to PDU to power cycle device"
