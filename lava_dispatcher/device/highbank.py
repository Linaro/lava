# Copyright (C) 2012 Linaro Limited
#
# Author: Michael Hudson-Doyle <michael.hudson@linaro.org>
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
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.    See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along
# with this program; if not, see <http://www.gnu.org/licenses>.

import contextlib
import logging

from lava_dispatcher.client.base import (
    NetworkCommandRunner,
)
from lava_dispatcher.device.target import (
    Target
)
from lava_dispatcher.utils import (
    download_image,
    logging_system,
    logging_spawn,
)


class HighbankTarget(Target):

    def __init__(self, context, config):
        super(HighbankTarget, self).__init__(context, config)

    def deploy_linaro(self, hwpack, rfs, bootloader):
        with self._boot_master() as runner:
            rootfs = download_image(rfs, self.context, decompress=False)
            kernel_deb = download_image(hwpack, self.context, decompress=False)
            self._format_testpartition(runner)
            # _customize_linux assumes an image :(

    def power_on(self):
        XXX
        return proc

    def power_off(self, proc):
        XXX
        pass

    @contextlib.contextmanager
    def file_system(self, partition, directory):

        XXX

    def get_device_version(self):
        XXX

    MASTER_PS1 = 'root@master# '
    MASTER_PS1_PATTERN = 'root@master# '

    @contextlib.contextmanager
    def _boot_master(self):
        proc = logging_spawn(self.config.connection_command)
        self._ipmi("chassis bootdev pxe")
        self._ipmi("chassis power off")
        self._ipmi("chassis power on")
        proc.expect("\(initramfs\)")
        proc.sendline('export PS1="%s"' % self.MASTER_PS1)
        proc.expect(self.MASTER_PS1_PATTERN, timeout=120, lava_no_logging=1)
        try:
            yield HBMasterCommandRunner(self)
        finally:
            proc.close()

    def _ipmi(self, cmd):
        logging_system(
            "ipmitool -H %(ecmeip)s -U admin -P admin " % (self.config.ecmeip,)
            + cmd)

    def _format_testpartition(self, runner, fstype='ext4'):
        logging.info("Formatting boot and rootfs partitions")
        runner.run('mkfs -t %s -q /dev/disk/by-label/rootfs -L rootfs'
            % fstype, timeout=1800)
        runner.run('mkfs.vfat /dev/disk/by-label/boot -n boot')

    def _target_extract(self, runner, tar_url, dest, timeout=-1, num_retry=5):
        decompression_char = ''
        if tar_url.endswith('.gz') or tar_url.endswith('.tgz'):
            decompression_char = 'z'
        elif tar_url.endswith('.bz2'):
            decompression_char = 'j'
        else:
            raise RuntimeError('bad file extension: %s' % tar_url)

        runner.run(
            'wget --no-check-certificate --no-proxy '
            '--connect-timeout=30 -S --progress=dot -e dotbytes=2M '
            '-O- %s | '
            'tar --warning=no-timestamp --numeric-owner -C %s -x%sf -'
            % (tar_url, dest, decompression_char),
            timeout=timeout)
        return

class HBMasterCommandRunner(NetworkCommandRunner):
    """A CommandRunner to use when the board is booted into the master image.
    """
    def __init__(self, target):
        super(HBMasterCommandRunner, self).__init__(
            target, target.MASTER_PS1_PATTERN, prompt_str_includes_rc=False)

target_class = HighbankTarget
