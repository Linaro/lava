# Copyright (C) 2012 Linaro Limited
#
# Author: Andy Doan <andy.doan@linaro.org>
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

import atexit
import contextlib
import logging
import os
import pexpect
import shutil
import stat
import threading

from lava_dispatcher.client.base import (
    CommandRunner,
    LavaClient,
    )
from lava_dispatcher.client.lmc_utils import (
    image_partition_mounted,
    generate_android_image,
    generate_fastmodel_image,
    get_partition_offset,
    )
from lava_dispatcher.downloader import (
    download_image,
    )
from lava_dispatcher.utils import (
    logging_spawn,
    logging_system,
    )


class LavaFastModelClient(LavaClient):

    PORT_PATTERN = 'terminal_0: Listening for serial connection on port (\d+)'
    ANDROID_WALLPAPER = 'system/wallpaper_info.xml'
    SYS_PARTITION = 2
    DATA_PARTITION = 5

    def __init__(self, context, config):
        super(LavaFastModelClient, self).__init__(context, config)
        self._sim_binary = config.get('simulator_binary', None)
        lic_server = config.get('license_server', None)
        self.git_url_disablesuspend_sh = config.get('git_url_disablesuspend_sh',
                                                    None)
        if not self._sim_binary or not lic_server:
            raise RuntimeError("The device type config for this device "
                "requires settings for 'simulator_binary' and 'license_server'")

        os.putenv('ARMLMD_LICENSE_FILE', lic_server)
        self._sim_proc = None

    def get_android_adb_interface(self):
        return 'lo'

    def _customize_android(self):
        with image_partition_mounted(self._sd_image, self.DATA_PARTITION) as d:
            wallpaper = '%s/%s' % (d, self.ANDROID_WALLPAPER)
            # delete the android active wallpaper as slows things down
            logging_system('sudo rm -f %s' % wallpaper)

        with image_partition_mounted(self._sd_image, self.SYS_PARTITION) as d:
            script_path = '%s/%s' % (d, '/system/bin/disablesuspend.sh')
            if self.git_url_disablesuspend_sh:
                logging_system('sudo wget %s -O %s' % (
                                               self.git_url_disablesuspend_sh,
                                               script_path))
                logging_system('sudo chmod +x %s' % script_path)
                logging_system('sudo chown :2000 %s' % script_path)

            #make sure PS1 is what we expect it to be
            logging_system(
                'sudo sh -c \'echo "PS1=%s: ">> %s/etc/mkshrc\'' % (self.tester_str, d))
            # fast model usermode networking does not support ping
            logging_system(
                'sudo sh -c \'echo "alias ping=\\\"echo LAVA-ping override 1 received\\\"">> %s/etc/mkshrc\'' % d)

    def _customize_ubuntu(self):
        with image_partition_mounted(self._sd_image, self.root_part) as mntdir:
            logging_system('sudo echo linaro > %s/etc/hostname' % mntdir)

    def deploy_image(self, image, axf, is_android=False):
        self._axf = download_image(axf, self.context)
        self._sd_image = download_image(image, self.context)

        logging.debug("image file is: %s" % self._sd_image)
        if is_android:
            self._customize_android()
        else:
            self._customize_ubuntu()

    def _copy_axf(self, partno, fname):
        with image_partition_mounted(self._sd_image, partno) as mntdir:
            src = '%s/%s' % (mntdir,fname)
            odir = os.path.dirname(self._sd_image)
            self._axf = '%s/%s' % (odir, os.path.split(src)[1])
            shutil.copyfile(src, self._axf)

    def deploy_linaro_android(self, boot, system, data, pkg=None,
                                rootfstype='ext4'):
        logging.info("Deploying Android on %s" % self.hostname)

        self._boot = download_image(boot, self.context, decompress=False)
        self._data = download_image(data, self.context, decompress=False)
        self._system = download_image(system, self.context, decompress=False)

        self._sd_image = '%s/android.img' % os.path.dirname(self._system)

        generate_android_image(
            'vexpress-a9', self._boot, self._data, self._system, self._sd_image)

        self._copy_axf(self.boot_part, 'linux-system-ISW.axf')

        self._customize_android()

    def deploy_linaro(self, hwpack=None, rootfs=None, image=None,
                      kernel_matrix=None, rootfstype='ext3'):
        if image is None:
            if hwpack is None or rootfs is None:
                raise CriticalError(
                    "must specify both hwpack and rootfs when not specifying image")
        elif hwpack is not None or rootfs is not None:
            raise CriticalError(
                    "cannot specify hwpack or rootfs when specifying image")

        if image is None:
            hwpack = download_image(hwpack, self.context, decompress=False)
            rootfs = download_image(rootfs, self.context, decompress=False)
            odir = os.path.dirname(rootfs)

            generate_fastmodel_image(hwpack, rootfs, odir)
            self._sd_image = '%s/sd.img' % odir
            self._axf = '%s/img.axf' % odir
        else:
            self._sd_image = download_image(image, self.context)
            self._copy_axf(self.root_part, 'boot/img.axf')

        self._customize_ubuntu()

    def _close_sim_proc(self):
        self._sim_proc.close(True)

    def _close_serial_proc(self):
        self.proc.close(True)

    def _fix_perms(self):
        ''' The directory created for the image download/creation gets created
        with tempfile.mkdtemp which grants permission only to the creator of
        the directory. We need group access because the dispatcher may run
        the simulator as a different user
        '''
        d = os.path.dirname(self._sd_image)
        os.chmod(d, stat.S_IRWXG|stat.S_IRWXU)
        os.chmod(self._sd_image, stat.S_IRWXG|stat.S_IRWXU)
        os.chmod(self._axf, stat.S_IRWXG|stat.S_IRWXU)

        #lmc ignores the parent directories group owner
        st = os.stat(d)
        os.chown(self._axf, st.st_uid, st.st_gid)
        os.chown(self._sd_image, st.st_uid, st.st_gid)

    def _get_sim_cmd(self):
        return ("%s -a coretile.cluster0.*=%s "
            "-C motherboard.smsc_91c111.enabled=1 "
            "-C motherboard.hostbridge.userNetworking=1 "
            "-C motherboard.mmc.p_mmc_file=%s "
            "-C coretile.cache_state_modelled=0 "
            "-C coretile.cluster0.cpu0.semihosting-enable=1 "
            "-C motherboard.hostbridge.userNetPorts='5555=5555'") % (
            self._sim_binary, self._axf, self._sd_image)

    def _stop(self):
        if self.proc is not None:
            self.proc.close()
        if self._sim_proc is not None:
            self._sim_proc.close()

    def _boot_linaro_image(self):
        self._stop()

        self._fix_perms()
        sim_cmd = self._get_sim_cmd()

        # the simulator proc only has stdout/stderr about the simulator
        # we hook up into a telnet port which emulates a serial console
        logging.info('launching fastmodel with command %r' % sim_cmd)
        self._sim_proc = logging_spawn(
            sim_cmd,
            logfile=self.sio,
            timeout=1200)
        atexit.register(self._close_sim_proc)
        self._sim_proc.expect(self.PORT_PATTERN, timeout=300)
        self._serial_port = self._sim_proc.match.groups()[0]
        logging.info('serial console port on: %s' % self._serial_port)

        match = self._sim_proc.expect(["ERROR: License check failed!",
                                       "Simulation is started"])
        if match == 0:
            raise RuntimeError("fast model license check failed")

        _pexpect_drain(self._sim_proc).start()

        logging.info('simulator is started connecting to serial port')
        self.proc = logging_spawn(
            'telnet localhost %s' % self._serial_port,
            logfile=self.sio,
            timeout=90)
        atexit.register(self._close_serial_proc)

    def _boot_linaro_android_image(self):
        ''' booting android or ubuntu style images don't differ for FastModel'''
        self._boot_linaro_image()

    def reliable_session(self):
        return self.tester_session()

    def retrieve_results(self, result_disk):
        self._stop()

        tardir = os.path.dirname(self._sd_image)
        tarfile = os.path.join(tardir, 'lava_results.tgz')
        with image_partition_mounted(self._sd_image, self.root_part) as mnt:
            logging_system(
                'tar czf %s -C %s%s .' % (
                    tarfile, mnt, self.context.lava_result_dir))
        return 'pass', '', tarfile

class _pexpect_drain(threading.Thread):
    ''' The simulator process can dump a lot of information to its console. If
    don't actively read from it, the pipe will get full and the process will
    be blocked. This allows us to keep the pipe empty so the process can run
    '''
    def __init__(self, proc):
        threading.Thread.__init__(self)
        self.proc = proc
        self.daemon = True #allows thread to die when main main proc exits
    def run(self):
        # change simproc's stdout so it doesn't overlap the stdout from our
        # serial console logging
        self.proc.logfile = open('/dev/null', 'w')
        self.proc.drain()
