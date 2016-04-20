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

import os
import subprocess
import tarfile

from lava_dispatcher.pipeline.action import (
    JobError
)

# https://www.kernel.org/doc/Documentation/xz.txt
compress_command_map = {'xz': 'xz --check=crc32', 'gz': 'gzip', 'bz2': 'bzip2'}
decompress_command_map = {'xz': 'unxz', 'gz': 'gunzip', 'bz2': 'bunzip2'}


def compress_file(infile, compression):
    if not compression:
        return infile
    if compression not in compress_command_map.keys():
        raise JobError("Cannot find shell command to compress: %s" % compression)
    pwd = os.getcwd()
    os.chdir(os.path.dirname(infile))
    cmd = "%s %s" % (compress_command_map[compression], infile)
    try:
        # safe to use shell=True here, no external arguments
        log = subprocess.check_output(cmd, shell=True)
        os.chdir(pwd)
        return "%s.%s" % (infile, compression)
    except OSError as exc:
        raise RuntimeError('unable to compress file %s: %s' % (infile, exc))


def decompress_file(infile, compression):
    if not compression:
        return infile
    if compression not in decompress_command_map.keys():
        raise JobError("Cannot find shell command to decompress: %s" % compression)
    os.chdir(os.path.dirname(infile))
    cmd = "%s %s" % (decompress_command_map[compression], infile)
    outfile = infile
    if infile.endswith(compression):
        outfile = infile[:-(len(compression) + 1)]
    try:
        # safe to use shell=True here, no external arguments
        log = subprocess.check_output(cmd, shell=True)
        return outfile
    except OSError as exc:
        raise RuntimeError('unable to decompress file %s: %s' % (infile, exc))


def untar_file(infile, outdir):
    try:
        tar = tarfile.open(infile)
        tar.extractall(outdir)
        tar.close()
    except tarfile.TarError as exc:
        raise JobError("Unable to unpack %s" % infile)
