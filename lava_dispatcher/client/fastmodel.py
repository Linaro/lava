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

from lava_dispatcher.client.base import (
    CommandRunner,
    LavaClient,
    )
from lava_dispatcher.client.lmc_utils import (
    image_partition_mounted,
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

    def __init__(self, context, config):
        super(LavaFastModelClient, self).__init__(context, config)
        self._sim_binary = config.get('simulator_binary', None)
        lic_server = config.get('license_server', None)
        if not self._sim_binary or not lic_server:
            raise RuntimeError("The device type config for this device is "
                "requires settings for 'simulator_binary' and 'license_server'")

        os.putenv('ARMLMD_LICENSE_FILE', lic_server)

    def deploy_image(self, image, axf, initrd, kernel, dtb):
        self._axf = download_image(axf, self.context)
        self._initrd = download_image(initrd, self.context)
        self._kernel = download_image(kernel, self.context)
        self._dtb = download_image(dtb, self.context)
        self._sd_image = download_image(image, self.context)

        logging.debug("image file is: %s" % self._sd_image)
        with image_partition_mounted(self._sd_image, self.root_part) as mntdir:
            logging_system('sudo echo linaro > %s/etc/hostname' % mntdir)

    def _close_sim_proc(self):
        self._sim_proc.close(True)

    def _close_serial_proc(self):
        self.proc.close(True)

    def _get_sim_cmd(self):
        return ("%s -a coretile.cluster0.*=%s "
            "-C motherboard.smsc_91c111.enabled=1 "
            "-C motherboard.hostbridge.userNetworking=1 "
            "-C motherboard.mmc.p_mmc_file=%s "
            "-C coretile.cache_state_modelled=0 "
            "-C coretile.cluster0.cpu0.semihosting-enable=1 "
            "-C coretile.cluster0.cpu0.semihosting-cmd_line=\""
                "--kernel %s --initrd %s --fdt %s -- "
                "mem=2046M console=ttyAMA0,115200 root=/dev/mmcblk0p2\"" ) % (
            self._sim_binary, self._axf, self._sd_image, self._kernel,
                self._initrd, self._dtb)

    def boot_linaro_image(self):
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

        logging.info('simulator is started connecting to serial port')
        self.proc = logging_spawn(
            'telnet localhost %s' % self._serial_port,
            logfile=self.sio,
            timeout=90)
        atexit.register(self._close_serial_proc)

        self.proc.expect(self.tester_str, timeout=300)
        self.proc.sendline('export PS1="$PS1 [rc=$(echo \$?)]: "')
        self.proc.expect(self.tester_str, timeout=10)

