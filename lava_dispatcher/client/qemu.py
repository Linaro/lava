# Copyright (C) 2011 Linaro Limited
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
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along
# with this program; if not, see <http://www.gnu.org/licenses>.

import contextlib
import logging
import os
import pexpect

from lava_dispatcher.client.base import (
    CommandRunner,
    LavaClient,
    )
from lava_dispatcher.client.lmc_utils import (
    generate_image,
    image_partition_mounted,
    )
from lava_dispatcher.downloader import (
    download_image,
    )
from lava_dispatcher.utils import (
    logging_spawn,
    logging_system,
    )



class LavaQEMUClient(LavaClient):

    def __init__(self, context, config):
        super(LavaQEMUClient, self).__init__(context, config)
        self._lava_image = None

    def deploy_linaro(self, hwpack=None, rootfs=None, image=None, rootfstype='ext3'):
        if image is None:
            odir = self.get_www_scratch_dir()
            image_file = generate_image(self, hwpack, rootfs, odir, rootfstype)
        else:
            image_file = download_image(image, self.context)
        self._lava_image = image_file
        with image_partition_mounted(self._lava_image, self.root_part) as mntdir:
            logging_system('echo %s > %s/etc/hostname' % (self.tester_hostname,
                mntdir))

    @contextlib.contextmanager
    def _mnt_prepared_for_qemu(self, mntdir):
        logging_system('sudo cp %s/etc/resolv.conf %s/etc/resolv.conf.bak' % (mntdir, mntdir))
        logging_system('sudo cp %s/etc/hosts %s/etc/hosts.bak' % (mntdir, mntdir))
        logging_system('sudo cp /etc/hosts %s/etc/hosts' % (mntdir,))
        logging_system('sudo cp /etc/resolv.conf %s/etc/resolv.conf' % (mntdir,))
        logging_system('sudo cp /usr/bin/qemu-arm-static %s/usr/bin/' % (mntdir,))
        try:
            yield
        finally:
            logging_system('sudo mv %s/etc/resolv.conf.bak %s/etc/resolv.conf' % (mntdir, mntdir))
            logging_system('sudo mv %s/etc/hosts.bak %s/etc/hosts' % (mntdir, mntdir))
            logging_system('sudo rm %s/usr/bin/qemu-arm-static' % (mntdir,))

    @contextlib.contextmanager
    def _chroot_into_rootfs_session(self):
        with image_partition_mounted(self._lava_image, self.root_part) as mntdir:
            with self._mnt_prepared_for_qemu(mntdir):
                cmd = pexpect.spawn('chroot ' + mntdir, logfile=self.sio, timeout=None)
                try:
                    cmd.sendline('export PS1="root@host-mount:# [rc=$(echo \$?)] "')
                    cmd.expect('root@host-mount:#')
                    yield CommandRunner(cmd, 'root@host-mount:#')
                finally:
                    cmd.sendline('exit')
                    cmd.close()

    def reliable_session(self):
        # We could use _chroot_into_rootfs_session instead, but in my testing
        # as of 2011-11-30, the network works better in a tested image than
        # qemu-arm-static works to run the complicated commands of test
        # installation.
        return self.tester_session()

    def boot_master_image(self):
        raise RuntimeError("QEMU devices do not have a master image to boot.")

    def boot_linaro_image(self):
        """
        Boot the system to the test image
        """
        if self.proc is not None:
            self.proc.sendline('sync')
            self.proc.expect([self.tester_str, pexpect.TIMEOUT], timeout=10)
            self.proc.close()
        qemu_cmd = ('%s -M %s -drive if=%s,cache=writeback,file=%s '
                    '-clock unix -device usb-kbd -device usb-mouse -usb '
                    '-device usb-net,netdev=mynet -netdev user,id=mynet '
                    '-net nic -net user -nographic') % (
            self.context.config.get('default_qemu_binary'),
            self.device_option('qemu_machine_type'),
            self.device_option('qemu_drive_interface'),
            self._lava_image)
        logging.info('launching qemu with command %r' % qemu_cmd)
        self.proc = logging_spawn(
            qemu_cmd, logfile=self.sio, timeout=None)
        self.proc.expect(self.tester_str, timeout=300)
        # set PS1 to include return value of last command
        self.proc.sendline('export PS1="$PS1 [rc=$(echo \$?)]: "')
        self.proc.expect(self.tester_str, timeout=10)

    def retrieve_results(self, result_disk):
        if self.proc is not None:
            self.proc.sendline('sync')
            self.proc.expect([self.tester_str, pexpect.TIMEOUT], timeout=10)
            self.proc.close()
        tardir = mkdtemp()
        tarfile = os.path.join(tardir, "lava_results.tgz")
        with image_partition_mounted(self._lava_image, self.root_part) as mntdir:
            logging_system(
                'tar czf %s -C %s%s .' % (
                    tarfile, mntdir, self.context.lava_result_dir))
            logging_system('rm %s%s/*.bundle' % (mntdir, self.context.lava_result_dir))
        return 'pass', '', tarfile
