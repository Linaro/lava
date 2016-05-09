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
from configobj import ConfigObj


def rmtree(directory):
    """
    Wrapper around shutil.rmtree to remove a directory tree while ignoring most
    errors.
    If called on a symbolic link, this function will raise a RuntimeError.
    """
    # TODO: consider how to handle problems if the directory has already been removed -
    # coding bugs may trigger this Runtime exception - implement before moving to production.
    try:
        shutil.rmtree(directory)
    except OSError as exc:
        raise RuntimeError("Error when trying to remove '%s': %s"
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
                '../' * 3,  # up three directories from this file - not a constant, a result of the layout.
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
    :return: real path to the TFTP directory or raises RuntimeError
    """
    var_name = 'TFTP_DIRECTORY'
    if os.path.exists('/etc/default/tftpd-hpa'):
        config = ConfigObj('/etc/default/tftpd-hpa')
        value = config.get(var_name)
        return os.path.realpath(value)
    raise RuntimeError("Unable to identify tftpd directory")


def write_bootscript(commands, filename):
    with open(filename, 'w') as bootscript:
        bootscript.write("#!ipxe\n\n")
        for line in commands:
            bootscript.write(line + "\n")
        bootscript.close()


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
    guest.launch()
    devices = guest.list_devices()
    if len(devices) != 1:
        raise RuntimeError("Unable to prepare guestfs")
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
