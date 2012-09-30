# Copyright (C) 2011 Linaro Limited
#
# Author: Michael Hudson-Doyle <michael.hudson@linaro.org>
# Author: Paul Larson <paul.larson@linaro.org>
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
import time
import traceback

import pexpect

from lava_dispatcher.device.target import (
    Target
    )
from lava_dispatcher.utils import (
    logging_spawn,
    logging_system,
    )
from lava_dispatcher.client.base import (
    CriticalError,
    NetworkCommandRunner,
    OperationFailed,
    )


class MasterImageTarget(Target):

    def __init__(self, context, config):
        super(MasterImageTarget, self).__init__(context, config)

        self.master_ip = None

        if config.pre_connect_command:
            logging_system(config.pre_connect_command)

        self.proc = self._connect_carefully(config.connection_command)
        atexit.register(self._close_logging_spawn)

    def power_on(self):
        ''' responsible for powering on the target device and returning an
        instance of a pexpect session
        '''
        raise NotImplementedError('power_on')

    def power_off(self, proc):
        ''' responsible for powering off the target device
        '''
        raise NotImplementedError('power_off')

    def deploy_linaro(self, hwpack, rfs):
        raise NotImplementedError('deploy_image')

    def deploy_android(self, boot, system, userdata):
        raise NotImplementedError('deploy_android_image')

    def deploy_linaro_prebuilt(self, image):
        raise NotImplementedError('deploy_linaro_prebuilt')

    def _connect_carefully(self, cmd):
        retry_count = 0
        retry_limit = 3

        port_stuck_message = 'Data Buffering Suspended\.'
        conn_closed_message = 'Connection closed by foreign host\.'

        expectations = {
            port_stuck_message: 'reset-port',
            'Connected\.\r': 'all-good',
            conn_closed_message: 'retry',
            pexpect.TIMEOUT: 'all-good',
            }
        patterns = []
        results = []
        for pattern, result in expectations.items():
            patterns.append(pattern)
            results.append(result)

        while retry_count < retry_limit:
            proc = logging_spawn(cmd, timeout=1200)
            proc.logfile_read = self.sio
            #serial can be slow, races do funny things, so increase delay
            proc.delaybeforesend = 1
            logging.info('Attempting to connect to device')
            match = proc.expect(patterns, timeout=10)
            result = results[match]
            logging.info('Matched %r which means %s', patterns[match], result)
            if result == 'retry':
                proc.close(True)
                retry_count += 1
                time.sleep(5)
                continue
            elif result == 'all-good':
                return proc
            elif result == 'reset-port':
                reset_port = self.config.reset_port_command
                if reset_port:
                    logging_system(reset_port)
                else:
                    raise OperationFailed("no reset_port command configured")
                proc.close(True)
                retry_count += 1
                time.sleep(5)
        raise OperationFailed("could execute connection_command successfully")

    def _close_logging_spawn(self):
        self.proc.close(True)

    def boot_master_image(self):
        """
        reboot the system, and check that we are in a master shell
        """
        logging.info("Boot the system master image")
        try:
            self._soft_reboot()
            self.proc.expect(self.config.image_boot_msg, timeout=300)
            self._in_master_shell(300)
        except:
            logging.exception("in_master_shell failed")
            self._hard_reboot()
            self.proc.expect(self.config.image_boot_msg, timeout=300)
            self._in_master_shell(300)
        self.proc.sendline('export PS1="$PS1 [rc=$(echo \$?)]: "')
        self.proc.expect(
            self.config.master_str, timeout=120, lava_no_logging=1)

        lava_proxy = self.context.config.lava_proxy
        if lava_proxy:
            logging.info("Setting up http proxy")
            self.proc.sendline("export http_proxy=%s" % lava_proxy)
            self.proc.expect(self.config.master_str, timeout=30)
        logging.info("System is in master image now")

    def _in_master_shell(self, timeout=10):
        self.proc.sendline("")
        match_id = self.proc.expect(
            [self.config.master_str, pexpect.TIMEOUT],
            timeout=timeout, lava_no_logging=1)
        if match_id == 1:
            raise OperationFailed

        if not self.master_ip:
            runner = MasterCommandRunner(self)
            self.master_ip = runner.get_master_ip()

    @contextlib.contextmanager
    def _as_master(self):
        """A session that can be used to run commands in the master image.

        Anything that uses this will have to be done differently for images
        that are not deployed via a master image (e.g. using a JTAG to blow
        the image onto the card or testing under QEMU).
        """
        try:
            self._in_master_shell()
            yield MasterCommandRunner(self)
        except OperationFailed:
            self.boot_master_image()
            yield MasterCommandRunner(self)

    def _soft_reboot(self):
        logging.info("Perform soft reboot the system")
        self.master_ip = None
        # make sure in the shell (sometime the earlier command has not exit)
        self.proc.sendcontrol('c')
        self.proc.sendline(self.config.soft_boot_cmd)
        # Looking for reboot messages or if they are missing, the U-Boot
        # message will also indicate the reboot is done.
        match_id = self.proc.expect(
            ['Restarting system.', 'The system is going down for reboot NOW',
                'Will now restart', 'U-Boot', pexpect.TIMEOUT], timeout=120)
        if match_id not in [0, 1, 2, 3]:
            raise Exception("Soft reboot failed")

    def _hard_reboot(self):
        logging.info("Perform hard reset on the system")
        self.master_ip = None
        if self.config.hard_reset_command != "":
            logging_system(self.config.hard_reset_command)
        else:
            self.proc.send("~$")
            self.proc.sendline("hardreset")
        self.proc.empty_buffer()


class MasterCommandRunner(NetworkCommandRunner):
    """A CommandRunner to use when the board is booted into the master image.
    """

    def __init__(self, target):
        super(MasterCommandRunner, self).__init__(
            target, target.config.master_str)

    def get_master_ip(self):
        logging.info("Waiting for network to come up")
        try:
            self.wait_network_up()
        except:
            msg = "Unable to reach LAVA server, check network"
            logging.error(msg)
            self._client.sio.write(traceback.format_exc())
            raise CriticalError(msg)

        pattern1 = "<(\d?\d?\d?\.\d?\d?\d?\.\d?\d?\d?\.\d?\d?\d?)>"
        cmd = ("ifconfig %s | grep 'inet addr' | awk -F: '{print $2}' |"
                "awk '{print \"<\" $1 \">\"}'" %
                self._client.config.default_network_interface)
        self.run(
            cmd, [pattern1, pexpect.EOF, pexpect.TIMEOUT], timeout=5)
        if self.match_id != 0:
            msg = "Unable to determine master image IP address"
            logging.error(msg)
            raise CriticalError(msg)

        ip = self.match.group(1)
        logging.debug("Master image IP is %s" % ip)
        return ip

    def has_partition_with_label(self, label):
        if not label:
            return False

        path = '/dev/disk/by-label/%s' % label
        return self.is_file_exist(path)

    def is_file_exist(self, path):
        cmd = 'ls %s' % path
        rc = self.run(cmd, failok=True)
        if rc == 0:
            return True
        return False


target_class = MasterImageTarget
