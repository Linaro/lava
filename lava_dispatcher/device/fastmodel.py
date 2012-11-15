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
import threading
import re
import subprocess

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
    )


class FastModelTarget(Target):

    PORT_PATTERN = 'terminal_0: Listening for serial connection on port (\d+)'
    ANDROID_WALLPAPER = 'system/wallpaper_info.xml'
    SYS_PARTITION = 2
    DATA_PARTITION = 5
    FM_VE = 0
    FM_FOUNDATION = 1
    FASTMODELS = {'ve': FM_VE, 'foundation': FM_FOUNDATION}
    AXF_IMAGES = {FM_VE: 'img.axf', FM_FOUNDATION: 'img-foundation.axf'}

    BOOT_OPTIONS_VE = {
        'motherboard.smsc_91c111.enabled': '1',
        'motherboard.hostbridge.userNetworking': '1',
        'coretile.cache_state_modelled': '0',
        'coretile.cluster0.cpu0.semihosting-enable': '1',
    }

    # a list of allowable values for BOOT_OPTIONS_VE
    BOOT_VALS = ['0', '1']

    def __init__(self, context, config):
        super(FastModelTarget, self).__init__(context, config)
        self._sim_binary = config.simulator_binary
        if not self._sim_binary:
            raise RuntimeError("Missing config option for simulator binary")

        try:
            self._fastmodel_type = self.FASTMODELS[config.fastmodel_type]
        except KeyError:
            raise RuntimeError("The fastmodel type for this device is invalid,"
                " please use 've' or 'foundation'")

        if self._fastmodel_type == self.FM_VE:
            lic_server = config.license_server
            if not lic_server:
                raise RuntimeError("The VE FastModel requires the config "
                    "option 'license_server'")

            os.putenv('ARMLMD_LICENSE_FILE', lic_server)

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

    def _copy_axf(self, partno, fname):
        with image_partition_mounted(self._sd_image, partno) as mntdir:
            src = '%s/%s' % (mntdir, fname)
            odir = os.path.dirname(self._sd_image)
            self._axf = '%s/%s' % (odir, os.path.split(src)[1])
            shutil.copyfile(src, self._axf)

    def deploy_android(self, boot, system, data):
        logging.info("Deploying Android on %s" % self.config.hostname)

        self._boot = download_image(boot, self.context, decompress=False)
        self._data = download_image(data, self.context, decompress=False)
        self._system = download_image(system, self.context, decompress=False)

        self._sd_image = '%s/android.img' % os.path.dirname(self._system)

        generate_android_image(
            'vexpress-a9', self._boot, self._data, self._system, self._sd_image
            )

        self._copy_axf(self.config.boot_part, 'linux-system-ISW.axf')

        self._customize_android()

    def deploy_linaro(self, hwpack=None, rootfs=None):
        hwpack = download_image(hwpack, self.context, decompress=False)
        rootfs = download_image(rootfs, self.context, decompress=False)
        odir = os.path.dirname(rootfs)

        generate_fastmodel_image(hwpack, rootfs, odir)
        self._sd_image = '%s/sd.img' % odir
        self._axf = '%s/%s' % (odir, self.AXF_IMAGES[self._fastmodel_type])

        self._customize_linux(self._sd_image)

    def deploy_linaro_prebuilt(self, image):
        self._sd_image = download_image(image, self.context)
        self._copy_axf(self.config.root_part,
                       'boot/%s' % self.AXF_IMAGES[self._fastmodel_type])

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

    def _boot_options_ve(self):
        options = dict(self.BOOT_OPTIONS_VE)
        for option in self.boot_options:
            keyval = option.split('=')
            if len(keyval) != 2:
                logging.warn("Invalid boot option format: %s" % option)
            elif keyval[0] not in self.BOOT_OPTIONS_VE:
                logging.warn("Invalid boot option: %s" % keyval[0])
            elif keyval[1] not in self.BOOT_VALS:
                logging.warn("Invalid boot option value: %s" % option)
            else:
                options[keyval[0]] = keyval[1]

        return ' '.join(['-C %s=%s' % (k, v) for k, v in options.iteritems()])

    def _get_sim_cmd(self):
        if self._fastmodel_type == self.FM_VE:
            options = self._boot_options_ve()
            return ("%s -a coretile.cluster0.*=%s "
                "-C motherboard.mmc.p_mmc_file=%s "
                "-C motherboard.hostbridge.userNetPorts='5555=5555' %s") % (
                self._sim_binary, self._axf, self._sd_image, options)
        elif self._fastmodel_type == self.FM_FOUNDATION:
            return ("%s --image=%s --block-device=%s --network=nat") % (
                self._sim_binary, self._axf, self._sd_image)

    def power_off(self, proc):
        super(FastModelTarget, self).power_off(proc)
        if self._sim_proc is not None:
            self._sim_proc.close()

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
        _pexpect_drain(self._sim_proc).start()

    def power_on(self):
        self._fix_perms()
        sim_cmd = self._get_sim_cmd()

        # the simulator proc only has stdout/stderr about the simulator
        # we hook up into a telnet port which emulates a serial console
        logging.info('launching fastmodel with command %r' % sim_cmd)
        self._sim_proc = logging_spawn(
            sim_cmd,
            logfile=self.sio,
            timeout=1200)
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
            logfile=self._create_rtsm_ostream(self.sio),
            timeout=1200)
        return self.proc

    def get_test_data_attachments(self):
        '''returns attachments to go in the "lava_results" test run'''
        # if the simulator never got started we won't even get to a logfile
        if getattr(self._sim_proc, 'logfile', None) is not None:
            content = self._sim_proc.logfile.getvalue()
            return [create_attachment('rtsm.log', content)]
        return []

    def get_device_version(self):
        cmd = '%s --version' % self._sim_binary
        try:
            banner = subprocess.check_output(cmd, shell=True)
            return self._parse_fastmodel_version(banner)
        except subprocess.CalledProcessError:
            return "unknown"

    def _parse_fastmodel_version(self, banner):
        match = re.search('Fast Models \[([0-9.]+)', banner)
        if match:
            return match.group(1)
        else:
            return "unknown"


class _pexpect_drain(threading.Thread):
    ''' The simulator process can dump a lot of information to its console. If
    don't actively read from it, the pipe will get full and the process will
    be blocked. This allows us to keep the pipe empty so the process can run
    '''
    def __init__(self, proc):
        threading.Thread.__init__(self)
        self.proc = proc

        self.daemon = True  # allow thread to die when main main proc exits

    def run(self):
        self.proc.drain()

target_class = FastModelTarget
