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
import shutil
import subprocess
from lava_dispatcher.pipeline.action import (
    Action,
    Pipeline,
    InfrastructureError,
    JobError
)
from lava_dispatcher.pipeline.actions.deploy.overlay import OverlayAction
from lava_dispatcher.pipeline.utils.constants import (
    LXC_PATH,
    RAMDISK_FNAME,
    UBOOT_DEFAULT_HEADER_LENGTH,
)
from lava_dispatcher.pipeline.utils.installers import (
    add_late_command,
    add_to_kickstart
)
from lava_dispatcher.pipeline.utils.filesystem import (
    mkdtemp,
    prepare_guestfs,
    copy_in_overlay,
    copy_overlay_to_sparse_fs,
)
from lava_dispatcher.pipeline.utils.shell import infrastructure_error
from lava_dispatcher.pipeline.utils.compression import (
    compress_file,
    decompress_file,
    untar_file
)
from lava_dispatcher.pipeline.utils.strings import substitute
from lava_dispatcher.pipeline.utils.network import dispatcher_ip
from lava_dispatcher.pipeline.actions.deploy.prepare import PrepareKernelAction


class ApplyOverlayGuest(Action):

    def __init__(self):
        super(ApplyOverlayGuest, self).__init__()
        self.name = "apply-overlay-guest"
        self.summary = "build a guest filesystem with the overlay"
        self.description = "prepare a qcow2 drive containing the overlay"
        self.guest_filename = 'lava-guest.qcow2'

    def validate(self):
        super(ApplyOverlayGuest, self).validate()
        self.set_namespace_data(action=self.name, label='guest', key='name', value=self.guest_filename)
        lava_test_results_base = self.parameters['deployment_data']['lava_test_results_dir']
        lava_test_results_dir = lava_test_results_base % self.job.job_id
        self.set_namespace_data(action='test', label='results', key='lava_test_results_dir', value=lava_test_results_dir)
        if 'guest' not in self.job.device['actions']['deploy']['methods']['image']['parameters']:
            self.errors = "Device configuration does not specify size of guest filesystem."

    def run(self, connection, max_end_time, args=None):
        overlay_file = self.get_namespace_data(action='compress-overlay', label='output', key='file')
        if not overlay_file:
            raise RuntimeError("Unable to find the overlay")
        self.logger.debug("Overlay: %s", overlay_file)
        guest_dir = self.mkdtemp()
        guest_file = os.path.join(guest_dir, self.guest_filename)
        self.set_namespace_data(action=self.name, label='guest', key='filename', value=guest_file)
        blkid = prepare_guestfs(
            guest_file, overlay_file,
            self.job.device['actions']['deploy']['methods']['image']['parameters']['guest']['size'])
        self.results = {'success': blkid}
        self.set_namespace_data(action=self.name, label='guest', key='UUID', value=blkid)
        return connection


class ApplyOverlayImage(Action):

    def __init__(self):
        super(ApplyOverlayImage, self).__init__()
        self.name = "apply-overlay-image"
        self.summary = "apply overlay to test image"
        self.description = "apply overlay via guestfs to the test image"

    def run(self, connection, max_end_time, args=None):
        overlay_file = self.get_namespace_data(action='compress-overlay', label='output', key='file')
        if overlay_file:
            self.logger.debug("Overlay: %s", overlay_file)
            decompressed_image = self.get_namespace_data(action='download_action', label='image', key='file')
            self.logger.debug("Image: %s", decompressed_image)
            root_partition = self.parameters['image']['root_partition']
            self.logger.debug("root_partition: %s", root_partition)
            copy_in_overlay(decompressed_image, root_partition, overlay_file)
        else:
            self.logger.debug("No overlay to deploy")
        return connection


class ApplyOverlaySparseRootfs(Action):

    def __init__(self):
        super(ApplyOverlaySparseRootfs, self).__init__()
        self.name = "apply-overlay-sparse-rootfs"
        self.summary = "apply overlay to sparse rootfs image"
        self.description = "apply overlay to sparse rootfs image"

    def validate(self):
        super(ApplyOverlaySparseRootfs, self).validate()
        self.errors = infrastructure_error('/usr/bin/simg2img')
        self.errors = infrastructure_error('/bin/mount')
        self.errors = infrastructure_error('/bin/umount')
        self.errors = infrastructure_error('/usr/bin/img2simg')

    def run(self, connection, max_end_time, args=None):
        overlay_file = self.get_namespace_data(action='compress-overlay',
                                               label='output', key='file')
        if overlay_file:
            self.logger.debug("Overlay: %s", overlay_file)
            decompressed_image = self.get_namespace_data(
                action='download_action', label='rootfs', key='file')
            self.logger.debug("Image: %s", decompressed_image)
            copy_overlay_to_sparse_fs(decompressed_image, overlay_file)
        else:
            self.logger.debug("No overlay to deploy")
        return connection


class PrepareOverlayTftp(Action):
    """
    Extracts the ramdisk or nfsrootfs in preparation for the lava overlay
    """
    def __init__(self):
        super(PrepareOverlayTftp, self).__init__()
        self.name = "prepare-tftp-overlay"
        self.summary = "extract ramdisk or nfsrootfs"
        self.description = "extract ramdisk or nfsrootfs in preparation for lava overlay"

    def populate(self, parameters):
        self.internal_pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        self.internal_pipeline.add_action(ExtractNfsRootfs())  # idempotent, checks for nfsrootfs parameter
        self.internal_pipeline.add_action(OverlayAction())  # idempotent, includes testdef
        self.internal_pipeline.add_action(ExtractRamdisk())  # idempotent, checks for a ramdisk parameter
        self.internal_pipeline.add_action(ExtractModules())  # idempotent, checks for a modules parameter
        self.internal_pipeline.add_action(ApplyOverlayTftp())
        if 'kernel' in parameters and 'type' in parameters['kernel']:
            self.internal_pipeline.add_action(PrepareKernelAction())
        self.internal_pipeline.add_action(ConfigurePreseedFile())  # idempotent, checks for a preseed parameter
        self.internal_pipeline.add_action(CompressRamdisk())  # idempotent, checks for a ramdisk parameter

    def run(self, connection, max_end_time, args=None):
        connection = super(PrepareOverlayTftp, self).run(connection, max_end_time, args)
        ramdisk = self.get_namespace_data(
            action='download_action',
            label='file',
            key='ramdisk'
        )
        if ramdisk:  # nothing else to do
            return connection
        return connection


class ApplyOverlayTftp(Action):
    """
    Unpacks the overlay on top of the ramdisk or nfsrootfs
    Implicit default order: overlay goes into the NFS by preference
    only into the ramdisk if NFS not specified
    Other actions applying overlays for other deployments need their
    own logic.
    """
    def __init__(self):
        super(ApplyOverlayTftp, self).__init__()
        self.name = "apply-overlay-tftp"
        self.summary = "apply lava overlay test files"
        self.description = "unpack the overlay into the nfsrootfs or ramdisk"

    def validate(self):
        super(ApplyOverlayTftp, self).validate()
        persist = self.parameters.get('persistent_nfs', None)
        if persist:
            if not isinstance(persist, dict):
                self.errors = "Invalid persistent_nfs parameter."
            if 'address' not in persist:
                self.errors = "Missing address for persistent NFS"

    def run(self, connection, max_end_time, args=None):  # pylint: disable=too-many-branches
        connection = super(ApplyOverlayTftp, self).run(connection, max_end_time, args)
        directory = None
        nfs_address = None
        overlay_file = None
        if self.parameters.get('nfsrootfs', None) is not None:
            if not self.parameters['nfsrootfs'].get('install_overlay', True):
                self.logger.info("Skipping applying overlay to NFS")
                return connection
            overlay_file = self.get_namespace_data(action='compress-overlay', label='output', key='file')
            directory = self.get_namespace_data(action='extract-rootfs', label='file', key='nfsroot')
            self.logger.info("Applying overlay to NFS")
        elif self.parameters.get('persistent_nfs', None) is not None:
            if not self.parameters['persistent_nfs'].get('install_overlay', True):
                self.logger.info("Skipping applying overlay to persistent NFS")
                return connection
            overlay_file = self.get_namespace_data(action='compress-overlay', label='output', key='file')
            nfs_address = self.parameters['persistent_nfs'].get('address')
            self.logger.info("Applying overlay to persistent NFS address %s", nfs_address)
            # need to mount the persistent NFS here.
            # We can't use self.mkdtemp() here because this directory should
            # not be removed if umount fails.
            directory = mkdtemp(autoremove=False)
            try:
                subprocess.check_output(['mount', '-t', 'nfs', nfs_address, directory])
            except subprocess.CalledProcessError as exc:
                raise JobError(exc)
        elif self.parameters.get('ramdisk', None) is not None:
            if not self.parameters['ramdisk'].get('install_overlay', True):
                self.logger.info("Skipping applying overlay to ramdisk")
                return connection
            overlay_file = self.get_namespace_data(action='compress-overlay', label='output', key='file')
            directory = self.get_namespace_data(action='extract-overlay-ramdisk', label='extracted_ramdisk', key='directory')
            if overlay_file:
                self.logger.info("Applying overlay %s to ramdisk", overlay_file)
        elif self.parameters.get('rootfs', None) is not None:
            overlay_file = self.get_namespace_data(action='compress-overlay', label='output', key='file')
            directory = self.get_namespace_data(action='apply-overlay', label='file', key='root')
        else:
            self.logger.debug("No overlay directory")
            self.logger.debug(self.parameters)
        if self.parameters.get('os', None) == "centos_installer":
            # centos installer ramdisk doesnt like having anything other
            # than the kickstart config being inserted. Instead, make the
            # overlay accessible through tftp. Yuck.
            tftp_dir = os.path.dirname(self.get_namespace_data(action='download_action', label='ramdisk', key='file'))
            shutil.copy(overlay_file, tftp_dir)
            suffix = self.get_namespace_data(action='tftp-deploy', label='tftp', key='suffix')
            if not suffix:
                suffix = ''
            self.set_namespace_data(action=self.name, label='file', key='overlay',
                                    value=os.path.join(suffix, "ramdisk", os.path.basename(overlay_file)))
        if overlay_file:
            untar_file(overlay_file, directory)
            if nfs_address:
                subprocess.check_output(['umount', directory])
                os.rmdir(directory)  # fails if the umount fails
        return connection


class ExtractRootfs(Action):  # pylint: disable=too-many-instance-attributes
    """
    Unpacks the rootfs and applies the overlay to it
    """
    def __init__(self):
        super(ExtractRootfs, self).__init__()
        self.name = "extract-rootfs"
        self.description = "unpack rootfs"
        self.summary = "unpack rootfs, ready to apply lava overlay"
        self.param_key = 'rootfs'
        self.file_key = "root"
        self.extra_compression = ['xz']
        self.use_tarfile = True
        self.use_lzma = False

    def run(self, connection, max_end_time, args=None):
        if not self.parameters.get(self.param_key, None):  # idempotency
            return connection
        connection = super(ExtractRootfs, self).run(connection, max_end_time, args)
        root = self.get_namespace_data(action='download_action', label=self.param_key, key='file')
        root_dir = self.mkdtemp()
        untar_file(root, root_dir)
        self.set_namespace_data(action='extract-rootfs', label='file', key=self.file_key, value=root_dir)
        self.logger.debug("Extracted %s to %s", self.file_key, root_dir)
        return connection


class ExtractNfsRootfs(ExtractRootfs):
    """
    Unpacks the nfsrootfs and applies the overlay to it
    """
    def __init__(self):
        super(ExtractNfsRootfs, self).__init__()
        self.name = "extract-nfsrootfs"
        self.description = "unpack nfsrootfs"
        self.summary = "unpack nfsrootfs, ready to apply lava overlay"
        self.param_key = 'nfsrootfs'
        self.file_key = "nfsroot"

    def validate(self):
        super(ExtractNfsRootfs, self).validate()
        if not self.parameters.get(self.param_key, None):  # idempotency
            return
        if not self.get_namespace_data(
                action='download_action', label=self.param_key, key='file'):
            self.errors = "no file specified extract as %s" % self.param_key
        if not os.path.exists('/usr/sbin/exportfs'):
            raise InfrastructureError("NFS job requested but nfs-kernel-server not installed.")
        if 'prefix' in self.parameters[self.param_key]:
            prefix = self.parameters[self.param_key]['prefix']
            if prefix.startswith('/'):
                self.errors = 'prefix must not be an absolute path'
            if not prefix.endswith('/'):
                self.errors = 'prefix must be a directory and end with /'

    def run(self, connection, max_end_time, args=None):
        if not self.parameters.get(self.param_key, None):  # idempotency
            return connection
        connection = super(ExtractNfsRootfs, self).run(connection, max_end_time, args)

        if 'prefix' in self.parameters[self.param_key]:
            prefix = self.parameters[self.param_key]['prefix']
            self.logger.warning("Adding '%s' prefix, any other content will not be visible.",
                                prefix)

            # Grab the path already defined in super().run() and add the prefix
            root_dir = self.get_namespace_data(
                action='extract-rootfs',
                label='file',
                key=self.file_key
            )
            root_dir = os.path.join(root_dir, prefix)
            # sets the directory into which the overlay is unpacked and which
            # is used in the substitutions into the bootloader command string.
            self.set_namespace_data(action='extract-rootfs', label='file', key=self.file_key, value=root_dir)
        return connection


class ExtractModules(Action):
    """
    If modules are specified in the deploy parameters, unpack the modules
    whilst the nfsrootfs or ramdisk are unpacked.
    """
    def __init__(self):
        super(ExtractModules, self).__init__()
        self.name = "extract-modules"
        self.summary = "extract kernel modules"
        self.description = "extract supplied kernel modules"

    def run(self, connection, max_end_time, args=None):
        if not self.parameters.get('modules', None):  # idempotency
            return connection
        connection = super(ExtractModules, self).run(connection, max_end_time, args)
        modules = self.get_namespace_data(action='download_action', label='modules', key='file')
        if not self.parameters.get('ramdisk', None):
            if not self.parameters.get('nfsrootfs', None):
                raise JobError("Unable to identify a location for the unpacked modules")
        # if both NFS and ramdisk are specified, apply modules to both
        # as the kernel may need some modules to raise the network and
        # will need other modules to support operations within the NFS
        if self.parameters.get('nfsrootfs', None):
            if not self.parameters['nfsrootfs'].get('install_modules', True):
                self.logger.info("Skipping applying overlay to NFS")
                return connection
            root = self.get_namespace_data(
                action='extract-rootfs',
                label='file',
                key='nfsroot'
            )
            self.logger.info("extracting modules file %s to %s", modules, root)
            untar_file(modules, root)
        if self.parameters.get('ramdisk', None):
            if not self.parameters['ramdisk'].get('install_modules', True):
                self.logger.info("Not adding modules to the ramdisk.")
                return
            root = self.get_namespace_data(
                action='extract-overlay-ramdisk', label='extracted_ramdisk', key='directory')
            self.logger.info("extracting modules file %s to %s", modules, root)
            untar_file(modules, root)
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
        self.skip = False

    def validate(self):
        super(ExtractRamdisk, self).validate()
        if not self.parameters.get('ramdisk', None):  # idempotency
            return
        if not self.parameters['ramdisk'].get('install_modules', True) and \
                not self.parameters['ramdisk'].get('install_overlay', True):
            self.skip = True
            return

    def run(self, connection, max_end_time, args=None):
        if not self.parameters.get('ramdisk', None):  # idempotency
            return connection
        ramdisk = self.get_namespace_data(action='download_action', label='ramdisk', key='file')
        if self.skip:
            self.logger.info("Not extracting ramdisk.")
            suffix = self.get_namespace_data(action='tftp-deploy', label='tftp', key='suffix')
            filename = os.path.join(suffix, "ramdisk", os.path.basename(ramdisk))
            # declare the original ramdisk as the name to be used later.
            self.set_namespace_data(action='compress-ramdisk', label='file', key='ramdisk', value=filename)
            return
        connection = super(ExtractRamdisk, self).run(connection, max_end_time, args)
        ramdisk_dir = self.mkdtemp()
        extracted_ramdisk = os.path.join(ramdisk_dir, 'ramdisk')
        os.mkdir(extracted_ramdisk, 0o755)
        compression = self.parameters['ramdisk'].get('compression', None)
        suffix = ""
        if compression:
            suffix = ".%s" % compression
        ramdisk_compressed_data = os.path.join(ramdisk_dir, RAMDISK_FNAME + suffix)
        if self.parameters['ramdisk'].get('header', None) == 'u-boot':
            cmd = ('dd if=%s of=%s ibs=%s skip=1' % (
                ramdisk, ramdisk_compressed_data, UBOOT_DEFAULT_HEADER_LENGTH)).split(' ')
            try:
                self.run_command(cmd)
            except:
                raise RuntimeError('Unable to remove uboot header: %s' % ramdisk)
        else:
            # give the file a predictable name
            shutil.move(ramdisk, ramdisk_compressed_data)
        ramdisk_data = decompress_file(ramdisk_compressed_data, compression)
        pwd = os.getcwd()
        os.chdir(extracted_ramdisk)
        cmd = ('cpio -iud -F %s' % ramdisk_data).split(' ')
        if not self.run_command(cmd):
            raise JobError('Unable to extract cpio arcive: %s - missing header definition (i.e. u-boot)?' % ramdisk_data)
        os.chdir(pwd)
        # tell other actions where the unpacked ramdisk can be found
        self.set_namespace_data(action=self.name, label='extracted_ramdisk', key='directory', value=extracted_ramdisk)
        self.set_namespace_data(action=self.name, label='ramdisk_file', key='file', value=ramdisk_data)
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
        self.mkimage_arch = None
        self.add_header = None
        self.skip = False

    def validate(self):
        super(CompressRamdisk, self).validate()
        if not self.parameters.get('ramdisk', None):  # idempotency
            return
        if not self.parameters['ramdisk'].get('install_modules', True) and \
                not self.parameters['ramdisk'].get('install_overlay', True):
            self.skip = True
            return
        if 'parameters' in self.job.device['actions']['deploy']:
            self.add_header = self.job.device['actions']['deploy']['parameters'].get('add_header', None)
            if self.add_header is not None:
                if self.add_header == 'u-boot':
                    self.errors = infrastructure_error('mkimage')
                    if 'mkimage_arch' not in self.job.device['actions']['deploy']['parameters']:
                        self.errors = "Missing architecture for uboot mkimage support (mkimage_arch in deploy parameters)"
                        return
                    self.mkimage_arch = self.job.device['actions']['deploy']['parameters']['mkimage_arch']
                else:
                    self.errors = "ramdisk: add_header: unknown header type"

    def run(self, connection, max_end_time, args=None):  # pylint: disable=too-many-locals
        if not self.parameters.get('ramdisk', None):  # idempotency
            return connection
        if self.skip:
            return connection
        connection = super(CompressRamdisk, self).run(connection, max_end_time, args)
        ramdisk_dir = self.get_namespace_data(
            action='extract-overlay-ramdisk', label='extracted_ramdisk', key='directory')
        ramdisk_data = self.get_namespace_data(
            action='extract-overlay-ramdisk', label='ramdisk_file', key='file')
        if not ramdisk_dir:
            raise RuntimeError("Unable to find unpacked ramdisk")
        if not ramdisk_data:
            raise RuntimeError("Unable to find ramdisk directory")
        if self.parameters.get('preseed', None):
            if self.parameters["deployment_data"].get("preseed_to_ramdisk", None):
                # download action must have completed to get this far
                # some installers (centos) cannot fetch the preseed file via tftp.
                # Instead, put the preseed file into the ramdisk using a given name
                # from deployment_data which we can use in the boot commands.
                filename = self.parameters["deployment_data"]["preseed_to_ramdisk"]
                self.logger.info("Copying preseed file into ramdisk: %s", filename)
                shutil.copy(self.get_namespace_data(
                    action='download_action', label='preseed',
                    key='file'), os.path.join(ramdisk_dir, filename))
                self.set_namespace_data(action=self.name, label='file', key='preseed_local', value=filename)
        pwd = os.getcwd()
        os.chdir(ramdisk_dir)
        self.logger.info("Building ramdisk %s containing %s",
                         ramdisk_data, ramdisk_dir)
        cmd = "find . | cpio --create --format='newc' > %s" % ramdisk_data
        try:
            # safe to use shell=True here, no external arguments
            log = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT)
        except OSError as exc:
            raise RuntimeError('Unable to create cpio filesystem: %s' % exc)
        # lazy-logging would mean that the quoting of cmd causes invalid YAML
        self.logger.debug("%s\n%s" % (cmd, log))  # pylint: disable=logging-not-lazy

        # we need to compress the ramdisk with the same method is was submitted with
        compression = self.parameters['ramdisk'].get('compression', None)
        final_file = compress_file(ramdisk_data, compression)
        os.chdir(pwd)
        tftp_dir = os.path.dirname(self.get_namespace_data(
            action='download_action', label='ramdisk', key='file'))

        if self.add_header == 'u-boot':
            ramdisk_uboot = final_file + ".uboot"
            self.logger.debug("Adding RAMdisk u-boot header.")
            cmd = ("mkimage -A %s -T ramdisk -C none -d %s %s" % (self.mkimage_arch, final_file, ramdisk_uboot)).split(' ')
            if not self.run_command(cmd):
                raise RuntimeError("Unable to add uboot header to ramdisk")
            final_file = ramdisk_uboot

        shutil.move(final_file, os.path.join(tftp_dir, os.path.basename(final_file)))
        self.logger.debug("rename %s to %s",
                          final_file, os.path.join(tftp_dir, os.path.basename(final_file)))
        if self.parameters['to'] == 'tftp':
            suffix = self.get_namespace_data(action='tftp-deploy', label='tftp', key='suffix')
            if not suffix:
                suffix = ''
            self.set_namespace_data(
                action=self.name,
                label='file', key='ramdisk', value=os.path.join(suffix, "ramdisk", os.path.basename(final_file)))
        else:
            self.set_namespace_data(
                action=self.name,
                label='file', key='ramdisk', value=final_file)
        return connection


class ApplyLxcOverlay(Action):

    def __init__(self):
        super(ApplyLxcOverlay, self).__init__()
        self.name = "apply-lxc-overlay"
        self.summary = "apply overlay on the container"
        self.description = "apply the overlay to the container by copying"
        self.lava_test_dir = os.path.realpath(
            '%s/../../../pipeline/lava_test_shell' % os.path.dirname(__file__))
        self.scripts_to_copy = ['lava-test-runner']

    def validate(self):
        super(ApplyLxcOverlay, self).validate()
        self.errors = infrastructure_error('tar')

    def run(self, connection, max_end_time, args=None):
        connection = super(ApplyLxcOverlay, self).run(connection, max_end_time, args)
        overlay_file = self.get_namespace_data(action='compress-overlay', label='output', key='file')
        if overlay_file is None:
            self.logger.debug("skipped %s", self.name)
            return connection
        lxc_name = self.get_namespace_data(
            action='lxc-create-action',
            label='lxc', key='name')
        lxc_path = os.path.join(LXC_PATH, lxc_name, 'rootfs')
        if not os.path.exists(lxc_path):
            raise JobError("Lxc container rootfs not found")
        tar_cmd = ['tar', '--warning', 'no-timestamp', '-C', lxc_path, '-xaf',
                   overlay_file]
        command_output = self.run_command(tar_cmd)
        if command_output and command_output is not '':
            raise JobError("Unable to untar overlay: %s" %
                           command_output)  # FIXME: JobError needs a unit test

        # FIXME: Avoid copying this special 'lava-test-runner' which does not
        #        have 'sync' in cleanup. This should be handled during the
        #        creation of the overlay instead. Make a special case to copy
        #        lxc specific scripts, with distro specific versions.
        fname = os.path.join(self.lava_test_dir, 'lava-test-runner')
        output_file = '%s/bin/%s' % (lxc_path, os.path.basename(fname))
        self.logger.debug("Copying %s", output_file)
        try:
            shutil.copy(fname, output_file)
        except IOError:
            raise JobError("Unable to copy: %s" % output_file)

        return connection


class ConfigurePreseedFile(Action):
    def __init__(self):
        super(ConfigurePreseedFile, self).__init__()
        self.name = "configure-preseed-file"
        self.summary = "add commands to installer config"
        self.description = "add commands to automated installers, to copy the lava test overlay to the installed system"

    def run(self, connection, max_end_time, args=None):
        if 'deployment_data' not in self.parameters:
            return connection
        if self.parameters["deployment_data"].get('installer_extra_cmd', None):
            if self.parameters.get('os', None) == "debian_installer":
                add_late_command(self.get_namespace_data(action='download_action', label='preseed', key='file'),
                                 self.parameters["deployment_data"]["installer_extra_cmd"])
            if self.parameters.get('os', None) == "centos_installer":
                ip_addr = dispatcher_ip(self.job.parameters['dispatcher'])
                overlay = self.get_namespace_data(
                    action='download_action', label='file', key='overlay')
                substitutions = {
                    '{OVERLAY_URL}': 'tftp://' + ip_addr + '/' + overlay
                }
                post_command = substitute([self.parameters["deployment_data"]["installer_extra_cmd"]], substitutions)
                add_to_kickstart(self.get_namespace_data(action='download_action', label='preseed', key='file'), post_command[0])
        return connection
