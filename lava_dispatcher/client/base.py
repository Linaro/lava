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

import commands
import contextlib
import logging
import pexpect
import sys
import time
import traceback

import lava_dispatcher.utils as utils

from cStringIO import StringIO

from lava_dispatcher.test_data import create_attachment


class CommandRunner(object):
    """A convenient way to run a shell command and wait for a shell prompt.

    The main interface is run().  Subclasses exist to (a) be more conveniently
    constructed in some situations and (b) define higher level functions that
    involve executing multiple commands.
    """

    def __init__(self, connection, prompt_str, prompt_str_includes_rc):
        """

        :param connection: A pexpect.spawn-like object.
        :param prompt_str: The shell prompt to wait for.
        :param prompt_str_includes_rc: Whether prompt_str includes a pattern
            matching the return code of the command.
        """
        self._connection = connection
        self._prompt_str = prompt_str
        self._prompt_str_includes_rc = prompt_str_includes_rc
        self.match_id = None
        self.match = None

    def run(self, cmd, response=None, timeout=-1, failok=False):
        """Run `cmd` and wait for a shell response.

        :param cmd: The command to execute.
        :param response: A pattern or sequences of patterns to pass to
            .expect().
        :param timeout: How long to wait for 'response' (if specified) and the
            shell prompt, defaulting to forever.
        :param failok: The command can fail or not, if it is set False and
            command fail, an OperationFail exception will raise
        :return: The exit value of the command, if wait_for_rc not explicitly
            set to False during construction.
        """
        self._connection.empty_buffer()
        self._connection.sendline(cmd)
        start = time.time()
        if response is not None:
            self.match_id = self._connection.expect(response, timeout=timeout)
            self.match = self._connection.match
            if self.match == pexpect.TIMEOUT:
                return None
            # If a non-trivial timeout was specified, it is held to apply to
            # the whole invocation, so now reduce the time we'll wait for the
            # shell prompt.
            if timeout > 0:
                timeout -= time.time() - start
                # But not too much; give at least a little time for the shell
                # prompt to appear.
                if timeout < 1:
                    timeout = 1
        else:
            self.match_id = None
            self.match = None

        prompt_wait_count = 0
        if timeout == -1:
            timeout = self._connection.timeout
        while True:
            try:
                self._connection.expect(self._prompt_str, timeout=timeout/10.0)
            except pexpect.TIMEOUT:
                if prompt_wait_count < 10:
                    prompt_wait_count += 1
                    self._connection.sendline('')
                    continue
                else:
                    raise
            else:
                break
        if self._prompt_str_includes_rc:
            rc = int(self._connection.match.group(1))
            if rc != 0 and not failok:
                raise OperationFailed(
                    "executing %r failed with code %s" % (cmd, rc))
        else:
            rc = None
        return rc


class NetworkCommandRunner(CommandRunner):
    """A CommandRunner with some networking utility methods."""

    def __init__(self, client, prompt_str, prompt_str_includes_rc):
        CommandRunner.__init__(
            self, client.proc, prompt_str,
            prompt_str_includes_rc=prompt_str_includes_rc)
        self._client = client

    def _check_network_up(self):
        """Internal function for checking network once."""
        lava_server_ip = self._client.context.config.lava_server_ip
        self.run(
            "LC_ALL=C ping -W4 -c1 %s" % lava_server_ip,
            ["1 received", "0 received", "Network is unreachable"],
            timeout=5, failok=True)
        if self.match_id == 0:
            return True
        else:
            return False

    def wait_network_up(self, timeout=300):
        """Wait until the networking is working."""
        now = time.time()
        while time.time() < now + timeout:
            if self._check_network_up():
                return
        raise NetworkError


class TesterCommandRunner(CommandRunner):
    """A CommandRunner to use when the board is booted into the test image.

    See `LavaClient.tester_session`.
    """

    def __init__(self, client):
        CommandRunner.__init__(
            self,
            client.proc,
            client.target_device.deployment_data['TESTER_PS1_PATTERN'],
            prompt_str_includes_rc=client.target_device.deployment_data[
                'TESTER_PS1_INCLUDES_RC'])

    def export_display(self):
        self.run("su - linaro -c 'DISPLAY=:0 xhost local:'", failok=True)
        self.run("export DISPLAY=:0")


class AndroidTesterCommandRunner(NetworkCommandRunner):
    """A CommandRunner to use when the board is booted into the android image.

    See `LavaClient.android_tester_session`.
    """

    def __init__(self, client):
        super(AndroidTesterCommandRunner, self).__init__(
            client, client.target_device.deployment_data['TESTER_PS1_PATTERN'],
            prompt_str_includes_rc=client.target_device.deployment_data['TESTER_PS1_INCLUDES_RC'])
        self.dev_name = None

    # adb cound be connected through network
    def android_adb_connect(self, dev_ip):
        pattern1 = "connected to (\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d{1,5})"
        pattern2 = "already connected to (\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d{1,5})"
        pattern3 = "unable to connect to"

        cmd = "adb connect %s" % dev_ip
        logging.info("Execute adb command on host: %s" % cmd)
        adb_proc = pexpect.spawn(cmd, timeout=300, logfile=sys.stdout)
        match_id = adb_proc.expect([pattern1, pattern2, pattern3, pexpect.EOF])
        if match_id in [0, 1]:
            self.dev_name = adb_proc.match.groups()[0]

    def android_adb_disconnect(self, dev_ip):
        cmd = "adb disconnect %s" % dev_ip
        logging.info("Execute adb command on host: %s" % cmd)
        pexpect.run(cmd, timeout=300, logfile=sys.stdout)

    def get_default_nic_ip(self):
        network_interface = self._client.get_android_adb_interface()
        try:
            ip = self._get_default_nic_ip_by_ifconfig(network_interface)
        except:
            logging.exception("_get_default_nic_ip_by_ifconfig failed")
            return None

        return ip

    def _get_default_nic_ip_by_ifconfig(self, nic_name):
        # Check network ip and setup adb connection
        try:
            self.wait_network_up()
        except:
            logging.warning(traceback.format_exc())
            return None
        ip_pattern = "%s: ip (\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}) mask" % nic_name
        try:
            self.run(
                "ifconfig %s" % nic_name, [ip_pattern, pexpect.EOF], timeout=60)
        except Exception as e:
            raise NetworkError("ifconfig can not match ip pattern for %s:%s" % (nic_name, e))

        if self.match_id == 0:
            match_group = self.match.groups()
            if len(match_group) > 0:
                return match_group[0]
        return None

    def wait_until_attached(self):
        for count in range(3):
            if self.check_device_state():
                return
            time.sleep(3)

        raise NetworkError(
            "The android device(%s) isn't attached" % self._client.hostname)

    def wait_home_screen(self):
        cmd = 'getprop init.svc.bootanim'
        for count in range(100):
            try:
                self.run(cmd, response=['stopped'], timeout=5)
                if self.match_id == 0:
                    return True
            except pexpect.TIMEOUT:
                time.sleep(1)
        raise GeneralError('The home screen has not displayed')

    def check_device_state(self):
        (rc, output) = commands.getstatusoutput('adb devices')
        if rc != 0:
            return False
        expect_line = '%s\tdevice' % self.dev_name
        for line in output.splitlines():
            if line.strip() == expect_line:
                return True
        return False

    def retrieve_results(self, result_disk):
        raise NotImplementedError(self.retrieve_results)


class LavaClient(object):
    """
    LavaClient manipulates the target board, bootup, reset, power off the
    board, sends commands to board to execute.

    The main interfaces to execute commands on the board are the \*_session()
    methods.  These should be used as context managers, for example::

        with client.tester_session() as session:
            session.run('ls')

    Each method makes sure the board is booted into the appropriate state
    (tester image, chrooted into a partition, etc) and additionally
    android_tester_session connects to the board via adb while in the 'with'
    block.
    """

    def __init__(self, context, config):
        self.context = context
        self.config = config
        self.hostname = config.hostname
        self.sio = SerialIO(sys.stdout)
        self.proc = None
        # used for apt-get in lava-test.py
        self.aptget_cmd = "apt-get"

    @contextlib.contextmanager
    def tester_session(self):
        """A session that can be used to run commands booted into the test
        image."""
        try:
            self._in_test_shell()
        except OperationFailed:
            self.boot_linaro_image()
        yield TesterCommandRunner(self)

    @contextlib.contextmanager
    def android_tester_session(self):
        """A session that can be used to run commands booted into the android
        test image.

        Additionally, adb is connected while in the with block using this
        manager.
        """
        try:
            self._in_test_shell()
        except OperationFailed:
            self.boot_linaro_android_image()

        session = AndroidTesterCommandRunner(self)
        logging.info("adb connect over default network interface")
        dev_ip = session.get_default_nic_ip()
        if dev_ip is None:
            raise OperationFailed("failed to get board ip address")
        try:
            ## just disconnect the adb connection in case is remained
            ## by last action or last job
            ## that connection should be expired already
            session.android_adb_disconnect(dev_ip)
        except:
            ## ignore all exception
            ## this just in case of exception
            pass
        session.android_adb_connect(dev_ip)
        session.wait_until_attached()
        try:
            session.wait_home_screen()
        except:
            # ignore home screen exception if it is a health check job.
            if not (self.context.job_data.has_key("health_check") and self.context.job_data["health_check"] == True):
                raise
            else:
                logging.info("Skip raising exception on the home screen has not displayed for health check jobs")
        try:
            yield session
        finally:
            session.android_adb_disconnect(dev_ip)

    def reliable_session(self):
        """
        Return a session rooted in the rootfs to be tested where networking is
        guaranteed to work.
        """
        raise NotImplementedError(self.reliable_session)

    def _in_test_shell(self):
        """
        Check that we are in a shell on the test image
        """
        if self.proc is None:
            raise OperationFailed
        self.proc.sendline("")
        prompt = self.target_device.deployment_data['TESTER_PS1_PATTERN']
        match_id = self.proc.expect([prompt, pexpect.TIMEOUT], timeout=10)
        if match_id == 1:
            raise OperationFailed

    def setup_proxy(self, prompt_str):
        lava_proxy = self.context.config.lava_proxy
        if lava_proxy:
            logging.info("Setting up http proxy")
            # haven't included Android support yet
            # Timeout is 30 seconds because of some underlying
            # problem that causes these commands to sometimes
            # take around 15-20 seconds.
            self.proc.sendline("export http_proxy=%s" % lava_proxy)
            self.proc.expect(prompt_str, timeout=30)
            self.aptget_cmd = ' '.join([self.aptget_cmd,
                "-o Acquire::http::proxy=%s" % lava_proxy])

    def boot_master_image(self):
        raise NotImplementedError(self.boot_master_image)

    def boot_linaro_image(self):
        """
        Reboot the system to the test image
        """
        logging.info("Boot the test image")

        self._boot_linaro_image()
        timeout = self.config.boot_linaro_timeout
        TESTER_PS1_PATTERN = self.target_device.deployment_data['TESTER_PS1_PATTERN']
        self.proc.expect(TESTER_PS1_PATTERN, timeout=timeout)
        self.setup_proxy(TESTER_PS1_PATTERN)
        logging.info("System is in test image now")

    def get_www_scratch_dir(self):
        """ returns a temporary directory available for downloads that gets
        deleted when the process exits """
        return utils.mkdtemp(self.context.config.lava_image_tmpdir)

    def get_test_data_attachments(self):
        '''returns attachments to go in the "lava_results" test run'''
        return [ create_attachment('serial.log', self.sio.getvalue()) ]

    # Android stuff

    def get_android_adb_interface(self):
        return self.config.default_network_interface

    def boot_linaro_android_image(self):
        """Reboot the system to the test android image."""
        self._boot_linaro_android_image()
        match_id = self.proc.expect(
            [self.target_device.deployment_data['TESTER_PS1'], pexpect.TIMEOUT],
            timeout=900)
        if match_id == 1:
            raise OperationFailed("booting into android test image failed")
        #TODO: set up proxy

        # we are tcp'ish adb fans here...
        self._disable_adb_over_usb()

        self._disable_suspend()
        if self.config.enable_network_after_boot_android:
            time.sleep(1)
            self._enable_network()

        self._restart_adb_after_netup()


    def _disable_suspend(self):
        """ disable the suspend of images.
        this needs wait unitl the home screen displayed"""
        session = AndroidTesterCommandRunner(self)
        try:
            session.wait_home_screen()
        except:
            # ignore home screen exception if it is a health check job.
            if not (self.context.job_data.has_key("health_check") and self.context.job_data["health_check"] == True):
                raise
            else:
                logging.info("Skip raising exception on the home screen has not displayed for health check jobs")

        session.run(
            '/system/bin/disablesuspend.sh',
            timeout=self.config.disablesuspend_timeout)

    def _enable_network(self):
        session = AndroidTesterCommandRunner(self)
        session.run("netcfg", timeout=20)
        session.run("netcfg %s up" % self.config.default_network_interface, timeout=20)
        session.run("netcfg %s dhcp" % self.config.default_network_interface, timeout=300)
        session.run("ifconfig " + self.config.default_network_interface, timeout=20)


    def _restart_adb_after_netup(self):
        logging.info("Restart adb after netup")
        session = AndroidTesterCommandRunner(self)
        session.run('setprop service.adb.tcp.port 5555')
        session.run('stop adbd')
        session.run('start adbd')

    def _disable_adb_over_usb(self):
        logging.info("Disabling adb over USB")
        session = AndroidTesterCommandRunner(self)
        session.run('echo 0>/sys/class/android_usb/android0/enable')


class SerialIO(file):
    def __init__(self, logfile):
        self.serialio = StringIO()
        self.logfile = logfile

    def write(self, text):
        self.serialio.write(text)
        self.logfile.write(text)

    def close(self):
        self.serialio.close()
        self.logfile.close()

    def flush(self):
        self.logfile.flush()

    def getvalue(self):
        return self.serialio.getvalue()


class DispatcherError(Exception):
    """
    Base exception and error class for dispatcher
    """


class TimeoutError(DispatcherError):
    """
    The timeout error
    """


class CriticalError(DispatcherError):
    """
    The critical error
    """


class GeneralError(DispatcherError):
    """
    The non-critical error
    """


class NetworkError(CriticalError):
    """
    This is used when a network error occurs, such as failing to bring up
    the network interface on the client
    """


class OperationFailed(GeneralError):
    """
    The exception throws when a file system or system operation fails.
    """
