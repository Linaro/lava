# Copyright (C) 2014 Linaro Limited
#
# Author: Antonio Terceiro <antonio.terceiro@linaro.org>
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

import copy
import ConfigParser
import contextlib
import logging
import os

from lava_dispatcher.device.target import (
    Target,
    get_target,
)
from lava_dispatcher.config import get_device_config
from lava_dispatcher.utils import (
    ensure_directory,
)
from lava_dispatcher.client.lmc_utils import (
    image_partition_mounted,
)


class DynamicVmTarget(Target):

    supported_backends = {
        'kvm': lambda: kvm_adapter,
    }

    def __init__(self, context, config):

        super(DynamicVmTarget, self).__init__(context, config)

        self.__host__ = config.dynamic_vm_host
        if self.__host__ is None:
            raise CriticalError(
                "dynamic_vm_host configuration entry is mandatory")

        device_type = config.dynamic_vm_backend_device_type
        if not device_type in self.supported_backends.keys():
            raise CriticalError("%s is not supported as a backend" %
                                device_type)

        backend_config = get_device_config(config.hostname,
                                           backend_device_type=device_type)
        self.backend = get_target(context, backend_config)
        adapter_class = self.supported_backends[device_type]()
        self.backend_adapter = adapter_class(self.backend)
        self.backend_adapter.amend_config()

    @property
    def deployment_data(self):
        return self.backend.deployment_data

    def power_on(self):
        return self.backend.power_on()

    def deploy_linaro_prebuilt(self, image, rootfstype, bootloadertype):
        self.backend.deploy_linaro_prebuilt(image, rootfstype, bootloadertype)
        self.backend_adapter.copy_image()

    def power_off(self, proc):
        self.backend.power_off(proc)

    @contextlib.contextmanager
    def file_system(self, partition, directory):
        with self.backend_adapter.mount(partition) as mntdir:
            target = '%s/%s' % (mntdir, directory)
            ensure_directory(target)
            yield target

    def extract_tarball(self, tarball_url, partition, directory='/'):
        # FIXME
        raise NotImplementedError("extract_tarball")


class kvm_adapter(object):

    def __init__(self, device):
        self.device = device
        self.identity_file = '%s/dynamic_vm_keys/lava' % os.path.dirname(__file__)
        self.local_image = None
        self.remote_image = None

    def copy_image(self):
        device = self.device

        self.local_image = device._sd_image
        self.remote_image = '/lava/vm-images/%s/%s' % (device.config.hostname, os.path.basename(self.local_image))

        device.context.run_command('rm -rf /lava/vm-images/%s' % device.config.hostname, failok=False)
        device.context.run_command('ssh -o StrictHostKeyChecking=no -i %s root@%s -- mkdir -p %s' % (self.identity_file, device.config.dynamic_vm_host, os.path.dirname(self.remote_image)), failok=False)
        device.context.run_command('scp -o StrictHostKeyChecking=no -i %s %s root@%s:%s' % (self.identity_file, self.local_image, device.config.dynamic_vm_host, self.remote_image), failok=False)

        device._sd_image = self.remote_image

    def amend_config(self):
        device = self.device
        ssh = 'ssh -o StrictHostKeyChecking=no root@' + device.config.dynamic_vm_host + ' -i ' + self.identity_file
        device.config.qemu_binary = '%s -- %s' % (ssh, device.config.qemu_binary)

    @contextlib.contextmanager
    def mount(self, partition):
        device = self.device
        rsync_ssh = 'ssh -o StrictHostKeyChecking=no -i %s' % self.identity_file
        device.context.run_command('rsync -avp -e "%s" root@%s:%s %s' % (rsync_ssh, device.config.dynamic_vm_host, self.remote_image, self.local_image), failok=False)
        with image_partition_mounted(self.local_image, partition) as mount_point:
            yield mount_point
        device.context.run_command('rsync -avp -e "%s" %s root@%s:%s' % (rsync_ssh, self.local_image, device.config.dynamic_vm_host, self.remote_image))

target_class = DynamicVmTarget
