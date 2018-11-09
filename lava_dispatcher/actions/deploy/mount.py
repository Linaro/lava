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
import re
import glob
from lava_common.exceptions import JobError, InfrastructureError, LAVABug
from lava_dispatcher.action import Action, Pipeline
from lava_dispatcher.logical import RetryAction
from lava_dispatcher.actions.deploy import DeployAction
from lava_dispatcher.utils.filesystem import mkdtemp, rmtree


class OffsetAction(DeployAction):
    """
    Uses the target.deployment_data['lava_test_results_part_attr']
    which, for example, maps to the root_part in the Device config for a qemu.
    The Device object is passed into the parser which uses the action
    parameters to determine the deployment_data parameter of the Device object.
    The calculated offset is dynamic data, stored in the context.
    """

    name = "offset-action"
    description = "calculate offset of the image"
    summary = "offset calculation"

    def __init__(self, key):
        super().__init__()
        self.key = key

    def validate(self):
        super().validate()
        if not self.get_namespace_data(
            action="download-action", label=self.key, key="file"
        ):
            self.errors = "no file specified to calculate offset"

    def run(self, connection, max_end_time):
        if self.get_namespace_data(
            action="download-action", label=self.key, key="offset"
        ):
            # idempotency
            return connection
        connection = super().run(connection, max_end_time)
        image = self.get_namespace_data(
            action="download-action", label=self.key, key="file"
        )
        if not os.path.exists(image):
            raise JobError("Not able to mount %s: file does not exist" % image)
        part_data = self.run_command(
            ["/sbin/parted", image, "-m", "-s", "unit", "b", "print"]
        )
        if not part_data:
            raise JobError("Unable to identify offset")
        deploy_params = self.job.device["actions"]["deploy"]["methods"]["image"][
            "parameters"
        ]
        partno = deploy_params[
            self.parameters["deployment_data"]["lava_test_results_part_attr"]
        ]

        pattern = re.compile("%d:([0-9]+)B:" % partno)
        for line in part_data.splitlines():
            found = re.match(pattern, line)
            if found:
                self.set_namespace_data(
                    action=self.name, label=self.key, key="offset", value=found.group(1)
                )
        if not self.get_namespace_data(action=self.name, label=self.key, key="offset"):
            raise JobError(  # FIXME: JobError needs a unit test
                "Unable to determine offset for %s" % image
            )
        return connection


class LoopCheckAction(DeployAction):

    name = "loop-check"
    description = "ensure a loop back mount operation is possible"
    summary = "check available loop back support"

    def __init__(self, key):
        super().__init__()
        self.key = key

    def validate(self):
        super().validate()
        if not glob.glob("/sys/block/loop*"):
            raise InfrastructureError(
                "Could not mount the image without loopback devices. "
                "Is the 'loop' kernel module activated?"
            )
        available_loops = len(glob.glob("/sys/block/loop*"))
        self.set_namespace_data(
            action=self.name,
            label=self.key,
            key="available_loops",
            value=available_loops,
        )

    def run(self, connection, max_end_time):
        connection = super().run(connection, max_end_time)
        if not self.get_namespace_data(
            action=self.name, label=self.key, key="available_loops"
        ):
            raise LAVABug("Unable to check available loop devices")
        args = ["/sbin/losetup", "-a"]
        pro = self.run_command(args)
        mounted_loops = len(pro.strip().split("\n")) if pro else 0
        available_loops = self.get_namespace_data(
            action=self.name, label=self.key, key="available_loops"
        )
        # FIXME: we should retry as this can happen and be fixed automatically
        # when one is unmounted
        if mounted_loops >= available_loops:
            raise InfrastructureError("Insufficient loopback devices?")
        self.logger.debug("available loops: %s", available_loops)
        self.logger.debug("mounted_loops: %s", mounted_loops)
        return connection


class LoopMountAction(RetryAction):
    """
    Needs to expose the final mountpoint in the job data
    to allow the customise action to push any test definitions in
    without doing to consecutive (identical) mounts in the Deploy and
    again in the test shell.
    """

    name = "loop-mount"
    description = "Mount using a loopback device and offset"
    summary = "loopback mount"

    def __init__(self, key):
        super().__init__()
        self.retries = 10
        self.sleep = 10
        self.mntdir = None
        self.key = key

    def validate(self):
        super().validate()
        lava_test_results_base = self.parameters["deployment_data"][
            "lava_test_results_dir"
        ]
        lava_test_results_dir = lava_test_results_base % self.job.job_id
        self.set_namespace_data(
            action="test",
            label="results",
            key="lava_test_results_dir",
            value=lava_test_results_dir,
        )
        if not self.get_namespace_data(
            action="download-action", label=self.key, key="file"
        ):
            self.errors = "no file specified to mount"

    def run(self, connection, max_end_time):
        connection = super().run(connection, max_end_time)
        self.mntdir = mkdtemp(autoremove=False)
        lava_test_results_dir = self.get_namespace_data(
            action="test", label="results", key="lava_test_results_dir"
        )
        test_mntdir = os.path.abspath("%s/%s" % (self.mntdir, lava_test_results_dir))
        self.set_namespace_data(
            action=self.name, label="mntdir", key="mntdir", value=self.mntdir
        )
        self.set_namespace_data(
            action="mount-action", label="mntdir", key="mntdir", value=test_mntdir
        )
        offset = self.get_namespace_data(
            action="download-action", label=self.key, key="offset"
        )
        mount_cmd = [
            "mount",
            "-o",
            "loop,offset=%s" % offset,
            self.get_namespace_data(
                action="download-action", label=self.key, key="file"
            ),
            self.mntdir,
        ]
        command_output = self.run_command(mount_cmd)
        if command_output and command_output != "":
            raise JobError(
                "Unable to mount: %s" % command_output
            )  # FIXME: JobError needs a unit test
        return connection

    def cleanup(self, connection):
        super().cleanup(connection)
        self.logger.debug("%s cleanup", self.name)
        if self.mntdir:
            if os.path.ismount(self.mntdir):
                self.run_command(["umount", self.mntdir])
            if os.path.isdir(self.mntdir):
                rmtree(self.mntdir)
            self.mntdir = None


class MountAction(DeployAction):
    """
    Depending on the type of deployment, this needs to perform
    an OffsetAction, LoopCheckAction, LoopMountAction
    """

    name = "mount-action"
    description = "mount with offset"
    summary = "mount loop"

    def __init__(self, key):
        super().__init__()
        self.key = key

    def populate(self, parameters):
        """
        Needs to take account of the deployment type / image type etc.
        to determine which actions need to be added to the internal pipeline
        as part of the deployment selection step.
        """
        if not self.job:
            raise LAVABug("No job object supplied to action")
        # FIXME: not all mount operations will need these actions
        self.internal_pipeline = Pipeline(
            parent=self, job=self.job, parameters=parameters
        )
        self.internal_pipeline.add_action(OffsetAction(self.key))
        # FIXME: LoopCheckAction and LoopMountAction should be in only one Action
        self.internal_pipeline.add_action(LoopCheckAction(self.key))
        self.internal_pipeline.add_action(LoopMountAction(self.key))


class UnmountAction(RetryAction):

    name = "umount-retry"
    description = "retry support for umount"
    summary = "retry umount"

    def populate(self, parameters):
        self.internal_pipeline = Pipeline(
            parent=self, job=self.job, parameters=parameters
        )
        self.internal_pipeline.add_action(Unmount())


class Unmount(Action):

    name = "umount"
    description = "unmount the test image at end of deployment"
    summary = "unmount image"

    def run(self, connection, max_end_time):
        """
        rmtree is not a cleanup action - it needs to be umounted first.
        """
        connection = super().run(connection, max_end_time)
        # mntdir was never being set correctly
        return connection
