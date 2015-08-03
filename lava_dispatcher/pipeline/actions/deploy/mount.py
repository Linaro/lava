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
from lava_dispatcher.pipeline.action import (
    JobError,
    InfrastructureError,
    Action,
    Pipeline
)
from lava_dispatcher.pipeline.logical import RetryAction
from lava_dispatcher.pipeline.actions.deploy import DeployAction
from lava_dispatcher.pipeline.utils.filesystem import mkdtemp, rmtree


class OffsetAction(DeployAction):
    """
    Uses the target.deployment_data['lava_test_results_part_attr']
    which, for example, maps to the root_part in the Device config for a qemu.
    The Device object is passed into the parser which uses the action
    parameters to determine the deployment_data parameter of the Device object.
    The calculated offset is dynamic data, stored in the context.
    """

    def __init__(self, key):
        super(OffsetAction, self).__init__()
        self.name = "offset_action"
        self.description = "calculate offset of the image"
        self.summary = "offset calculation"
        self.key = key

    def validate(self):
        if 'download_action' not in self.data:
            self.errors = "missing download_action in parameters"
        elif 'file' not in self.data['download_action']['image']:
            self.errors = "no file specified to calculate offset"

    def run(self, connection, args=None):
        if 'download_action' not in self.data:
            raise RuntimeError("Missing download action")
        if 'offset' in self.data['download_action']:
            # idempotency
            return connection
        connection = super(OffsetAction, self).run(connection, args)
        image = self.data['download_action'][self.key]['file']
        if not os.path.exists(image):
            raise RuntimeError("Not able to mount %s: file does not exist" % image)
        part_data = self.run_command([
            '/sbin/parted',
            image,
            '-m',
            '-s',
            'unit',
            'b',
            'print'
        ])
        if not part_data:
            raise JobError("Unable to identify offset")
        deploy_params = self.job.device['actions']['deploy']['methods']['image']['parameters']
        partno = deploy_params[self.parameters['deployment_data']['lava_test_results_part_attr']]

        pattern = re.compile('%d:([0-9]+)B:' % partno)
        for line in part_data.splitlines():
            found = re.match(pattern, line)
            if found:
                self.data['download_action']['offset'] = found.group(1)
        if 'offset' not in self.data['download_action']:
            raise JobError(  # FIXME: JobError needs a unit test
                "Unable to determine offset for %s" % image
            )
        return connection


class LoopCheckAction(DeployAction):

    def __init__(self):
        super(LoopCheckAction, self).__init__()
        self.name = "loop_check"
        self.description = "ensure a loop back mount operation is possible"
        self.summary = "check available loop back support"

    def validate(self):
        if 'download_action' not in self.data:
            raise RuntimeError("download_action not found %s" % self.name)
            # return  # already failed elsewhere
        if len(glob.glob('/sys/block/loop*')) <= 0:
            raise InfrastructureError("Could not mount the image without loopback devices. "
                                      "Is the 'loop' kernel module activated?")
        available_loops = len(glob.glob('/sys/block/loop*'))
        self.data['download_action']['available_loops'] = available_loops

    def run(self, connection, args=None):
        connection = super(LoopCheckAction, self).run(connection, args)
        if 'available_loops' not in self.data['download_action']:
            raise RuntimeError("Unable to check available loop devices")
        args = ['/sbin/losetup', '-a']
        pro = self.run_command(args)
        mounted_loops = len(pro.strip().split("\n")) if pro else 0
        available_loops = self.data['download_action']['available_loops']
        # FIXME: we should retry as this can happen and be fixed automatically
        # when one is unmounted
        if mounted_loops >= available_loops:
            raise InfrastructureError("Insufficient loopback devices?")
        self.logger.debug("available loops: %s" % available_loops)
        self.logger.debug("mounted_loops: %s" % mounted_loops)
        return connection


class LoopMountAction(RetryAction):
    """
    Needs to expose the final mountpoint in the job data
    to allow the customise action to push any test definitions in
    without doing to consecutive (identical) mounts in the Deploy and
    again in the test shell.
    """

    def __init__(self):
        super(LoopMountAction, self).__init__()
        self.name = "loop_mount"
        self.description = "Mount using a loopback device and offset"
        self.summary = "loopback mount"
        self.retries = 10
        self.sleep = 10
        self.mntdir = None

    def validate(self):
        self.data[self.name] = {}
        self.data.setdefault('mount_action', {})
        if 'download_action' not in self.data:
            raise RuntimeError("download-action missing: %s" % self.name)
        lava_test_results_dir = self.parameters['deployment_data']['lava_test_results_dir']
        self.data['lava_test_results_dir'] = lava_test_results_dir % self.job.job_id
        if 'file' not in self.data['download_action']['image']:
            self.errors = "no file specified to mount"

    def run(self, connection, args=None):
        connection = super(LoopMountAction, self).run(connection, args)
        self.data[self.name]['mntdir'] = mkdtemp(autoremove=False)
        self.data['mount_action']['mntdir'] = \
            os.path.abspath("%s/%s" % (self.data[self.name]['mntdir'], self.data['lava_test_results_dir']))
        mount_cmd = [
            'mount',
            '-o',
            'loop,offset=%s' % self.data['download_action']['offset'],
            self.data['download_action']['image']['file'],
            self.data[self.name]['mntdir']
        ]
        command_output = self.run_command(mount_cmd)
        self.mntdir = self.data['loop_mount']['mntdir']
        self.data['mount_action']['mntdir'] = \
            os.path.abspath("%s/%s" % (self.data[self.name]['mntdir'], self.data['lava_test_results_dir']))
        if command_output and command_output is not '':
            raise JobError("Unable to mount: %s" % command_output)  # FIXME: JobError needs a unit test
        return connection

    def cleanup(self):
        self.logger.debug("%s cleanup" % self.name)
        if self.mntdir:
            if os.path.ismount(self.mntdir):
                self.run_command(['umount', self.mntdir])
            if os.path.isdir(self.mntdir):
                rmtree(self.mntdir)
            self.mntdir = None


class MountAction(DeployAction):
    """
    Depending on the type of deployment, this needs to perform
    an OffsetAction, LoopCheckAction, LoopMountAction
    """

    def __init__(self):
        super(MountAction, self).__init__()
        self.name = "mount_action"
        self.description = "mount with offset"
        self.summary = "mount loop"

    def validate(self):
        if not self.job:
            raise RuntimeError("No job object supplied to action")
        self.internal_pipeline.validate_actions()

    def populate(self, parameters):
        """
        Needs to take account of the deployment type / image type etc.
        to determine which actions need to be added to the internal pipeline
        as part of the deployment selection step.
        """
        if not self.job:
            raise RuntimeError("No job object supplied to action")
        # FIXME: not all mount operations will need these actions
        self.internal_pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        self.internal_pipeline.add_action(OffsetAction('image'))
        # FIXME: LoopCheckAction and LoopMountAction should be in only one Action
        self.internal_pipeline.add_action(LoopCheckAction())
        self.internal_pipeline.add_action(LoopMountAction())


class UnmountAction(RetryAction):

    def __init__(self):
        super(UnmountAction, self).__init__()
        self.name = "umount-retry"
        self.description = "retry support for umount"
        self.summary = "retry umount"

    def populate(self, parameters):
        self.internal_pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        self.internal_pipeline.add_action(Unmount())


class Unmount(Action):

    def __init__(self):
        super(Unmount, self).__init__()
        self.name = "umount"
        self.description = "unmount the test image at end of deployment"
        self.summary = "unmount image"

    def run(self, connection, args=None):
        """
        rmtree is not a cleanup action - it needs to be umounted first.
        """
        connection = super(Unmount, self).run(connection, args)
        mntdir = self.data['loop_mount']['mntdir']
        self.logger.debug("umounting %s" % mntdir)
        if os.path.ismount(mntdir):
            self.run_command(['umount', mntdir])
        if os.path.isdir(mntdir):
            rmtree(mntdir)
        return connection
