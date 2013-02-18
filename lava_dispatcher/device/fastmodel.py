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

import codecs
import contextlib
import cStringIO
import logging
import os
import shutil
import stat
import subprocess

import lava_dispatcher.device.boot_options as boot_options

from lava_dispatcher.device.target import (
    Target
)
from lava_dispatcher.client.lmc_utils import (
    image_partition_mounted,
    generate_android_image,
    generate_fastmodel_image,
    )
from lava_dispatcher.downloader import (
    download_image,
    )
from lava_dispatcher.test_data import (
    create_attachment,
    )
from lava_dispatcher.utils import (
    ensure_directory,
    extract_targz,
    logging_spawn,
    logging_system,
    DrainConsoleOutput,
    )


class FastModelTarget(Target):

    PORT_PATTERN = 'terminal_0: Listening for serial connection on port (\d+)'
    ANDROID_WALLPAPER = 'system/wallpaper_info.xml'
    SYS_PARTITION = 2
    DATA_PARTITION = 5

    def __init__(self, context, config):
        super(FastModelTarget, self).__init__(context, config)

        self._sim_proc = None

    def _customize_android(self):
        with image_partition_mounted(self._sd_image, self.DATA_PARTITION) as d:
            wallpaper = '%s/%s' % (d, self.ANDROID_WALLPAPER)
            # delete the android active wallpaper as slows things down
            logging_system('sudo rm -f %s' % wallpaper)

        with image_partition_mounted(self._sd_image, self.SYS_PARTITION) as d:
            with open('%s/etc/mkshrc' % d, 'a') as f:
                f.write('\n# LAVA CUSTOMIZATIONS\n')
                #make sure PS1 is what we expect it to be
                f.write('PS1="%s"\n' % self.ANDROID_TESTER_PS1)
                # fast model usermode networking does not support ping
                f.write('alias ping="echo LAVA-ping override 1 received"\n')

        self.deployment_data = Target.android_deployment_data

    def _copy_axf(self, partno, subdir):
        self._axf = None
        with image_partition_mounted(self._sd_image, partno) as mntdir:
            subdir = os.path.join(mntdir, subdir)
            for fname in self.config.simulator_axf_files:
                src = os.path.join(subdir, fname)
                if os.path.exists(src):
                    odir = os.path.dirname(self._sd_image)
                    self._axf = '%s/%s' % (odir, os.path.split(src)[1])
                    shutil.copyfile(src, self._axf)
                    break

            if not self._axf:
                raise RuntimeError('No AXF found, %r' % os.listdir(subdir))

    def deploy_android(self, boot, system, data):
        logging.info("Deploying Android on %s" % self.config.hostname)

        self._boot = download_image(boot, self.context, decompress=False)
        self._data = download_image(data, self.context, decompress=False)
        self._system = download_image(system, self.context, decompress=False)

        self._sd_image = '%s/android.img' % os.path.dirname(self._system)

        generate_android_image(
            'vexpress-a9', self._boot, self._data, self._system, self._sd_image
            )

        self._copy_axf(self.config.boot_part, '')

        self._customize_android()

    def deploy_linaro(self, hwpack=None, rootfs=None, bootloader='u_boot'):
        hwpack = download_image(hwpack, self.context, decompress=False)
        rootfs = download_image(rootfs, self.context, decompress=False)
        odir = os.path.dirname(rootfs)

        generate_fastmodel_image(hwpack, rootfs, odir, bootloader)
        self._sd_image = '%s/sd.img' % odir
        self._axf = None
        for f in self.config.simulator_axf_files:
            fname = os.path.join(odir, f)
            if os.path.exists(fname):
                self._axf = fname
                break
        if not self._axf:
            raise RuntimeError('No AXF found, %r' % os.listdir(odir))

        self._customize_linux(self._sd_image)

    def deploy_linaro_prebuilt(self, image):
        self._sd_image = download_image(image, self.context)
        self._copy_axf(self.config.root_part, 'boot')

        self._customize_linux(self._sd_image)

    @contextlib.contextmanager
    def file_system(self, partition, directory):
        with image_partition_mounted(self._sd_image, partition) as mntdir:
            path = '%s/%s' % (mntdir, directory)
            ensure_directory(path)
            yield path

    def extract_tarball(self, tarball_url, partition, directory='/'):
        logging.info('extracting %s to target' % tarball_url)

        with image_partition_mounted(self._sd_image, partition) as mntdir:
            tb = download_image(tarball_url, self.context, decompress=False)
            extract_targz(tb, '%s/%s' % (mntdir, directory))

    def _fix_perms(self):
        ''' The directory created for the image download/creation gets created
        with tempfile.mkdtemp which grants permission only to the creator of
        the directory. We need group access because the dispatcher may run
        the simulator as a different user
        '''
        d = os.path.dirname(self._sd_image)
        os.chmod(d, stat.S_IRWXG | stat.S_IRWXU)
        os.chmod(self._sd_image, stat.S_IRWXG | stat.S_IRWXU)
        os.chmod(self._axf, stat.S_IRWXG | stat.S_IRWXU)

        #lmc ignores the parent directories group owner
        st = os.stat(d)
        os.chown(self._axf, st.st_uid, st.st_gid)
        os.chown(self._sd_image, st.st_uid, st.st_gid)

    def power_off(self, proc):
        super(FastModelTarget, self).power_off(proc)
        if self._sim_proc is not None:
            self._sim_proc.close()
            self._sim_proc = None

    def _create_rtsm_ostream(self, ofile):
        """the RTSM binary uses the windows code page(cp1252), but the
        dashboard and celery needs data with a utf-8 encoding"""
        return codecs.EncodedFile(ofile, 'cp1252', 'utf-8')

    def _drain_sim_proc(self):
        """pexpect will continue to get data for the simproc process. We need
        to keep this pipe drained so that it won't get full and then stop block
        the process from continuing to execute"""

        f = cStringIO.StringIO()
        self._sim_proc.logfile = self._create_rtsm_ostream(f)
        DrainConsoleOutput(proc=self._sim_proc).start()

    def power_on(self):
        if self._sim_proc is not None:
            logging.warning("device was still on, shutting down")
            self.power_off(None)

        self._fix_perms()

        options = boot_options.as_string(self, join_pattern=' -C %s=%s')
        sim_cmd = self.config.simulator_command.format(
            AXF=self._axf, IMG=self._sd_image)
        sim_cmd = '%s %s' % (sim_cmd, options)

        # the simulator proc only has stdout/stderr about the simulator
        # we hook up into a telnet port which emulates a serial console
        logging.info('launching fastmodel with command %r' % sim_cmd)
        self._sim_proc = self.context.spawn(sim_cmd, timeout=1200)
        self._sim_proc.expect(self.PORT_PATTERN, timeout=300)
        self._serial_port = self._sim_proc.match.groups()[0]
        logging.info('serial console port on: %s' % self._serial_port)

        match = self._sim_proc.expect(["ERROR: License check failed!",
                                       "Simulation is started"])
        if match == 0:
            raise RuntimeError("fast model license check failed")

        self._drain_sim_proc()

        logging.info('simulator is started connecting to serial port')
        self.proc = logging_spawn(
            'telnet localhost %s' % self._serial_port,
            timeout=1200)
        self.proc.logfile_read = self._create_rtsm_ostream(
            self.proc.logfile_read)
        return self.proc

    def get_test_data_attachments(self):
        '''returns attachments to go in the "lava_results" test run'''
        # if the simulator never got started we won't even get to a logfile
        if getattr(self._sim_proc, 'logfile', None) is not None:
            if getattr(self._sim_proc.logfile, 'getvalue', None) is not None:
                content = self._sim_proc.logfile.getvalue()
                return [create_attachment('rtsm.log', content)]
        return []

    def get_device_version(self):
        cmd = self.config.simulator_version_command
        try:
            return subprocess.check_output(cmd, shell=True).strip()
        except subprocess.CalledProcessError:
            return "unknown"


target_class = FastModelTarget
