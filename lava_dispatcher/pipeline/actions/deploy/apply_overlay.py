# Copyright (C) 2014 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
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

import os
import tarfile
import subprocess
from lava_dispatcher.pipeline.action import Action, Pipeline, InfrastructureError
from lava_dispatcher.pipeline.actions.deploy.overlay import OverlayAction
from lava_dispatcher.pipeline.utils.constants import (
    RAMDISK_COMPRESSED_FNAME,
    RAMDISK_FNAME,
)
from lava_dispatcher.pipeline.utils.filesystem import mkdtemp
from lava_dispatcher.pipeline.utils.shell import which


class ApplyOverlayImage(Action):
    """
    Applies the overlay to an image using mntdir
    * checks that the filesystem we need is actually mounted.
    """
    def __init__(self):
        super(ApplyOverlayImage, self).__init__()
        self.name = "apply-overlay-image"
        self.summary = "unpack overlay onto image"
        self.description = "unpack overlay onto image mountpoint"

    def run(self, connection, args=None):
        if not self.data['compress-overlay'].get('output'):
            raise RuntimeError("Unable to find the overlay")
        if not os.path.ismount(self.data['loop_mount']['mntdir']):
            raise RuntimeError("Image overlay requested to be applied but %s is not a mountpoint" %
                               self.data['loop_mount']['mntdir'])
        # use tarfile module - no SELinux support here yet
        try:
            tar = tarfile.open(self.data['compress-overlay'].get('output'))
            tar.extractall(self.data['loop_mount']['mntdir'])
            tar.close()
        except tarfile.TarError as exc:
            raise RuntimeError("Unable to unpack overlay: %s" % exc)
        return connection


class PrepareOverlayTftp(Action):
    """
    Extracts the ramdisk or rootfs in preparation for the lava overlay
    """
    def __init__(self):
        super(PrepareOverlayTftp, self).__init__()
        self.name = "prepare-tftp-overlay"
        self.summary = "extract ramdisk or rootfs"
        self.description = "extract ramdisk or rootfs in preparation for lava overlay"

    def populate(self, parameters):
        self.internal_pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        self.internal_pipeline.add_action(OverlayAction())  # idempotent, includes testdef
        self.internal_pipeline.add_action(ExtractRootfs())
        self.internal_pipeline.add_action(ExtractRamdisk())
        self.internal_pipeline.add_action(ExtractModules())
        self.internal_pipeline.add_action(ApplyOverlayTftp())
        self.internal_pipeline.add_action(CompressRamdisk())  # FIXME: needs a rootfs action

    def run(self, connection, args=None):
        connection = self.internal_pipeline.run_actions(connection, args)
        ramdisk = self.data['compress-ramdisk'].get('ramdisk', None)
        if not ramdisk:  # FIXME: needs a conditional to allow for rootfs
            raise RuntimeError("Unable to apply overlay, not output file")
        return connection


class ApplyOverlayTftp(Action):
    """
    Unpacks the overlay on top of the ramdisk or rootfs
    """
    def __init__(self):
        super(ApplyOverlayTftp, self).__init__()
        self.name = "apply-overlay-tftp"
        self.summary = "apply lava overlay test files"
        self.description = "unpack the overlay into the rootfs or ramdisk"

    def run(self, connection, args=None):
        try:
            tar = tarfile.open(self.data['compress-overlay'].get('output'))
            tar.extractall(self.data['extract-overlay-ramdisk']['extracted_ramdisk'])
            tar.close()
        except tarfile.TarError as exc:
            raise RuntimeError("Unable to unpack overlay: %s" % exc)
        return connection


# FIXME: Not implemented yet
class ExtractRootfs(Action):
    """
    Unpacks the rootfs and applies the overlay to it
    """
    def __init__(self):
        super(ExtractRootfs, self).__init__()
        self.name = "extract-rootfs"
        self.description = "unpack rootfs"
        self.summary = "unpack rootfs, ready to apply lava overlay"

    def validate(self):
        super(ExtractRootfs, self).validate()
        if not self.parameters.get('rootfs', None):  # idempotency
            return
        raise NotImplementedError("No rootfs support yet")

    def run(self, connection, args=None):
        if not self.parameters.get('rootfs', None):  # idempotency
            return connection
        return connection


class ExtractModules(Action):
    """
    If modules are specified in the deploy parameters, unpack the modules
    whilst the rootfs or ramdisk are unpacked.
    """
    def __init__(self):
        super(ExtractModules, self).__init__()
        self.name = "extract-modules"
        self.summary = "extract kernel modules"
        self.description = "extract supplied kernel modules"

    def validate(self):
        super(ExtractModules, self).validate()
        if not self.parameters.get('modules', None):  # idempotency
            return

    def run(self, connection, args=None):
        if not self.parameters.get('modules', None):  # idempotency
            return connection
        if not self.parameters.get('ramdisk', None):
            if not self.parameters.get('rootfs', None):
                raise RuntimeError("Unable to identify unpack location")
            else:
                raise NotImplementedError("rootfs extraction needed")  # FIXME
        else:
            root = self.data['extract-overlay-ramdisk']['extracted_ramdisk']

        modules = self.data['download_action']['modules']['file']
        cmd = ('tar --selinux -C %s -xaf %s' % (root, modules)).split(' ')
        if not self._run_command(cmd):
            raise RuntimeError('Unable to extract tarball: %s to %s' % (modules, root))
        try:
            os.unlink(modules)
        except OSError as exc:
            raise RuntimeError("Unable to remove tarball: '%s' - %s" % (modules, exc))
        return connection


class ExtractRamdisk(Action):
    """
    Removes the uboot header, if kernel-type is uboot
    unzips the ramdisk and uncompresses the contents,
    applies the overlay and then leaves the ramdisk open
    for other actions to modify. Needs CompressRamdisk to
    recreate the ramdisk with modifications.
    """
    def __init__(self):
        super(ExtractRamdisk, self).__init__()
        self.name = "extract-overlay-ramdisk"
        self.summary = "extract the ramdisk"
        self.description = "extract ramdisk to a temporary directory"

    def validate(self):
        super(ExtractRamdisk, self).validate()
        if not self.parameters.get('ramdisk', None):  # idempotency
            return

    def run(self, connection, args=None):
        if not self.parameters.get('ramdisk', None):  # idempotency
            return connection
        ramdisk = self.data['download_action']['ramdisk']['file']
        ramdisk_dir = mkdtemp()
        extracted_ramdisk = os.path.join(ramdisk_dir, 'ramdisk')
        os.mkdir(extracted_ramdisk)
        ramdisk_compressed_data = os.path.join(ramdisk_dir, RAMDISK_COMPRESSED_FNAME)
        if self.parameters.get('ramdisk-type', None) == 'u-boot':
            # TODO: 64 bytes is empirical - may need to be configurable in the future
            cmd = ('dd if=%s of=%s ibs=64 skip=1' % (ramdisk, ramdisk_compressed_data)).split(' ')
            try:
                self._run_command(cmd)
            except:
                raise RuntimeError('Unable to remove uboot header: %s' % ramdisk)
        else:
            # give the file a predictable name
            os.rename(ramdisk, ramdisk_compressed_data)
        self._log(os.system("file %s" % ramdisk_compressed_data))
        cmd = ('gzip -d -f %s' % ramdisk_compressed_data).split(' ')
        if self._run_command(cmd) is not '':
            raise RuntimeError('Unable to uncompress: %s' % ramdisk_compressed_data)
        # filename has been changed by gzip
        ramdisk_data = os.path.join(ramdisk_dir, RAMDISK_FNAME)
        pwd = os.getcwd()
        os.chdir(extracted_ramdisk)
        cmd = ('cpio -i -F %s' % ramdisk_data).split(' ')
        if not self._run_command(cmd):
            raise RuntimeError('Unable to uncompress: %s' % ramdisk_data)
        os.chdir(pwd)
        # tell other actions where the unpacked ramdisk can be found
        self.data[self.name]['extracted_ramdisk'] = extracted_ramdisk  # directory
        self.data[self.name]['ramdisk_file'] = ramdisk_data  # filename
        return connection


class CompressRamdisk(Action):
    """
     recreate ramdisk, with overlay in place
    """
    def __init__(self):
        super(CompressRamdisk, self).__init__()
        self.name = "compress-ramdisk"
        self.summary = "compress ramdisk with overlay"
        self.description = "recreate a ramdisk with the overlay applied."

    def validate(self):
        super(CompressRamdisk, self).validate()
        if not self.parameters.get('ramdisk', None):  # idempotency
            return
        try:
            which('mkimage')
        except InfrastructureError:
            raise InfrastructureError("Unable to find mkimage - is u-boot-tools installed?")

    def run(self, connection, args=None):
        if not self.parameters.get('ramdisk', None):  # idempotency
            return connection
        if 'extracted_ramdisk' not in self.data['extract-overlay-ramdisk']:
            raise RuntimeError("Unable to find unpacked ramdisk")
        if 'ramdisk_file' not in self.data['extract-overlay-ramdisk']:
            raise RuntimeError("Unable to find ramdisk directory")
        ramdisk_dir = self.data['extract-overlay-ramdisk']['extracted_ramdisk']
        ramdisk_data = self.data['extract-overlay-ramdisk']['ramdisk_file']
        pwd = os.getcwd()
        os.chdir(ramdisk_dir)
        cmd = "find . | cpio --create --format='newc' > %s" % ramdisk_data
        try:
            # safe to use shell=True here, no external arguments
            log = subprocess.check_output(cmd, shell=True)
        except OSError as exc:
            raise RuntimeError('Unable to create cpio filesystem: %s' % exc)
        self._log("%s\n%s" % (cmd, log))
        os.chdir(os.path.dirname(ramdisk_data))
        if self._run_command(("gzip %s" % ramdisk_data).split(' ')) is not '':
            raise RuntimeError('Unable to compress cpio filesystem')
        os.chdir(pwd)
        final_file = os.path.join(os.path.dirname(ramdisk_data), 'ramdisk.cpio.gz')
        tftp_dir = os.path.dirname(self.data['download_action']['ramdisk']['file'])

        if self.parameters.get('ramdisk-type', None) == 'u-boot':
            ramdisk_uboot = final_file + ".uboot"
            self._log("Adding RAMdisk u-boot header.")
            # FIXME: hidden architecture assumption
            cmd = ("mkimage -A arm -T ramdisk -C none -d %s %s" % (final_file, ramdisk_uboot)).split(' ')
            if not self._run_command(cmd):
                raise RuntimeError("Unable to add uboot header to ramdisk")
            final_file = ramdisk_uboot

        os.rename(final_file, os.path.join(tftp_dir, os.path.basename(final_file)))
        self.data[self.name]['ramdisk'] = final_file
        return connection
