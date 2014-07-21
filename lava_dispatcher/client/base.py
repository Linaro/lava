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
import os
import pexpect
import sys
import time
import traceback
import json
from lava_dispatcher.device.target import (
    get_target,
)
from lava_dispatcher.utils import (
    mkdtemp,
    mk_targz,
    read_content,
    wait_for_prompt,
)
from lava_dispatcher.errors import (
    NetworkError,
    OperationFailed,
    CriticalError,
    ADBConnectError,
)


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

    def wait_for_prompt(self, timeout=-1):
        wait_for_prompt(self._connection, self._prompt_str, timeout)

    def get_connection(self):
        return self._connection

    def run(self, cmd, response=None, timeout=-1,
            failok=False, wait_prompt=True, log_in_host=None):
        """Run `cmd` and wait for a shell response.

        :param cmd: The command to execute.
        :param response: A pattern or sequences of patterns to pass to
            .expect().
        :param timeout: How long to wait for 'response' (if specified) and the
            shell prompt, defaulting to forever.
        :param failok: The command can fail or not, if it is set False and
            command fail, an OperationFail exception will raise
        :param log_in_host: If set, the input and output of the command will be
            logged in it
        :return: The exit value of the command, if wait_for_rc not explicitly
            set to False during construction.
        """
        self._connection.empty_buffer()
        if log_in_host is not None:
            self._connection.logfile = open(log_in_host, "a")
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

        if wait_prompt:
            self.wait_for_prompt(timeout)

            if self._prompt_str_includes_rc:
                rc = int(self._connection.match.group(1))
                if rc != 0 and not failok:
                    raise RuntimeError(
                        "executing %r failed with code %s" % (cmd, rc))
            else:
                rc = None
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

    def get_target_ip(self):
        logging.info("Waiting for network to come up")
        try:
            self.wait_network_up()
        except NetworkError:
            logging.exception("Unable to reach LAVA server")
            raise

        pattern1 = "<(\d?\d?\d?\.\d?\d?\d?\.\d?\d?\d?\.\d?\d?\d?)>"
        cmd = ("ifconfig `ip route get %s | sed 's/.*via\ //' | cut -d ' ' -f3` | grep 'inet addr' |"
               "awk -F: '{split($2,a,\" \"); print \"<\" a[1] \">\"}'" %
               self._client.context.config.lava_server_ip)
        self.run(
            cmd, [pattern1, pexpect.EOF, pexpect.TIMEOUT], timeout=300)
        if self.match_id != 0:
            msg = "Unable to determine target image IP address"
            logging.exception(msg)
            raise NetworkError(msg)

        ip = self.match.group(1)
        if ip == "127.0.0.1":
            msg = "Got localhost (127.0.0.1) as IP address"
            logging.exception(msg)
            raise NetworkError(msg)
        logging.debug("Target image IP is %s" % ip)
        return ip

    def _check_network_up(self):
        """Internal function for checking network once."""
        lava_server_ip = self._client.context.config.lava_server_ip
        self.run(
            "LC_ALL=C ping -W4 -c1 %s" % lava_server_ip,
            ["1 received|1 packets received", "0 received|0 packets received", "Network is unreachable"],
            timeout=60, failok=True)
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
            client.target_device.tester_ps1_pattern,
            prompt_str_includes_rc=client.target_device.tester_ps1_includes_rc)

    def export_display(self):
        self.run("su - linaro -c 'DISPLAY=:0 xhost local:'", failok=True)
        self.run("export DISPLAY=:0")


class AndroidTesterCommandRunner(NetworkCommandRunner):
    """A CommandRunner to use when the board is booted into the android image.

    See `LavaClient.android_tester_session`.
    """

    def __init__(self, client):
        super(AndroidTesterCommandRunner, self).__init__(
            client, client.target_device.tester_ps1_pattern,
            prompt_str_includes_rc=client.target_device.tester_ps1_includes_rc)
        self.dev_name = None

    def connect(self):
        if self._client.target_device.config.android_adb_over_tcp:
            self._setup_adb_over_tcp()
        elif self._client.target_device.config.android_adb_over_usb:
            self._setup_adb_over_usb()
        else:
            raise CriticalError('ADB not configured for TCP or USB')

    def _setup_adb_over_tcp(self):
        logging.info("adb connect over default network interface")
        self.dev_ip = self.get_default_nic_ip()
        if self.dev_ip is None:
            raise OperationFailed("failed to get board ip address")
        try:
            ## just disconnect the adb connection in case is remained
            ## by last action or last job
            ## that connection should be expired already
            self.android_adb_over_tcp_disconnect()
        except KeyboardInterrupt:
            raise KeyboardInterrupt
        except:
            ## ignore all exception
            ## this just in case of exception
            pass
        self.android_adb_over_tcp_connect()
        self.wait_until_attached()

    def _setup_adb_over_usb(self):
        self.run('getprop ro.serialno', response=['[0-9A-Fa-f]{16}'])
        self.dev_name = self.match.group(0)

    def disconnect(self):
        if self._client.target_device.config.android_adb_over_tcp:
            self.android_adb_over_tcp_disconnect()

    # adb cound be connected through network
    def android_adb_over_tcp_connect(self):
        dev_ip = self.dev_ip
        pattern1 = "connected to (\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d{1,5})"
        pattern2 = "already connected to (\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d{1,5})"
        pattern3 = "unable to connect to"

        adb_port = self._client.config.android_adb_port
        cmd = "adb connect %s:%s" % (dev_ip, adb_port)
        logging.info("Execute adb command on host: %s" % cmd)
        adb_proc = pexpect.spawn(cmd, timeout=300, logfile=sys.stdout)
        match_id = adb_proc.expect([pattern1, pattern2, pattern3, pexpect.EOF])
        if match_id in [0, 1]:
            self.dev_name = adb_proc.match.groups()[0]
        else:
            raise ADBConnectError(('Failed to connected to device with'
                                   ' command:%s') % cmd)

    def android_adb_over_tcp_disconnect(self):
        dev_ip = self.dev_ip
        adb_port = self._client.config.android_adb_port
        cmd = "adb disconnect %s:%s" % (dev_ip, adb_port)
        logging.info("Execute adb command on host: %s" % cmd)
        pexpect.run(cmd, timeout=300, logfile=sys.stdout)

    def get_default_nic_ip(self):
        network_interface = self._client.get_android_adb_interface()
        try:
            ip = self._get_default_nic_ip_by_ifconfig(network_interface)
        except KeyboardInterrupt:
            raise KeyboardInterrupt
        except:
            logging.exception("_get_default_nic_ip_by_ifconfig failed")
            return None

        return ip

    def _get_default_nic_ip_by_ifconfig(self, nic_name):
        # Check network ip and setup adb connection
        try:
            self.wait_network_up()
        except KeyboardInterrupt:
            raise KeyboardInterrupt
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

        raise ADBConnectError(
            "The android device(%s) isn't attached" % self._client.hostname)

    def wait_home_screen(self):
        timeout = self._client.config.android_home_screen_timeout
        activity_pat = self._client.config.android_wait_for_home_screen_activity
        #waiting for the home screen displayed
        try:
            self.run('logcat -s ActivityManager:I',
                     response=[activity_pat],
                     timeout=timeout, wait_prompt=False)
        except pexpect.TIMEOUT:
            msg = "The home screen was not displayed"
            logging.critical(msg)
            raise CriticalError(msg)
        finally:
            #send ctrl+c to exit the logcat command,
            #and make the latter command can be run on the normal
            #command line session, instead of the session of logcat command
            self._connection.sendcontrol("c")
            self.run('')

    def check_device_state(self):
        (rc, output) = commands.getstatusoutput('adb devices')
        if rc != 0:
            return False
        expect_line = '%s\tdevice' % self.dev_name
        for line in output.splitlines():
            if line.strip() == expect_line:
                return True
        return False


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
        self.proc = None
        # used for apt-get in lava-test.py
        self.aptget_cmd = "apt-get"
        self.target_device = get_target(context, config)
        self.vm_group = VmGroupHandler(self)

    def deploy_linaro_android(self, boot, system, data, rootfstype,
                              bootloadertype, target_type):
        self.target_device.deploy_android(boot, system, data, rootfstype,
                                          bootloadertype, target_type)

    def deploy_linaro(self, hwpack, rootfs, image, dtb, rootfstype, bootloadertype):
        if image is None:
            if hwpack is None or rootfs is None:
                raise CriticalError(
                    "must specify both hwpack and rootfs \
                     when not specifying image")
        elif hwpack is not None or rootfs is not None:
            raise CriticalError(
                "cannot specify hwpack or rootfs when specifying image")

        if image is None:
            self.target_device.deploy_linaro(hwpack, rootfs, dtb,
                                             rootfstype, bootloadertype)
        else:
            self.target_device.deploy_linaro_prebuilt(image, dtb, rootfstype,
                                                      bootloadertype)

    def deploy_linaro_kernel(self, kernel, ramdisk, dtb, modules, rootfs,
                             nfsrootfs, bootloader, firmware, bl1, bl2, bl31,
                             rootfstype, bootloadertype, target_type):
        self.target_device.deploy_linaro_kernel(kernel, ramdisk, dtb, modules, rootfs,
                                                nfsrootfs, bootloader, firmware,
                                                bl1, bl2, bl31, rootfstype,
                                                bootloadertype, target_type)

    @contextlib.contextmanager
    def runner(self):
        """
        Powers on the target and yields a CommandRunner object.

        The yielded CommandRunner is ready to receive commands on the
        just-booted system.
        """

        self.boot_linaro_image()

        ps1_pattern = self.target_device.tester_ps1_pattern
        ps1_includes_rc = self.target_device.tester_ps1_includes_rc
        proc = self.proc

        runner = CommandRunner(proc, ps1_pattern, ps1_includes_rc)

        yield runner

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
        session.connect()

        try:
            yield session
        finally:
            session.disconnect()

    def reliable_session(self):
        return self.tester_session()

    def _in_test_shell(self):
        """
        Check that we are in a shell on the test image
        """
        if self.proc is None:
            raise OperationFailed
        self.proc.sendline("")
        prompt = self.target_device.tester_ps1_pattern
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

    def _boot_linaro_image(self):
        self.proc = self.target_device.power_on()

    def _boot_linaro_android_image(self):
        """Booting android or ubuntu style images don't differ much"""

        logging.info('ensuring ADB port is ready')
        adb_port = self.target_device.config.android_adb_port
        while self.context.run_command("sh -c 'netstat -an | grep %s.*TIME_WAIT'" % adb_port) == 0:
            logging.info("waiting for TIME_WAIT %s socket to finish" % adb_port)
            time.sleep(3)

        self._boot_linaro_image()

    def boot_linaro_image(self):
        """
        Reboot the system to the test image
        """
        logging.info("Boot the test image")
        boot_attempts = self.config.boot_retries
        attempts = 0
        in_linaro_image = False
        while (attempts < boot_attempts) and (not in_linaro_image):
            logging.info("Booting the test image. Attempt: %d" % (attempts + 1))
            timeout = self.config.boot_linaro_timeout
            TESTER_PS1_PATTERN = self.target_device.tester_ps1_pattern

            self.vm_group.wait_for_vms()

            start = time.time()
            try:
                self._boot_linaro_image()
            except (OperationFailed, pexpect.TIMEOUT) as e:
                msg = "Boot linaro image failed: %s" % e
                logging.info(msg)
                attempts += 1
                continue

            try:
                wait_for_prompt(self.proc, TESTER_PS1_PATTERN, timeout=timeout)
            except pexpect.TIMEOUT as e:
                msg = "Timeout waiting for boot prompt: %s" % e
                logging.info(msg)
                attempts += 1
                continue

            # Record boot time metadata
            boottime = "{0:.2f}".format(time.time() - start)
            boottime_meta = {'kernel-boot-time': boottime}
            self.context.test_data.add_metadata(boottime_meta)
            logging.debug("Kernel boot time: %s seconds" % boottime)

            self.setup_proxy(TESTER_PS1_PATTERN)
            logging.info("System is in test image now")
            logging.debug("mount information")
            self.proc.sendline('mount')
            wait_for_prompt(self.proc, TESTER_PS1_PATTERN, timeout=timeout)
            logging.debug("root directory information")
            self.proc.sendline('ls -l /')
            wait_for_prompt(self.proc, TESTER_PS1_PATTERN, timeout=timeout)
            logging.debug("free space information")
            self.proc.sendline('df -h')
            wait_for_prompt(self.proc, TESTER_PS1_PATTERN, timeout=timeout)
            logging.debug("IP addr information")
            self.proc.sendline('ip addr')
            wait_for_prompt(self.proc, TESTER_PS1_PATTERN, timeout=timeout)
            in_linaro_image = True
            logging.debug("Checking for vm-group host")

            self.vm_group.start_vms()

        if not in_linaro_image:
            msg = "Could not get the test image booted properly"
            logging.critical(msg)
            raise CriticalError(msg)

    def get_www_scratch_dir(self):
        """ returns a temporary directory available for downloads that gets
        deleted when the process exits """
        return mkdtemp(self.context.config.lava_image_tmpdir)

    def get_test_data_attachments(self):
        '''returns attachments to go in the "lava_results" test run'''
        return self.target_device.get_test_data_attachments()

    def retrieve_results(self, result_disk):
        self.target_device.power_off(self.proc)

        td = self.target_device
        tar = os.path.join(td.scratch_dir, 'lava_results.tgz')
        result_dir = self.context.config.lava_result_dir
        with td.file_system(td.config.root_part, result_dir) as mnt:
            mk_targz(tar, mnt)
        return tar

    def finish(self):
        self.target_device.power_off(self.proc)
        self.vm_group.vm_finished()

    # Android stuff

    def get_android_adb_interface(self):
        return self.config.default_network_interface

    def boot_linaro_android_image(self, adb_check=False):
        """Reboot the system to the test android image."""
        boot_attempts = self.config.boot_retries
        attempts = 0
        in_linaro_android_image = False

        while (attempts < boot_attempts) and (not in_linaro_android_image):
            logging.info("Booting the Android test image. Attempt: %d" %
                         (attempts + 1))
            TESTER_PS1_PATTERN = self.target_device.tester_ps1_pattern
            timeout = self.config.android_boot_prompt_timeout

            start = time.time()
            try:
                self._boot_linaro_android_image()
            except (OperationFailed, pexpect.TIMEOUT) as e:
                msg = "Failed to boot the Android test image: %s" % e
                logging.info(msg)
                attempts += 1
                continue

            try:
                wait_for_prompt(self.proc, TESTER_PS1_PATTERN, timeout=timeout)
            except pexpect.TIMEOUT:
                msg = "Timeout waiting for boot prompt"
                logging.info(msg)
                attempts += 1
                continue

            # Record boot time metadata
            boottime = "{0:.2f}".format(time.time() - start)
            boottime_meta = {'kernel-boot-time': boottime}
            self.context.test_data.add_metadata(boottime_meta)
            logging.debug("Kernel boot time: %s seconds" % boottime)

            #TODO: set up proxy

            if not self.config.android_adb_over_usb:
                try:
                    self._disable_adb_over_usb()
                except (OperationFailed, pexpect.TIMEOUT) as e:
                    msg = "Failed to disable adb: %s" % e
                    logging.info(msg)
                    attempts += 1
                    continue

            if self.config.android_disable_suspend:
                try:
                    self._disable_suspend()
                except (OperationFailed, pexpect.TIMEOUT, CriticalError) as e:
                    msg = "Failed to disable suspend: %s" % e
                    logging.info(msg)
                    attempts += 1
                    continue

            if self.config.enable_network_after_boot_android:
                time.sleep(1)
                try:
                    self._enable_network()
                except (OperationFailed, pexpect.TIMEOUT) as e:
                    msg = "Failed to enable network: %s" % e
                    logging.info(msg)
                    attempts += 1
                    continue

            if self.config.android_adb_over_tcp:
                try:
                    self._enable_adb_over_tcp()
                except (OperationFailed, pexpect.TIMEOUT) as e:
                    msg = "Failed to enable adp over tcp: %s" % e
                    logging.info(msg)
                    attempts += 1
                    continue

            in_linaro_android_image = True

        if not in_linaro_android_image:
            msg = "Could not get the Android test image booted properly"
            logging.critical(msg)
            raise CriticalError(msg)

        #check if the adb connection can be created.
        #by adb connect dev_ip command
        if adb_check:
            try:
                session = AndroidTesterCommandRunner(self)
                session.connect()
            finally:
                session.disconnect()

    def _disable_suspend(self):
        """ disable the suspend of images.
        this needs wait unitl the home screen displayed"""
        session = AndroidTesterCommandRunner(self)
        try:
            if self.config.android_wait_for_home_screen:
                session.wait_home_screen()
        except KeyboardInterrupt:
            raise KeyboardInterrupt
        except:
            # ignore home screen exception if it is a health check job.
            if not ('health_check' in self.context.job_data and self.context.job_data["health_check"] is True):
                raise
            else:
                logging.info("Skip raising exception on the home screen has not displayed for health check jobs")
        # When disablesuspend executes it waits for home screen unless
        # --no-wait is passed.
        session.run(
            '/system/bin/disablesuspend.sh --no-wait',
            timeout=self.config.disablesuspend_timeout)

    def _enable_network(self):
        session = AndroidTesterCommandRunner(self)
        session.run("netcfg", timeout=20)
        session.run("netcfg %s up" % self.config.default_network_interface, timeout=20)
        session.run("netcfg %s dhcp" % self.config.default_network_interface, timeout=300)
        session.run("ifconfig " + self.config.default_network_interface, timeout=20)

    def _enable_adb_over_tcp(self):
        logging.info("Enabling ADB over TCP")
        session = AndroidTesterCommandRunner(self)
        adb_port = self.config.android_adb_port
        session.run('setprop service.adb.tcp.port %s' % adb_port)
        session.run('stop adbd')
        session.run('start adbd')
        try:
            session.connect()
        finally:
            session.disconnect()

    def _disable_adb_over_usb(self):
        logging.info("Disabling adb over USB")
        session = AndroidTesterCommandRunner(self)
        session.run('echo 0>/sys/class/android_usb/android0/enable')


class VmGroupHandler(object):

    def __init__(self, client):
        self.client = client
        self.vms_started = False

    @property
    def is_vm_group_job(self):
        return 'is_vmhost' in self.client.context.test_data.metadata

    @property
    def is_host(self):
        return self.is_vm_group_job and self.client.context.test_data.metadata['is_vmhost'] == "true"

    @property
    def is_vm(self):
        return self.is_vm_group_job and self.client.context.test_data.metadata['is_vmhost'] == "false"

    @property
    def auto_start_vms(self):
        return self.is_vm_group_job and self.client.context.test_data.metadata['auto_start_vms'] == 'true'

    def start_vms(self):
        if not self.is_host:
            return

        runner = NetworkCommandRunner(
            self.client,
            self.client.target_device.tester_ps1_pattern,
            self.client.target_device.tester_ps1_includes_rc
        )

        logging.debug("vm-group host: injecting SSH public key")
        public_key_file = os.path.join(os.path.dirname(__file__), '../device/dynamic_vm_keys/lava.pub')
        public_key = read_content(public_key_file).strip()
        runner.run('mkdir -p /root/.ssh && echo "%s" >> /root/.ssh/authorized_keys' % public_key)

        logging.debug("vm-group host: obtaining host IP for guest VM.")
        try:
            host_ip = runner.get_target_ip()
        except NetworkError as e:
            raise CriticalError("Failed to get network up: " % e)
        runner.run('export _LAVA_VM_GROUP_HOST_IP=%s' % host_ip)

        if self.auto_start_vms:
            # send a message to each guest
            msg = {"request": "lava_send", "messageID": "lava_vm_start", "message": {"host_ip": host_ip}}
            reply = self.client.context.transport(json.dumps(msg))
            if reply == "nack":
                raise CriticalError("lava_vm_start failed")
            logging.info("[ACTION-B] LAVA VM start, using %s" % host_ip)
            self.vms_started = True

    def wait_for_vms(self):
        if not (self.is_host and self.vms_started):
            return

        logging.info("Waiting for all VMs to finish ...")

        self.client.context.transport(
            json.dumps({
                "request": "lava_send",
                "messageID": "lava_vm_stop",
                "message": {}
            })
        )

        reply = self.client.context.transport(
            json.dumps({
                "request": "lava_wait_all",
                "messageID": "lava_vm_stop"
            })
        )

        if reply == 'nack':
            raise CriticalError("Failure while waiting for VMs to finish")
        logging.info("All VMs finished, proceeding with reboot")

        self.vms_started = False

    def vm_finished(self):
        if not (self.is_vm):
            return

        msg = {"request": "lava_send", "messageID": "lava_vm_stop", "message": {}}
        reply = self.client.context.transport(json.dumps(msg))
        if reply == 'nack':
            raise CriticalError("Failure when notifying VM finish to group")
        logging.info("VM finished")
