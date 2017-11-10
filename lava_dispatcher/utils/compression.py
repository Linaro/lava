# Copyright (C) 2016 Linaro Limited
#
# Author: Matthew Hart <matthew.hart@linaro.org>
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


# ramdisk, always cpio, comp: gz,xz
# rootfs, always tar, comp: gz,xz,bzip2
# android images: tar + xz,bz2,gz, or just gz,xz,bzip2
# vexpress recovery images: any compression though usually zip

import os
import subprocess
import tarfile

from lava_dispatcher.action import (
    InfrastructureError,
    JobError
)

from lava_dispatcher.utils.contextmanager import chdir


# https://www.kernel.org/doc/Documentation/xz.txt
compress_command_map = {'xz': 'xz --check=crc32', 'gz': 'gzip', 'bz2': 'bzip2'}
decompress_command_map = {'xz': 'unxz', 'gz': 'gunzip', 'bz2': 'bunzip2', 'zip': 'unzip'}


def compress_file(infile, compression):
    if not compression:
        return infile
    if compression not in compress_command_map.keys():
        raise JobError("Cannot find shell command to compress: %s" % compression)

    with chdir(os.path.dirname(infile)):
        cmd = "%s %s" % (compress_command_map[compression], infile)
        try:
            # safe to use shell=True here, no external arguments
            subprocess.check_output(cmd, shell=True)
            return "%s.%s" % (infile, compression)
        except (OSError, subprocess.CalledProcessError) as exc:
            raise InfrastructureError('unable to compress file %s: %s' % (infile, exc))


def decompress_file(infile, compression):
    if not compression:
        return infile
    if compression not in decompress_command_map.keys():
        raise JobError("Cannot find shell command to decompress: %s" % compression)

    with chdir(os.path.dirname(infile)):
        cmd = "%s %s" % (decompress_command_map[compression], infile)
        outfile = infile
        if infile.endswith(compression):
            outfile = infile[:-(len(compression) + 1)]
        try:
            # safe to use shell=True here, no external arguments
            subprocess.check_output(cmd, shell=True)
            return outfile
        except (OSError, subprocess.CalledProcessError) as exc:
            raise InfrastructureError('unable to decompress file %s: %s' % (infile, exc))


def untar_file(infile, outdir, member=None, outfile=None):
    try:
        tar = tarfile.open(infile)
        if member:
            file_obj = tar.extractfile(member)
            target = open(outfile, 'wb')
            target.write(file_obj.read())
            target.close()
            file_obj.close()
            tar.close()
        else:
            tar.extractall(outdir)
            tar.close()
    except tarfile.TarError as exc:
        raise JobError("Unable to unpack %s: %s" % (infile, str(exc)))
