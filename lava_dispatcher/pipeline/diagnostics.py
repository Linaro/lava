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


from lava_dispatcher.pipeline.logical import DiagnosticAction


class DiagnoseNetwork(DiagnosticAction):
    """
    Reports network information on the dispatcher
    """
    def __init__(self):
        super(DiagnoseNetwork, self).__init__()
        self.name = "dispatcher_network_issues"
        self.summary = "output IP data on dispatcher"
        self.description = "add information to the job output about the dispatcher network"

    @classmethod
    def trigger(cls):
        return "network"

    def run(self, connection, args=None):
        connection = super(DiagnoseNetwork, self).run(connection, args)
        return connection


class DiagnoseTargetNetwork(DiagnosticAction):
    """
    Runs network checks on the target device using the current connection
    """
    def __init__(self):
        super(DiagnoseTargetNetwork, self).__init__()
        self.name = "target_network_issues"
        self.summary = "output IP data on device"
        self.description = "add information to the job output about the device network"

    @classmethod
    def trigger(cls):
        return "target-network"

    def run(self, connection, args=None):
        connection = super(DiagnoseTargetNetwork, self).run(connection, args)
        return connection


class DiagnoseUBoot(DiagnosticAction):
    """
    Report the UBoot environment
    """
    def __init__(self):
        super(DiagnoseUBoot, self).__init__()
        self.name = "uboot_environment"
        self.summary = "run printenv"
        self.description = "report the uboot environment"

    @classmethod
    def trigger(cls):
        return "uboot-printenv"

    def run(self, connection, args=None):
        connection = super(DiagnoseUBoot, self).run(connection, args)
        # FIXME: write the support for reset, including running PDU command
        return connection
