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
        'kvm-aarch64': lambda: kvm_adapter,
    }

    def __init__(self, context, config):

        super(DynamicVmTarget, self).__init__(context, config)

        device_type = config.dynamic_vm_backend_device_type
        if device_type not in self.supported_backends.keys():
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

    def deploy_linaro_kernel(self, kernel, ramdisk, dtb, overlays, rootfs, nfsrootfs, image, bootloader, firmware, bl0, bl1,
                             bl2, bl31, rootfstype, bootloadertype, target_type, qemu_pflash=None):
        self.backend.deploy_linaro_kernel(kernel, ramdisk, dtb, overlays, rootfs, nfsrootfs, image, bootloader, firmware, bl0,
                                          bl1, bl2, bl31, rootfstype, bootloadertype, target_type, qemu_pflash=qemu_pflash)
        self.backend_adapter.copy_images()

    def deploy_linaro_prebuilt(self, image, dtb, rootfstype, bootfstype, bootloadertype, qemu_pflash=None):
        self.backend.deploy_linaro_prebuilt(image, dtb, rootfstype, bootfstype, bootloadertype, qemu_pflash=qemu_pflash)
        self.backend_adapter.copy_images()

    def power_off(self, proc):
        self.backend.power_off(proc)
        self.backend_adapter.cleanup()

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

    ssh_options = '-o Compression=yes -o UserKnownHostsFile=/dev/null -o PasswordAuthentication=no -o StrictHostKeyChecking=no -o LogLevel=FATAL'
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
        self.vm_images_dir = '/lava-vm-images/%s' % device.config.hostname
        self.qemu_binary = device.config.qemu_binary

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
        self.run_on_host('rm -rf %s' % self.vm_images_dir)
        self.run_on_host('mkdir -p %s' % self.vm_images_dir)

        device = self.device
        self.local_sd_image = device._sd_image  # save local image location
        device._sd_image = self.copy_image(device._sd_image)
        device._kernel = self.copy_image(device._kernel)
        device._dtb = self.copy_image(device._dtb)
        device._ramdisk = self.copy_image(device._ramdisk)
        device._firmware = self.copy_image(device._firmware)
        if device._qemu_pflash is not None:
            device._qemu_pflash = map(self.copy_image, device._qemu_pflash)

    def copy_image(self, local_image):
        if local_image is None:
            return None

        image = os.path.basename(local_image)
        logging.info("Copying %s to the host device", image)

        vm_images_dir = self.vm_images_dir
        remote_image = '%s/%s' % (vm_images_dir, os.path.basename(local_image))
        self.scp_to_host(local_image, remote_image)

        return remote_image

    def amend_config(self):
        device = self.device
        ssh = self.ssh + ' root@' + self.host + ' -i ' + self.identity_file
        device.config.qemu_binary = '%s -- %s' % (ssh, self.qemu_binary)

    @contextlib.contextmanager
    def mount(self, partition):
        device = self.device

        remote_sd_image = self.device._sd_image
        remote_sd_location = os.path.dirname(remote_sd_image)
        remote_sd_name = os.path.basename(remote_sd_image)

        dir_mount_point = os.path.join(device.scratch_dir, self.host)
        if not os.path.exists(dir_mount_point):
            os.makedirs(dir_mount_point)

        local_sd_image = os.path.join(dir_mount_point, remote_sd_name)

        run = device.context.run_command

        run('sshfs %s:%s %s %s -o IdentityFile=%s' % (self.host, remote_sd_location, dir_mount_point, self.ssh_options, self.identity_file), failok=False)

        try:
            with image_partition_mounted(local_sd_image, partition) as mount_point:
                yield mount_point
        finally:
            run('fusermount -u %s' % dir_mount_point, failok=False)

    def cleanup(self):
        if self.device._sd_image:
            image = self.device._sd_image
        elif self.device._ramdisk:
            image = self.device._ramdisk
        if image:
            self.run_on_host(
                'pkill -f "qemu-system-arm.*%s"' % image, failok=True)
        self.run_on_host('rm -rf %s' % self.vm_images_dir)

    def run_on_host(self, cmd, failok=False):
        ssh = self.ssh + ' -i %s' % self.identity_file
        run = self.device.context.run_command
        run('%s root@%s -- %s' % (ssh, self.host, cmd), failok)

    def scp_to_host(self, src, dst):
        scp = self.scp + ' -i %s' % self.identity_file
        run = self.device.context.run_command
        run('%s %s root@%s:%s' % (scp, src, self.host, dst), failok=False)

    def scp_from_host(self, src, dst):
        scp = self.scp + ' -i %s' % self.identity_file
        run = self.device.context.run_command
        run('%s root@%s:%s %s' % (scp, self.host, src, dst), failok=False)


target_class = DynamicVmTarget
