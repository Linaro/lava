# Copyright (C) 2014 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later


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

    def run(self, connection, max_end_time):
        connection = super().run(connection, max_end_time)
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

    def run(self, connection, max_end_time):
        connection = super().run(connection, max_end_time)
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

    def run(self, connection, max_end_time):
        connection = super().run(connection, max_end_time)
        # FIXME: write the support for reset, including running PDU command
        return connection
