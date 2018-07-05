# Copyright (C) 2014 Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
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
import os
import shutil
import tarfile
import tempfile
import guestfs
import subprocess
import glob
import logging
import magic
import errno
from configobj import ConfigObj

from lava_common.exceptions import InfrastructureError, JobError, LAVABug
from lava_common.constants import (
    LXC_PATH,
    LAVA_LXC_HOME,
)
from lava_dispatcher.utils.compression import decompress_file
from lava_dispatcher.utils.decorator import replace_exception


def rmtree(directory):
    """
    Wrapper around shutil.rmtree to remove a directory tree while ignoring most
    errors.
    If called on a symbolic link, this function will raise a LAVABug.
    """
    # TODO: consider how to handle problems if the directory has already been removed -
    # coding bugs may trigger this Runtime exception - implement before moving to production.
    try:
        shutil.rmtree(directory)
    except OSError as exc:
        raise LAVABug("Error when trying to remove '%s': %s"
                      % (directory, exc))


def mkdtemp(autoremove=True, basedir='/tmp'):
    """
    returns a temporary directory that's deleted when the process exits

    """
    tmpdir = tempfile.mkdtemp(dir=basedir)
    os.chmod(tmpdir, 0o755)
    if autoremove:
        atexit.register(rmtree, tmpdir)
    return tmpdir


def check_ssh_identity_file(params):  # pylint: disable=too-many-return-statements
    """
    Return a tuple based on if an identity file can be determine in the params.
    If the first value returned is not None, an error occurred.
    If the first value is None, the second value contains the path to the identity_file
    """
    if not params or not isinstance(params, dict):
        return "Invalid parameters", None
    if 'ssh' not in params:
        return "Empty ssh parameter list in device configuration %s" % params, None
    if os.path.isabs(params['ssh']['identity_file']):
        identity_file = params['ssh']['identity_file']
    else:
        identity_file = os.path.realpath(
            os.path.join(
                __file__,
                '../' * 2,  # up two directories from this file - not a constant, a result of the layout.
                params['ssh']['identity_file']))
    if not os.path.exists(identity_file):
        return "Cannot find SSH private key %s" % identity_file, None
    if not os.path.exists("%s.pub" % identity_file):
        return "Cannot find SSH public key %s.pub" % identity_file, None
    return None, identity_file


def tftpd_dir():
    """
    read in 'TFTP_DIRECTORY' from /etc/default/tftpd-hpa
    Any file to be offered using tftp must use this directory or a
    subdirectory of it. Default installation value: /srv/tftp/
    :return: real path to the TFTP directory or raises InfrastructureError
    """
    var_name = 'TFTP_DIRECTORY'
    if os.path.exists('/etc/default/tftpd-hpa'):
        config = ConfigObj('/etc/default/tftpd-hpa')
        value = config.get(var_name)
        return os.path.realpath(value)
    raise InfrastructureError("Unable to identify tftpd directory")


def write_bootscript(commands, filename):
    with open(filename, 'w') as bootscript:
        bootscript.write("#!ipxe\n\n")
        for line in commands:
            bootscript.write(line + "\n")
        bootscript.close()


def _launch_guestfs(guest):
    # Launch guestfs and raise an InfrastructureError if needed
    try:
        guest.launch()
    except RuntimeError as exc:
        logger = logging.getLogger('dispatcher')
        logger.exception(str(exc))
        raise InfrastructureError("Unable to start libguestfs")


@replace_exception(RuntimeError, JobError)
def prepare_guestfs(output, overlay, size):
    """
    Applies the overlay, offset by one directory.
    This allows the booted device to mount at the
    original lava directory and retain the same path
    as if the overlay was unpacked directly into the
    image.
    :param output: filename of the temporary device
    :param overlay: tarball of the lava test shell overlay.
    :param size: size of the filesystem in Mb
    :return blkid of the guest device
    """
    guest = guestfs.GuestFS(python_return_dict=True)
    guest.disk_create(output, "qcow2", size * 1024 * 1024)
    guest.add_drive_opts(output, format="qcow2", readonly=False)
    _launch_guestfs(guest)
    devices = guest.list_devices()
    if len(devices) != 1:
        raise InfrastructureError("Unable to prepare guestfs")
    guest_device = devices[0]
    guest.mke2fs(guest_device, label='LAVA')
    # extract to a temp location
    tar_output = mkdtemp()
    # Now mount the filesystem so that we can add files.
    guest.mount(guest_device, "/")
    tarball = tarfile.open(overlay)
    tarball.extractall(tar_output)
    guest_dir = mkdtemp()
    guest_tar = os.path.join(guest_dir, 'guest.tar')
    root_tar = tarfile.open(guest_tar, 'w')
    for topdir in os.listdir(tar_output):
        for dirname in os.listdir(os.path.join(tar_output, topdir)):
            root_tar.add(os.path.join(tar_output, topdir, dirname), arcname=dirname)
    root_tar.close()
    guest.tar_in(guest_tar, '/')
    os.unlink(guest_tar)
    guest.umount(guest_device)
    return guest.blkid(guest_device)['UUID']


@replace_exception(RuntimeError, JobError)
def prepare_install_base(output, size):
    """
    Create an empty image of the specified size (in bytes),
    ready for an installer to partition, create filesystem(s)
    and install files.
    """
    guest = guestfs.GuestFS(python_return_dict=True)
    guest.disk_create(output, "raw", size)
    guest.add_drive_opts(output, format="raw", readonly=False)
    _launch_guestfs(guest)
    devices = guest.list_devices()
    if len(devices) != 1:
        raise InfrastructureError("Unable to prepare guestfs")
    guest.shutdown()


@replace_exception(RuntimeError, JobError)
def copy_out_files(image, filenames, destination):
    """
    Copies a list of files out of the image to the specified
    destination which must exist. Launching the guestfs is
    expensive, so copy out all files in one operation. The
    filenames list must contain unique filenames even if the
    source files exist in separate directories.
    """
    if not isinstance(filenames, list):
        raise LAVABug('filenames must be a list')
    guest = guestfs.GuestFS(python_return_dict=True)
    guest.add_drive_ro(image)
    _launch_guestfs(guest)
    devices = guest.list_devices()
    if len(devices) != 1:
        raise InfrastructureError("Unable to prepare guestfs")
    guest.mount_ro(devices[0], '/')
    for filename in filenames:
        file_buf = guest.read_file(filename)
        with open(os.path.join(destination, os.path.basename(filename)), 'wb') as out:
            out.write(file_buf)
    guest.shutdown()


@replace_exception(RuntimeError, JobError)
def copy_in_overlay(image, root_partition, overlay):
    """
    Mounts test image partition as specified by the test
    writer and extracts overlay at the root, if root_partition
    is None the image is handled as a filesystem instead of
    partitioned image.
    """
    guest = guestfs.GuestFS(python_return_dict=True)
    guest.add_drive(image)
    _launch_guestfs(guest)

    if root_partition:
        partitions = guest.list_partitions()
        if not partitions:
            raise InfrastructureError("Unable to prepare guestfs")
        guest_partition = partitions[root_partition]
        guest.mount(guest_partition, '/')
    else:
        devices = guest.list_devices()
        if not devices:
            raise InfrastructureError("Unable to prepare guestfs")
        guest.mount(devices[0], '/')

    # FIXME: max message length issues when using tar_in
    # on tar.gz.  Works fine with tar so decompressing
    # overlay first.
    if os.path.exists(overlay[:-3]):
        os.unlink(overlay[:-3])
    decompressed_overlay = decompress_file(overlay, 'gz')
    guest.tar_in(decompressed_overlay, '/')

    if root_partition:
        guest.umount(guest_partition)
    else:
        guest.umount(devices[0])


def lxc_path(dispatcher_config):
    """
    Returns LXC_PATH which is a constant, unless a dispatcher specific path is
    configured via lxc_path key in dispatcher_config.
    """
    try:
        return dispatcher_config["lxc_path"]
    except (KeyError, TypeError):
        return LXC_PATH


def lava_lxc_home(lxc_name, dispatcher_config):
    """
    Creates lava_lxc_home if it is unavailable and Returns absolute path of
    LAVA_LXC_HOME as seen from the host machine.

    Takes into account the dispatcher specific path configured via lxc_path
    key in dispatcher_config.
    """
    path = os.path.join(lxc_path(dispatcher_config), lxc_name, 'rootfs',
                        LAVA_LXC_HOME.lstrip('/'))
    # Create lava_lxc_home if it is unavailable
    os.makedirs(path, 0o755, exist_ok=True)
    return path


def copy_to_lxc(lxc_name, src, dispatcher_config):
    """Copies given file in SRC to LAVA_LXC_HOME with the provided LXC_NAME
    and configured lxc_path

    For example,

    SRC such as:
    '/var/lib/lava/dispatcher/tmp/tmpuuI_U0/system.img'

    will get copied to:
    '/var/lib/lxc/lxc-nexus4-test-None/rootfs/lava-lxc/system.img'

    where, '/var/lib/lxc' is the lxc_path and 'lxc-nexus4-test-None' is the
    LXC_NAME

    Returns the destination path within lxc. For example, '/lava-lxc/boot.img'

    Raises JobError if the copy failed.
    """
    filename = os.path.basename(src)
    dst = os.path.join(lava_lxc_home(lxc_name, dispatcher_config), filename)
    logger = logging.getLogger('dispatcher')
    if src == dst:
        logger.debug("Not copying since src: '%s' and dst: '%s' are same",
                     src, dst)
    else:
        logger.debug("Copying %s to %s", filename, lxc_name)
        try:
            shutil.copyfile(src, dst)
        except IOError:
            raise JobError("Unable to copy image: %s" % src)

    return os.path.join(LAVA_LXC_HOME, filename)


def copy_overlay_to_lxc(lxc_name, src, dispatcher_config, namespace):
    """Copies given overlay tar file in SRC to LAVA_LXC_HOME with the provided
    LXC_NAME and configured lxc_path

    For example,

    SRC such as:
    '/var/lib/lava/dispatcher/slave/tmp/523/overlay-1.8.4.tar.gz'

    will get copied to:
    '/var/lib/lxc/db410c-523/rootfs/lava-lxc/overlays/${namespace}/overlay.tar.gz'

    where,
    '/var/lib/lxc' is the lxc_path
    'db410c-523' is the LXC_NAME
    ${namespace} is the given NAMESPACE

    Returns the destination path. For example,
    '/var/lib/lxc/db410c-523/rootfs/lava-lxc/overlays/${namespace}/overlay.tar.gz'

    Raises JobError if the copy failed.
    """
    dst = os.path.join(lava_lxc_home(lxc_name, dispatcher_config), 'overlays',
                       namespace, 'overlay.tar.gz')
    logger = logging.getLogger('dispatcher')
    logger.debug("Copying %s to %s", os.path.basename(src), dst)
    try:
        shutil.copy(src, dst)
    except IOError as exc:
        # ENOENT(2): No such file or directory
        if exc.errno != errno.ENOENT:
            raise JobError("Unable to copy image: %s" % src)
        # try creating parent directories
        os.makedirs(os.path.dirname(dst), 0o755)
        shutil.copy(src, dst)
    return dst


@replace_exception(RuntimeError, JobError)
def copy_overlay_to_sparse_fs(image, overlay):
    """copy_overlay_to_sparse_fs
    """
    ext4_img = image + '.ext4'
    logger = logging.getLogger('dispatcher')
    guest = guestfs.GuestFS(python_return_dict=True)

    # Check if the given image is an Android sparse image
    if not is_sparse_image(image):
        raise JobError("Image is not an Android sparse image: %s" % image)

    subprocess.check_output(['/usr/bin/simg2img', image, ext4_img],
                            stderr=subprocess.STDOUT)
    guest.add_drive(ext4_img)
    _launch_guestfs(guest)
    devices = guest.list_devices()
    if not devices:
        raise InfrastructureError("Unable to prepare guestfs")
    guest.mount(devices[0], '/')
    # FIXME: max message length issues when using tar_in
    # on tar.gz.  Works fine with tar so decompressing
    # overlay first.
    if os.path.exists(overlay[:-3]):
        os.unlink(overlay[:-3])
    decompressed_overlay = decompress_file(overlay, 'gz')
    guest.tar_in(decompressed_overlay, '/')
    # Check if we have space left on the mounted image.
    output = guest.df()
    logger.debug(output)
    _, _, _, available, percent, _ = output.split("\n")[1].split()
    guest.umount(devices[0])
    if int(available) is 0 or percent == '100%':
        raise JobError("No space in image after applying overlay: %s" % image)
    subprocess.check_output(['/usr/bin/img2simg', ext4_img, image],
                            stderr=subprocess.STDOUT)
    os.remove(ext4_img)


def copy_directory_contents(root_dir, dst_dir):
    """
    Copies the contents of the root directory to the destination directory
    but excludes the root directory's top level folder
    """
    files_to_copy = glob.glob(os.path.join(root_dir, '*'))
    logger = logging.getLogger('dispatcher')
    for fname in files_to_copy:
        logger.debug("copying %s to %s", fname, os.path.join(dst_dir, os.path.basename(fname)))
        if os.path.isdir(fname):
            shutil.copytree(fname, os.path.join(dst_dir, os.path.basename(fname)))
        else:
            shutil.copy(fname, dst_dir)


def remove_directory_contents(root_dir):
    """
    Removes the contents of the root directory but not the root itself
    """
    files_to_remove = glob.glob(os.path.join(root_dir, '*'))
    logger = logging.getLogger('dispatcher')
    for fname in files_to_remove:
        logger.debug("removing %s", fname)
        if os.path.isdir(fname):
            shutil.rmtree(fname)
        else:
            os.remove(fname)


def is_sparse_image(image):
    """
    Returns True if the image is an 'Android sparse image' else False.
    """
    image_magic = magic.open(magic.MAGIC_NONE)  # pylint: disable=no-member
    image_magic.load()
    return bool(image_magic.file(image).split(',')[0] == 'Android sparse image')
