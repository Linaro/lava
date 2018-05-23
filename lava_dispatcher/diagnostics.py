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


from lava_dispatcher.logical import DiagnosticAction


class DiagnoseNetwork(DiagnosticAction):
    """
    Reports network information on the dispatcher
    """

    name = "dispatcher-network-issues"
    description = "add information to the job output about the dispatcher network"
    summary = "output IP data on dispatcher"

    @classmethod
    def trigger(cls):
        return "network"

    def run(self, connection, max_end_time, args=None):
        connection = super().run(connection, max_end_time, args)
        return connection


class DiagnoseTargetNetwork(DiagnosticAction):
    """
    Runs network checks on the target device using the current connection
    """

    name = "target-network-issues"
    description = "add information to the job output about the device network"
    summary = "output IP data on device"

    @classmethod
    def trigger(cls):
        return "target-network"

    def run(self, connection, max_end_time, args=None):
        connection = super().run(connection, max_end_time, args)
        return connection


class DiagnoseUBoot(DiagnosticAction):
    """
    Report the UBoot environment
    """
    name = "uboot-environment"
    description = "report the uboot environment"
    summary = "run printenv"

    @classmethod
    def trigger(cls):
        return "uboot-printenv"

    def run(self, connection, max_end_time, args=None):
        connection = super().run(connection, max_end_time, args)
        # FIXME: write the support for reset, including running PDU command
        return connection
