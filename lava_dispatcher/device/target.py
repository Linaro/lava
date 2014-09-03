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

import contextlib
import os
import shutil
import re
import logging
import time
import pexpect
import subprocess

from lava_dispatcher.device import boot_options
from lava_dispatcher.utils import (
    wait_for_prompt
)
from lava_dispatcher.client.lmc_utils import (
    image_partition_mounted
)
import lava_dispatcher.utils as utils
from lava_dispatcher import deployment_data

from lava_dispatcher.downloader import (
    download_image,
)

from lava_dispatcher.errors import (
    CriticalError,
    OperationFailed,
    NetworkError,
)


class ImagePathHandle(object):

    def __init__(self, image, image_path, config, mount_info):
        if image_path[:5] == "boot:":
            self.part = config.boot_part
            self.part_mntdir = mount_info['boot']
            self.path = image_path[5:]
        elif image_path[:7] == "rootfs:":
            self.part = config.root_part
            self.part_mntdir = mount_info['rootfs']
            self.path = image_path[7:]
        else:
            # FIXME: we can support more patitions here!
            logging.error('The partition we have supported : boot, rootfs. \n\
            And the right image path format is \"<partition>:<path>\".')
            raise CriticalError('Do not support this partition or path format %s yet!' % image_path)

        self.dir_full = os.path.dirname(self.path)
        self.dir_name = os.path.basename(self.dir_full)
        self.file_name = os.path.basename(self.path)
        self.image = image

    def copy_to(self, context, local_path=None):
        # copy file from image to local path
        des_path = None

        # make default local path in the lava
        if local_path is None:
            local_path = utils.mkdtemp(basedir=context.config.lava_image_tmpdir)

        src_path = '%s/%s' % (self.part_mntdir, self.path)
        if not os.path.exists(src_path):
            raise CriticalError('Can not find source in image (%s at part %s)!' % (self.path, self.part))
        if os.path.isdir(src_path):
            if not os.path.exists(local_path):
                des_path = local_path
            else:
                if self.file_name == '':
                    des_name = self.dir_name
                else:
                    des_name = self.file_name
                des_path = os.path.join(local_path, des_name)
            logging.debug("Copying dir from #%s:%s(%s) to %s!", self.part, self.path, src_path, des_path)
            shutil.copytree(src_path, des_path)
        elif os.path.isfile(src_path):
            if not os.path.exists(local_path):
                if os.path.basename(local_path) == '':
                    des_name = os.path.basename(src_path)
                    des_path = os.path.join(local_path, des_name)
                    os.makedirs(local_path)
                else:
                    if not os.path.exists(os.path.dirname(local_path)):
                        os.makedirs(os.path.dirname(local_path))
                    des_path = local_path
            else:
                if os.path.isdir(local_path):
                    des_name = os.path.basename(src_path)
                    des_path = os.path.join(local_path, des_name)
                else:
                    des_path = local_path
            logging.debug("Copying file from #%s:%s(%s) to %s!", self.part, self.path, src_path, des_path)
            shutil.copyfile(src_path, des_path)
        else:
            raise CriticalError('Please check the source file type, we only support file and dir!')

        return des_path

    def copy_from(self, local_path):
        # copy file from local path into image
        src_path = local_path
        if not os.path.exists(src_path):
            raise CriticalError('Can not find source in local server (%s)!' % src_path)

        if os.path.isdir(src_path):
            des_path = '%s/%s' % (self.part_mntdir, self.path)
            if os.path.exists(des_path):
                if os.path.basename(src_path) == '':
                    des_name = os.path.basename(os.path.dirname(src_path))
                else:
                    des_name = os.path.basename(src_path)
                des_path = os.path.join(des_path, des_name)
            logging.debug("Copying dir from %s to #%s:%s(%s)!", des_path, self.part, self.path, src_path)
            shutil.copytree(src_path, des_path)
        elif os.path.isfile(src_path):
            des_path = '%s/%s' % (self.part_mntdir, self.path)
            if not os.path.exists(des_path):
                if os.path.basename(des_path) == '':
                    os.makedirs(des_path)
                    des_name = os.path.basename(src_path)
                    des_path = os.path.join(des_path, des_name)
                else:
                    if not os.path.exists(os.path.dirname(des_path)):
                        os.makedirs(os.path.dirname(des_path))
            else:
                if os.path.isdir(des_path):
                    des_name = os.path.basename(src_path)
                    des_path = os.path.join(des_path, des_name)
            logging.debug("Copying file from %s to #%s:%s(%s)!", des_path, self.part, self.path, src_path)
            shutil.copyfile(src_path, des_path)
        else:
            raise CriticalError('Please check the source file type, we only support file and dir!')

        return des_path

    def remove(self):
        # delete the file/dir from Image
        des_path = '%s/%s' % (self.part_mntdir, self.path)
        if os.path.isdir(des_path):
            logging.debug("Removing dir(%s) %s from #%s partition of image!", des_path, self.path, self.part)
            shutil.rmtree(des_path)
        elif os.path.isfile(des_path):
            logging.debug("Removing file(%s) %s from #%s partition of image!", des_path, self.path, self.part)
            os.remove(des_path)
        else:
            logging.warning('Unrecognized file type or file/dir doesn\'t exist(%s)! Skipped', des_path)


def get_target(context, device_config):
    ipath = 'lava_dispatcher.device.%s' % device_config.client_type
    m = __import__(ipath, fromlist=[ipath])
    return m.target_class(context, device_config)


class Target(object):
    """ Defines the contract needed by the dispatcher for dealing with a
    target device
    """

    def __init__(self, context, device_config):
        self.context = context
        self.config = device_config
        self.boot_options = []
        self._scratch_dir = None
        self.__deployment_data__ = None
        self.mount_info = {'boot': None, 'rootfs': None}

    @property
    def deployment_data(self):
        if self.__deployment_data__:
            return self.__deployment_data__
        else:
            raise RuntimeError("No operating system deployed. "
                               "Did you forget to run a deploy action?")

    @deployment_data.setter
    def deployment_data(self, data):
        self.__deployment_data__ = data

    @property
    def scratch_dir(self):
        if self._scratch_dir is None:
            self._scratch_dir = utils.mkdtemp(
                self.context.config.lava_image_tmpdir)
        return self._scratch_dir

    def power_on(self):
        """ responsible for powering on the target device and returning an
        instance of a pexpect session
        """
        raise NotImplementedError('power_on')

    def deploy_linaro(self, hwpack, rfs, dtb, rootfstype, bootloadertype):
        raise NotImplementedError('deploy_image')

    def deploy_android(self, boot, system, userdata, rootfstype,
                       bootloadertype, target_type):
        raise NotImplementedError('deploy_android_image')

    def deploy_linaro_prebuilt(self, image, dtb, rootfstype, bootloadertype):
        raise NotImplementedError('deploy_linaro_prebuilt')

    def deploy_linaro_kernel(self, kernel, ramdisk, dtb, modules, rootfs,
                             nfsrootfs, bootloader, firmware, bl1, bl2,
                             bl31, rootfstype, bootloadertype, target_type):
        raise NotImplementedError('deploy_linaro_kernel')

    def power_off(self, proc):
        if proc is not None:
            proc.close()

    def is_booted(self):
        # By default we pass
        pass

    def reset_boot(self):
        # By default we pass
        pass

    @contextlib.contextmanager
    def file_system(self, partition, directory):
        """ Allows the caller to interact directly with a directory on
        the target. This method yields a directory where the caller can
        interact from. Upon the exit of this context, the changes will be
        applied to the target.

        The partition parameter refers to partition number the directory
        would reside in as created by linaro-media-create. ie - the boot
        partition would be 1. In the case of something like the master
        image, the target implementation must map this number to the actual
        partition its using.

        NOTE: due to difference in target implementations, the caller should
        try and interact with the smallest directory locations possible.
        """
        raise NotImplementedError('file_system')

    def extract_tarball(self, tarball_url, partition, directory='/'):
        """ This is similar to the file_system API but is optimized for the
        scenario when you just need explode a potentially large tarball on
        the target device. The file_system API isn't really suitable for this
        when thinking about an implementation like master.py
        """
        raise NotImplementedError('extract_tarball')

    def get_test_data_attachments(self):
        return []

    def get_device_version(self):
        """ Returns the device version associated with the device, i.e. version
        of emulation software, or version of master image. Must be overriden in
        subclasses.
        """
        return 'unknown'

    def _copy_first_find_from_list(self, subdir, odir, file_list, rename=None):
        f_path = None
        for fname in file_list:
            f_path = self._find_and_copy(subdir, odir, fname, rename)
            if f_path:
                break

        return f_path

    def _find_and_copy(self, rootdir, odir, pattern, name=None):
        dest = None
        for root, dirs, files in os.walk(rootdir, topdown=False):
            for file_name in files:
                if re.match(pattern, file_name):
                    src = os.path.join(root, file_name)
                    logging.info('Loading file: %s', src)
                    if name is not None:
                        dest = os.path.join(odir, name)
                        new_src = os.path.join(root, name)
                    else:
                        dest = os.path.join(odir, file_name)
                    if src != dest:
                        if name is not None:
                            shutil.copyfile(src, dest)
                            shutil.move(src, new_src)
                        else:
                            shutil.copyfile(src, dest)
                        return dest
                    else:
                        if name is not None:
                            shutil.move(src, new_src)
                        return dest
        return dest

    def _wait_for_prompt(self, connection, prompt_pattern, timeout):
        wait_for_prompt(connection, prompt_pattern, timeout)

    def _is_job_defined_boot_cmds(self, boot_cmds):
        if isinstance(self.config.boot_cmds, basestring):
            return False
        else:
            return True

    def _image_has_selinux_support(self, connection, timeout):
        unrecognised = ''
        connection.sendline("LANG=C tar --selinux 2>&1 | grep unrecognized| wc -l")
        connection.expect(pexpect.TIMEOUT, timeout=timeout)
        output = connection.before
        if len(output.split('\n')) >= 2:
            unrecognised = output.split('\n')[1].strip()
        if unrecognised == '1':
            logging.info("SELinux support disabled in test image. The current image has no selinux support in 'tar'.")
            return False
        elif unrecognised == '0' or unrecognised == '':
            logging.debug("Retaining SELinux support in the current image.")
            return True
        else:
            logging.error("Unable to determine SELinux support.")
            return False

    def _auto_login(self, connection, is_master=False):
        if is_master:
            if self.config.master_login_prompt is not None:
                self._wait_for_prompt(connection,
                                      self.config.master_login_prompt, timeout=300)
                connection.sendline(self.config.master_username)
            if self.config.master_password_prompt is not None:
                self._wait_for_prompt(connection,
                                      self.config.master_password_prompt, timeout=300)
                connection.sendline(self.config.master_password)
            if self.config.master_login_commands is not None:
                for command in self.config.master_login_commands:
                    connection.sendline(command)
        else:
            if self.config.login_prompt is not None:
                self._wait_for_prompt(connection,
                                      self.config.login_prompt, timeout=300)
                connection.sendline(self.config.username)
            if self.config.password_prompt is not None:
                self._wait_for_prompt(connection,
                                      self.config.password_prompt, timeout=300)
                connection.sendline(self.config.password)
            if self.config.login_commands is not None:
                for command in self.config.login_commands:
                    connection.sendline(command)

    def _is_uboot_ramdisk(self, ramdisk):
        try:
            out = subprocess.check_output('mkimage -l %s' % ramdisk, shell=True).splitlines()
        except subprocess.CalledProcessError:
            return False

        for line in out:
            if not line.startswith('Image Type:'):
                continue
            key, val = line.split(':')
            if val.find('RAMDisk') > 0:
                return True

        return False

    def _get_rel_path(self, path, base):
        return os.path.relpath(path, base)

    def _setup_nfs(self, nfsrootfs, tmpdir):
        lava_nfsrootfs = utils.mkdtemp(basedir=tmpdir)
        utils.extract_rootfs(nfsrootfs, lava_nfsrootfs)
        return lava_nfsrootfs

    def _setup_tmpdir(self):
        if not self.config.use_lava_tmpdir:
            if self.config.alternative_dir is None:
                logging.error("You have specified not to use the LAVA temporary \
                              directory. However, you have not defined an \
                              alternate temporary directory. Falling back to \
                              use the LAVA temporary directory.")
                return self.context.config.lava_image_tmpdir, self.scratch_dir
            else:
                if self.config.alternative_create_tmpdir:
                    return self.config.alternative_dir, utils.mkdtemp(self.config.alternative_dir)
                else:
                    return self.config.alternative_dir, self.config.alternative_dir
        else:
            return self.context.config.lava_image_tmpdir, self.scratch_dir

    def _load_boot_cmds(self, default=None, boot_cmds_dynamic=None,
                        boot_tags=None):
        # Set flags
        boot_cmds_job_file = False
        boot_cmds_boot_options = False

        # Set the default boot commands
        if default is None:
            boot_cmds = self.deployment_data['boot_cmds']
        else:
            boot_cmds = default

        # Check for job defined boot commands
        if boot_cmds != 'boot_cmds_master':
            boot_cmds_job_file = self._is_job_defined_boot_cmds(self.config.boot_cmds)

        # Check if a user has entered boot_options
        options, user_option = boot_options.as_dict(self, defaults={'boot_cmds': boot_cmds})
        if 'boot_cmds' in options and user_option:
            boot_cmds_boot_options = True

        # Interactive boot_cmds from the job file are a list.
        # We check for them first, if they are present, we use
        # them and ignore the other cases.
        if boot_cmds_job_file:
            logging.info('Overriding boot_cmds from job file')
            boot_cmds = self.config.boot_cmds
        # If there were no interactive boot_cmds, next we check
        # for boot_option overrides. If one exists, we use them
        # and ignore all other cases.
        elif boot_cmds_boot_options:
            logging.info('Overriding boot_cmds from boot_options')
            boot_cmds = options['boot_cmds'].value
            logging.info('boot_option=%s', boot_cmds)
            boot_cmds = self.config.cp.get('__main__', boot_cmds)
            boot_cmds = utils.string_to_list(boot_cmds.encode('ascii'))
        # No interactive or boot_option overrides are present,
        # we prefer to get the boot_cmds for the image if they are
        # present.
        elif boot_cmds_dynamic is not None:
            logging.info('Loading boot_cmds from image')
            boot_cmds = boot_cmds_dynamic
        # This is the catch all case. Where we get the default boot_cmds
        # from the deployment data.
        else:
            logging.info('Loading boot_cmds from device configuration')
            boot_cmds = self.config.cp.get('__main__', boot_cmds)
            boot_cmds = utils.string_to_list(boot_cmds.encode('ascii'))

        if boot_tags is not None:
            boot_cmds = self._tag_boot_cmds(boot_cmds, boot_tags)

        return boot_cmds

    def _soft_reboot(self, connection):
        logging.info("Perform soft reboot the system")
        # Try to C-c the running process, if any.
        connection.sendcontrol('c')
        connection.sendline(self.config.soft_boot_cmd)
        # Looking for reboot messages or if they are missing, the U-Boot
        # message will also indicate the reboot is done.
        match_id = connection.expect(
            [pexpect.TIMEOUT, 'Restarting system.',
             'The system is going down for reboot NOW',
             'Will now restart', 'U-Boot'], timeout=120)
        if match_id == 0:
            raise OperationFailed("Soft reboot failed")

    def _hard_reboot(self, connection):
        logging.info("Perform hard reset on the system")
        if self.config.hard_reset_command != "":
            self.context.run_command(self.config.hard_reset_command)
        else:
            connection.send("~$")
            connection.sendline("hardreset")
            connection.empty_buffer()

    def _enter_bootloader(self, connection):
        if connection.expect(self.config.interrupt_boot_prompt) != 0:
            raise Exception("Failed to enter bootloader")
        if self.config.interrupt_boot_control_character:
            connection.sendcontrol(self.config.interrupt_boot_control_character)
        else:
            connection.send(self.config.interrupt_boot_command)

    def _boot_cmds_preprocessing(self, boot_cmds):
        """ preprocess boot_cmds to prevent the boot procedure from some errors
        (1)Delete the redundant element "" at the end of boot_cmds
        (2)(we can add more actions for preprocessing here).
        """
        # Delete the redundant element "" at the end of boot_cmds
        while True:
            if boot_cmds and boot_cmds[-1] == "":
                del boot_cmds[-1]
            else:
                break
        # we can add more actions here
        logging.debug('boot_cmds(after preprocessing): %s', boot_cmds)
        return boot_cmds

    def _tag_boot_cmds(self, boot_cmds, boot_tags):
        for i, cmd in enumerate(boot_cmds):
            for key, value in boot_tags.iteritems():
                if key in cmd:
                    boot_cmds[i] = boot_cmds[i].replace(key, value)

        return boot_cmds

    def _customize_bootloader(self, connection, boot_cmds):
        start = time.time()
        delay = self.config.bootloader_serial_delay_ms
        _boot_cmds = self._boot_cmds_preprocessing(boot_cmds)
        for line in _boot_cmds:
            parts = re.match('^(?P<action>sendline|sendcontrol|expect)\s*(?P<command>.*)',
                             line)
            if parts:
                try:
                    action = parts.group('action')
                    command = parts.group('command')
                except AttributeError as e:
                    raise Exception("Badly formatted command in \
                                      boot_cmds %s" % e)
                if action == "sendline":
                    connection.send(command, delay,
                                    send_char=self.config.send_char)
                    connection.sendline('', delay,
                                        send_char=self.config.send_char)
                elif action == "sendcontrol":
                    connection.sendcontrol(command)
                elif action == "expect":
                    command = re.escape(command)
                    connection.expect(command, timeout=300)
            else:
                self._wait_for_prompt(connection,
                                      self.config.bootloader_prompt,
                                      timeout=300)
                connection.sendline(line, delay,
                                    send_char=self.config.send_char)

        # Record boot time metadata
        boottime = "{0:.2f}".format(time.time() - start)
        boottime_meta = {'bootloader-load-time': boottime}
        self.context.test_data.add_metadata(boottime_meta)
        logging.debug("Bootloader load time: %s seconds", boottime)

    def _target_extract(self, runner, tar_file, dest, timeout=-1, busybox=False):
        tmpdir = self.context.config.lava_image_tmpdir
        url = self.context.config.lava_image_url
        tar_file = tar_file.replace(tmpdir, '')
        tar_url = '/'.join(u.strip('/') for u in [url, tar_file])
        self._target_extract_url(runner, tar_url, dest, timeout=timeout, busybox=busybox)

    def _target_extract_url(self, runner, tar_url, dest, timeout=-1, busybox=False):
        decompression_cmd = ''
        if tar_url.endswith('.gz') or tar_url.endswith('.tgz'):
            decompression_cmd = '| /bin/gzip -dc'
        elif tar_url.endswith('.bz2'):
            decompression_cmd = '| /bin/bzip2 -dc'
        elif tar_url.endswith('.xz'):
            decompression_cmd = '| /usr/bin/xz -dc'
        elif tar_url.endswith('.tar'):
            decompression_cmd = ''
        else:
            raise RuntimeError('bad file extension: %s' % tar_url)

        if busybox:
            wget_options = ''
        else:
            wget_options = '--no-check-certificate --no-proxy --connect-timeout=30 -S --progress=dot -e dotbytes=2M'

        if self._image_has_selinux_support(runner.get_connection(), 3):
            self.context.selinux = '--selinux'
        else:
            self.context.selinux = ''

        runner.run('wget %s -O - %s %s | /bin/tar %s -C %s -xmf -'
                   % (wget_options, tar_url, decompression_cmd, self.context.selinux, dest),
                   timeout=timeout)

    @contextlib.contextmanager
    def _python_file_system(self, runner, directory, prompt_pattern, mounted=False):
        connection = runner.get_connection()
        error_detected = False
        try:
            if mounted:
                targetdir = os.path.abspath(os.path.join('/mnt/%s' % directory))
            else:
                targetdir = os.path.abspath(os.path.join('/', directory))

            runner.run('mkdir -p %s' % targetdir)

            parent_dir, target_name = os.path.split(targetdir)

            runner.run('nice tar -czf /tmp/fs.tgz -C %s %s' %
                       (parent_dir, target_name))
            runner.run('cd /tmp')  # need to be in same dir as fs.tgz

            try:
                ip = runner.get_target_ip()
            except NetworkError as e:
                error_detected = True
                raise CriticalError("Network error detected..aborting")

            connection.sendline('python -m SimpleHTTPServer 0 2>/dev/null')
            match_id = connection.expect([
                'Serving HTTP on 0.0.0.0 port (\d+) \.\.',
                pexpect.EOF, pexpect.TIMEOUT])
            if match_id != 0:
                msg = "Unable to start HTTP server"
                logging.error(msg)
                raise CriticalError(msg)
            port = connection.match.groups()[match_id]

            url = "http://%s:%s/fs.tgz" % (ip, port)
            tf = download_image(url,
                                self.context, self.scratch_dir, decompress=False)

            tfdir = os.path.join(self.scratch_dir, str(time.time()))
            try:
                utils.ensure_directory(tfdir)
                self.context.run_command('nice tar --selinux -C %s -xzf %s' % (tfdir, tf))
                yield os.path.join(tfdir, target_name)

            finally:
                tf = os.path.join(self.scratch_dir, 'fs.tgz')
                utils.mk_targz(tf, tfdir)
                utils.rmtree(tfdir)

                connection.sendcontrol('c')  # kill SimpleHTTPServer
                self._wait_for_prompt(connection,
                                      prompt_pattern,
                                      timeout=30)

                # get the last 2 parts of tf, ie "scratchdir/tf.tgz"
                tf = '/'.join(tf.split('/')[-2:])
                runner.run('rm -rf %s' % targetdir)
                self._target_extract(runner, tf, parent_dir)

        finally:
            if not error_detected:
                # kill SimpleHTTPServer
                connection.sendcontrol('c')
                self._wait_for_prompt(connection,
                                      prompt_pattern,
                                      timeout=30)
            if mounted:
                runner.run('umount /mnt')

    @contextlib.contextmanager
    def _busybox_file_system(self, runner, directory, mounted=False):
        error_detected = False
        try:
            if mounted:
                targetdir = os.path.abspath(os.path.join('/mnt/%s' % directory))
            else:
                targetdir = os.path.abspath(os.path.join('/', directory))

            runner.run('mkdir -p %s' % targetdir)

            parent_dir, target_name = os.path.split(targetdir)

            runner.run('/bin/tar -cmzf /tmp/fs.tgz -C %s %s'
                       % (parent_dir, target_name))
            runner.run('cd /tmp')  # need to be in same dir as fs.tgz

            try:
                ip = runner.get_target_ip()
            except NetworkError as e:
                error_detected = True
                raise CriticalError("Network error detected..aborting")

            url_base = self._start_busybox_http_server(runner, ip)

            url = url_base + '/fs.tgz'
            logging.info("Fetching url: %s", url)
            tf = download_image(url, self.context, self.scratch_dir,
                                decompress=False)

            tfdir = os.path.join(self.scratch_dir, str(time.time()))

            try:
                utils.ensure_directory(tfdir)
                self.context.run_command('/bin/tar -C %s -xzf %s'
                                         % (tfdir, tf))
                yield os.path.join(tfdir, target_name)
            finally:
                tf = os.path.join(self.scratch_dir, 'fs.tgz')
                utils.mk_targz(tf, tfdir)
                utils.rmtree(tfdir)

                # get the last 2 parts of tf, ie "scratchdir/tf.tgz"
                tf = '/'.join(tf.split('/')[-2:])
                runner.run('rm -rf %s' % targetdir)
                self._target_extract(runner, tf, parent_dir, busybox=True)
        finally:
            if not error_detected:
                self._stop_busybox_http_server(runner)
            if mounted:
                runner.run('umount /mnt')

    def _start_busybox_http_server(self, runner, ip):
        runner.run('busybox httpd -f -p %d &' % self.config.busybox_http_port)
        runner.run('echo $! > /tmp/httpd.pid')
        url_base = "http://%s:%d" % (ip, self.config.busybox_http_port)
        return url_base

    def _stop_busybox_http_server(self, runner):
        runner.run('kill `cat /tmp/httpd.pid`')

    def _customize_prompt_hostname(self, rootdir, profile_path):
        if re.search("%s", profile_path):
            # If profile path is expecting a rootdir in it, perform string
            # substitution.
            profile_path = profile_path % rootdir

        with open(profile_path, 'a') as f:
            f.write('export PS1="%s"\n' % self.tester_ps1)
        with open('%s/etc/hostname' % rootdir, 'w') as f:
            f.write('%s\n' % self.config.hostname)

    @property
    def tester_ps1(self):
        return self._get_from_config_or_deployment_data('tester_ps1')

    @property
    def tester_ps1_pattern(self):
        return self._get_from_config_or_deployment_data('tester_ps1_pattern')

    @property
    def tester_ps1_includes_rc(self):
        # tester_ps1_includes_rc is a string so we can decode it here as
        # yes/no/ not set. If it isn't set, we stick with the device
        # default. We can't do the tri-state logic as a BoolOption because an
        # unset BoolOption returns False, not None, so we can't detect not set.
        value = self._get_from_config_or_deployment_data(
            'tester_ps1_includes_rc')

        if isinstance(value, bool):
            return value

        if value.lower() in ['y', '1', 'yes', 'on', 'true']:
            return True
        elif value.lower() in ['n', '0', 'no', 'off', 'false']:
            return False
        else:
            raise ValueError("Unable to determine boolosity of %r" % value)

    @property
    def tester_rc_cmd(self):
        return self._get_from_config_or_deployment_data('tester_rc_cmd')

    @property
    def lava_test_dir(self):
        lava_test_dir = self._get_from_config_or_deployment_data('lava_test_dir')
        if re.match('.*%s', lava_test_dir):
            lava_test_dir = lava_test_dir % self.config.hostname
        return lava_test_dir

    @property
    def lava_test_results_dir(self):
        lava_test_results_dir = self._get_from_config_or_deployment_data('lava_test_results_dir')
        if re.match('.*%s', lava_test_results_dir):
            lava_test_results_dir = lava_test_results_dir % self.config.hostname
        return lava_test_results_dir

    def _get_from_config_or_deployment_data(self, key):
        value = getattr(self.config, key.lower())
        if value is None:
            keys = [key, key.upper(), key.lower()]
            for test_key in keys:
                value = self.deployment_data.get(test_key)
                if value is not None:
                    return value

            # At this point we didn't find anything.
            raise KeyError("Unable to find value for key %s" % key)
        else:
            return value

    def _customize_linux(self):
        # XXX Re-examine what to do here in light of deployment_data import.
        # perhaps make self.deployment_data = deployment_data({overrides: dict})
        # and remove the write function completely?

        os_release_id = 'linux'
        mnt = self.mount_info['rootfs']
        os_release_file = '%s/etc/os-release' % mnt
        if os.path.exists(os_release_file):
            for line in open(os_release_file):
                if line.startswith('ID='):
                    os_release_id = line[(len('ID=')):]
                    os_release_id = os_release_id.strip('\"\n')
                    break

        profile_path = "%s/etc/profile" % mnt
        if os_release_id == 'debian' or os_release_id == 'ubuntu' or \
                os.path.exists('%s/etc/debian_version' % mnt):
            self.deployment_data = deployment_data.ubuntu
            profile_path = '%s/root/.bashrc' % mnt
        elif os_release_id == 'fedora':
            self.deployment_data = deployment_data.fedora
        else:
            # assume an OE based image. This is actually pretty safe
            # because we are doing pretty standard linux stuff, just
            # just no upstart or dash assumptions
            self.deployment_data = deployment_data.oe

        self._customize_prompt_hostname(mnt, profile_path)

    def _pre_download_src(self, customize_info, image=None):
        # for self.customize_image

        if image is not None:
            for customize_object in customize_info["image"]:
                image_path = ImagePathHandle(image, customize_object["src"], self.config, self.mount_info)
                temp_file = image_path.copy_to(self.context, None)
                customize_object["src"] = temp_file
        else:
            customize_info["image"] = []
            logging.debug("There are not image files which will be pre-download to temp dir!")

        for customize_object in customize_info["remote"]:
            temp_file = download_image(customize_object["src"], self.context)
            customize_object["src"] = temp_file

    def _reorganize_customize_files(self):
        # for self.customize_image
        # translate the raw customize info from
        #    "customize": {
        #    "http://my.server/files/startup.nsh": ["boot:/EFI/BOOT/", "boot:/startup_backup.nsh"],
        #    "http://my.server/files/my-crazy-bash-binary": ["rootfs:/bin/bash"],
        #    "rootfs:/lib/modules/eth.ko": ["rootfs:/lib/modules/firmware/eth.ko", "delete"]
        #    }
        #
        # to a specific object
        #   customize_info = {
        #       "delete":[image_path_1, image_path_2],
        #       "image":[
        #           {"src":"image_path_1", "des":[image_path_1]},
        #           {"src":"image_path_2", "des":[image_path_1, image_path_2]}
        #       ],
        #       "remote":[
        #           {"src":"url_1", "des":[image_path_1, image_path_2]},
        #           {"src":"url_2", "des":[image_path_1]}
        #       ]
        #   }
        #
        # make this info easy to be processed
        #

        customize_info = {
            "delete": [],
            "image": [],
            "remote": []
        }
        image_part = ["boot", "root"]

        for src, des in self.config.customize.items():
            temp_dic = {"src": src, "des": des}
            for des_tmp in temp_dic["des"]:
                if des_tmp[:5] != "boot:" and des_tmp[:7] != "rootfs:" and des_tmp != "delete":
                    logging.error('Customize function only support <boot, rootfs>:<path> as image path, for now!')
                    raise CriticalError("Unrecognized image path %s, Please check your test definition!" % des_tmp)
                    # temp_dic["des"].remove(des_tmp)
            if src[:4] in image_part:
                if "delete" in temp_dic["des"]:
                    customize_info["delete"].append(src)
                    temp_dic["des"].remove("delete")
                customize_info["image"].append(temp_dic)
            else:
                if "delete" in temp_dic["des"]:
                    logging.warning("Do not try to delete the remote file %s", temp_dic["src"])
                    temp_dic["des"].remove("delete")
                customize_info["remote"].append(temp_dic)

        logging.debug("Do customizing image with %s", customize_info)

        return customize_info

    def _customize_image(self, image, boot_mnt, rootfs_mnt):
        self.mount_info = {'boot': boot_mnt, 'rootfs': rootfs_mnt}

        # for _customize_linux integration
        self._customize_linux()

        # for files injection function.
        if self.config.customize is not None and image is not None:
            # format raw config.customize to customize_info object
            customize_info = self._reorganize_customize_files()

            # fetch all the src file into the local temp dir
            self._pre_download_src(customize_info, image)

            # delete file or dir in image
            for delete_item in customize_info["delete"]:
                image_item = ImagePathHandle(image, delete_item, self.config, self.mount_info)
                image_item.remove()

            # inject files/dirs, all the items should be pre-downloaded into temp dir.
            for customize_object in customize_info["image"]:
                for des_image_path in customize_object["des"]:
                    def_item = ImagePathHandle(image, des_image_path, self.config, self.mount_info)
                    def_item.copy_from(customize_object["src"])
            for customize_object in customize_info["remote"]:
                for des_image_path in customize_object["des"]:
                    def_item = ImagePathHandle(image, des_image_path, self.config, self.mount_info)
                    def_item.copy_from(customize_object["src"])
        else:
            logging.debug("Skip customizing temp image %s !", image)
            logging.debug("Customize object is %s !", self.config.customize)

    def customize_image(self, image=None):
        if self.config.boot_part != self.config.root_part:
            with image_partition_mounted(image, self.config.boot_part) as boot_mnt:
                with image_partition_mounted(image, self.config.root_part) as rootfs_mnt:
                    self._customize_image(image, boot_mnt, rootfs_mnt)
        else:
            with image_partition_mounted(image, self.config.boot_part) as boot_mnt:
                self._customize_image(image, boot_mnt, boot_mnt)
