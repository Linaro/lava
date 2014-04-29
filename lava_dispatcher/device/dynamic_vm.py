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
import shutil

from lava_dispatcher.device.target import (
    Target,
    get_target,
)
from lava_dispatcher.config import get_device_config
from lava_dispatcher.errors import CriticalError
from lava_dispatcher.utils import (
    ensure_directory,
)
from lava_dispatcher.client.lmc_utils import (
    image_partition_mounted,
)


class DynamicVmTarget(Target):

    supported_backends = {
        'kvm': lambda: kvm_adapter,
        'kvm-arm': lambda: kvm_adapter,
    }

    def __init__(self, context, config):

        super(DynamicVmTarget, self).__init__(context, config)

        device_type = config.dynamic_vm_backend_device_type
        if not device_type in self.supported_backends.keys():
            raise CriticalError("%s is not supported as a backend" %
                                device_type)

        backend_config = get_device_config(config.hostname,
                                           backend_device_type=device_type)
        self.backend = get_target(context, backend_config)
        adapter_class = self.supported_backends[device_type]()
        self.backend_adapter = adapter_class(self.backend)

    @property
    def deployment_data(self):
        return self.backend.deployment_data

    def power_on(self):
        self.backend_adapter.amend_config()
        return self.backend.power_on()

    def deploy_linaro_kernel(self, kernel, ramdisk, dtb, rootfs, nfsrootfs,
                             bootloader, firmware, rootfstype, bootloadertype,
                             target_type):
        self.backend.deploy_linaro_kernel(kernel, ramdisk, dtb, rootfs,
                                          nfsrootfs, bootloader, firmware,
                                          rootfstype, bootloadertype,
                                          target_type)
        self.backend_adapter.copy_images()

    def deploy_linaro_prebuilt(self, image, dtb, rootfstype, bootloadertype):
        self.backend.deploy_linaro_prebuilt(image, dtb, rootfstype, bootloadertype)
        self.backend_adapter.copy_images()

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

    ssh_options = '-o Compression=yes -o UserKnownHostsFile=/dev/null -o PasswordAuthentication=no -o StrictHostKeyChecking=no'
    ssh = 'ssh %s' % ssh_options
    scp = 'scp %s' % ssh_options

    def __init__(self, device):
        self.device = device
        identity_file = '%s/dynamic_vm_keys/lava' % os.path.dirname(__file__)
        self.identity_file = os.path.join(device.scratch_dir, 'lava')
        shutil.copyfile(identity_file, self.identity_file)
        os.chmod(self.identity_file, 0600)
        self.local_sd_image = None
        self.__host__ = None

    @property
    def host(self):
        if self.__host__ is not None:
            return self.__host__

        device = self.device
        self.__host__ = device.config.dynamic_vm_host
        if self.__host__ is None and \
           'is_vmhost' in device.context.test_data.metadata and \
           'host_ip' in device.context.test_data.metadata:
            self.__host__ = device.context.test_data.metadata['host_ip']

        if self.__host__ is None:
            raise CriticalError("Config item dynamic_vm_host is mandatory")

        return self.__host__

    def copy_images(self):
        device = self.device
        self.local_sd_image = device._sd_image  # save local image location
        device._sd_image = self.copy_image(device._sd_image)
        device._kernel = self.copy_image(device._kernel)
        device._dtb = self.copy_image(device._dtb)
        device._ramdisk = self.copy_image(device._ramdisk)
        device._firmware = self.copy_image(device._firmware)

    def copy_image(self, local_image):
        if local_image is None:
            return None

        device = self.device

        remote_image = '/lava/vm-images/%s/%s' % (device.config.hostname, os.path.basename(local_image))

        device.context.run_command('rm -rf /lava/vm-images/%s' % device.config.hostname, failok=False)
        device.context.run_command(self.ssh + ' -i %s root@%s -- mkdir -p %s' % (self.identity_file, self.host, os.path.dirname(remote_image)), failok=False)
        device.context.run_command(self.scp + ' -i %s %s root@%s:%s' % (self.identity_file, local_image, self.host, remote_image), failok=False)

        return remote_image

    def amend_config(self):
        device = self.device
        ssh = self.ssh + ' root@' + self.host + ' -i ' + self.identity_file
        device.config.qemu_binary = '%s -- %s' % (ssh, device.config.qemu_binary)

    @contextlib.contextmanager
    def mount(self, partition):
        device = self.device
        local_sd_image = self.local_sd_image
        remote_sd_image = self.device._sd_image
        rsync_ssh = self.ssh + ' -i %s' % self.identity_file
        device.context.run_command('rsync -avpz --progress -e "%s" root@%s:%s %s' % (rsync_ssh, self.host, remote_sd_image, local_sd_image), failok=False)
        with image_partition_mounted(local_sd_image, partition) as mount_point:
            yield mount_point
        device.context.run_command('rsync -avpz --progress -e "%s" %s root@%s:%s' % (rsync_ssh, local_sd_image, self.host, remote_sd_image))

target_class = DynamicVmTarget
