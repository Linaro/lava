# Copyright (C) 2017 Linaro Limited
#
# Author: Matthew Hart <matthew.hart@linaro.org>
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

from lava_dispatcher.pipeline.action import (
    Action,
    Pipeline,
    InfrastructureError,
    JobError
)
from lava_dispatcher.pipeline.utils.strings import map_kernel_uboot


class PrepareKernelAction(Action):
    """
    Populate the pipeline with a kernel conversion action, if needed
    """
    def __init__(self):
        super(PrepareKernelAction, self).__init__()
        self.name = "prepare-kernel"
        self.summary = "add a kernel conversion"
        self.description = "populates the pipeline with a kernel conversion action"

    def populate(self, parameters):
        self.internal_pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        # the logic here can be upgraded in future if needed with more parameters to the deploy.
        if 'u-boot' in self.job.device['actions']['boot']['methods']:
            self.internal_pipeline.add_action(UBootPrepareKernelAction())


class UBootPrepareKernelAction(Action):
    """
    Convert kernels to uImage
    """
    def __init__(self):
        super(UBootPrepareKernelAction, self).__init__()
        self.name = "uboot-prepare-kernel"
        self.description = "convert kernel to uimage"
        self.summary = "prepare/convert kernel"
        self.bootcommand = None
        self.params = None
        self.kernel_type = None
        self.mkimage_conversion = False

    def create_uimage(self, kernel, load_addr, xip, arch, output):  # pylint: disable=too-many-arguments
        load_addr = int(load_addr, 16)
        uimage_path = '%s/%s' % (os.path.dirname(kernel), output)
        if xip:
            entry_addr = load_addr + 64
        else:
            entry_addr = load_addr
        cmd = "mkimage -A %s -O linux -T kernel" \
              " -C none -a 0x%x -e 0x%x" \
              " -d %s %s" % (arch, load_addr,
                             entry_addr, kernel,
                             uimage_path)
        if self.run_command(cmd.split(' ')):
            return uimage_path
        else:
            raise InfrastructureError("uImage creation failed")

    def validate(self):
        super(UBootPrepareKernelAction, self).validate()
        if 'parameters' not in self.job.device['actions']['deploy']:
            return
        self.params = self.job.device['actions']['deploy']['parameters']
        self.kernel_type = self.get_namespace_data(
            action='download_action',
            label='type',
            key='kernel'
        )
        self.bootcommand = None
        if 'parameters' not in self.job.device:
            if self.kernel_type:
                self.errors = "Kernel boot type is not supported by this device."
        if self.kernel_type:
            self.set_namespace_data(action=self.name, label='prepared-kernel', key='exists', value=True)
            self.bootcommand = map_kernel_uboot(self.kernel_type, self.job.device.get('parameters', None))
            self.kernel_type = str(self.kernel_type).lower()
            if self.bootcommand not in self.job.device['parameters']:
                self.errors = "Requested kernel boot type '%s' is not supported by this device." % self.bootcommand
            if self.kernel_type == "bootm" or self.kernel_type == "bootz" or self.kernel_type == "booti":
                self.errors = "booti, bootm and bootz are deprecated, please use 'image', 'uimage' or 'zimage'"
            if 'mkimage_arch' not in self.params:
                self.errors = "Missing architecture for uboot mkimage support (mkimage_arch in u-boot parameters)"
            if self.bootcommand == 'bootm' and self.kernel_type != 'uimage':
                self.mkimage_conversion = True
        self.set_namespace_data(
            action='uboot-prepare-kernel', label='bootcommand',
            key='bootcommand', value=self.bootcommand)

    def run(self, connection, max_end_time, args=None):
        connection = super(UBootPrepareKernelAction, self).run(connection, max_end_time, args)
        if not self.kernel_type:
            return connection  # idempotency
        old_kernel = self.get_namespace_data(
            action='download_action',
            label='file',
            key='kernel'
        )
        if self.mkimage_conversion:
            self.logger.info("Converting downloaded kernel to a uImage")
            filename = self.get_namespace_data(action='download_action', label='kernel', key='file')
            load_addr = self.job.device['parameters'][self.bootcommand]['kernel']
            if 'text_offset' in self.job.device['parameters']:
                load_addr = self.job.device['parameters']['text_offset']
            arch = self.params['mkimage_arch']
            self.create_uimage(filename, load_addr, False, arch, 'uImage')
            new_kernel = os.path.dirname(old_kernel) + '/uImage'
            # overwriting namespace data
            self.set_namespace_data(
                action='prepare-kernel',
                label='file', key='kernel', value=new_kernel)
        return connection
