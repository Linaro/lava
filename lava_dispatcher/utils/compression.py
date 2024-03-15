# Copyright (C) 2016 Linaro Limited
#
# Author: Matthew Hart <matthew.hart@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later


# ramdisk, always cpio, comp: gz,xz
# rootfs, always tar, comp: gz,xz,bzip2
# android images: tar + xz,bz2,gz, or just gz,xz,bzip2
# vexpress recovery images: any compression though usually zip

import os
import subprocess  # nosec - internal use.
import tarfile
from pathlib import Path

from lava_common.exceptions import InfrastructureError, JobError
from lava_dispatcher.utils.contextmanager import chdir
from lava_dispatcher.utils.shell import which

# https://www.kernel.org/doc/Documentation/xz.txt
compress_command_map = {
    "xz": ["xz", "--check=crc32"],
    "gz": ["gzip"],
    "bz2": ["bzip2"],
    "zstd": ["zstd"],
}
decompress_command_map = {
    "xz": ["unxz"],
    "gz": ["gunzip"],
    "bz2": ["bunzip2"],
    "zip": ["unzip"],
    "zstd": ["unzstd"],
}


def compress_file(infile, compression):
    if not compression:
        return infile
    if compression not in compress_command_map.keys():
        raise JobError("Cannot find shell command to compress: %s" % compression)

    # Check that the command does exists
    which(compress_command_map[compression][0])

    with chdir(os.path.dirname(infile)):
        # local copy for idempotency
        cmd = compress_command_map[compression][:]
        cmd.append(infile)
        try:
            subprocess.check_output(cmd)  # nosec - internal use.
            return "%s.%s" % (infile, compression)
        except (OSError, subprocess.CalledProcessError) as exc:
            raise InfrastructureError("unable to compress file %s: %s" % (infile, exc))


def decompress_file(infile, compression):
    if not compression:
        return infile
    if compression not in decompress_command_map.keys():
        raise JobError("Cannot find shell command to decompress: %s" % compression)

    # Check that the command does exists
    which(decompress_command_map[compression][0])

    with chdir(os.path.dirname(infile)):
        # local copy for idempotency
        cmd = decompress_command_map[compression][:]
        cmd.append(infile)
        outfile = infile
        if infile.endswith(compression):
            outfile = infile[: -(len(compression) + 1)]
        try:
            subprocess.check_output(cmd)  # nosec - internal use.
            return outfile
        except (OSError, subprocess.CalledProcessError) as exc:
            raise InfrastructureError(
                "unable to decompress file %s: %s" % (infile, exc)
            )


def create_tarfile(indir, outfile, arcname=None):
    try:
        with tarfile.open(outfile, "w") as tar:
            tar.add(indir, arcname=arcname)
    except tarfile.TarError as exc:
        raise InfrastructureError("Unable to create lava overlay tarball: %s" % exc)


def untar_file(infile, outdir):
    try:
        with tarfile.open(infile, encoding="utf-8") as tar:
            # Check for path traversal
            base = Path(outdir)
            for member in tar.getmembers():
                dest = (base / member.name).resolve()
                if not dest.is_relative_to(base):
                    raise JobError("Attempted path traversal in tar file at %s" % dest)
            # Extract the tarfile
            tar.extractall(outdir)
    except tarfile.TarError as exc:
        raise JobError("Unable to unpack %s: %s" % (infile, str(exc)))
    except OSError as exc:
        raise InfrastructureError("Unable to unpack %s: %s" % (infile, str(exc)))


def cpio(directory, filename):
    which("cpio")
    which("find")
    with chdir(directory):
        try:
            find = subprocess.check_output(
                ["find", "."], stderr=subprocess.STDOUT
            )  # nosec
            return subprocess.check_output(  # nosec
                ["cpio", "--create", "--format", "newc", "--file", filename],
                input=find,
                stderr=subprocess.STDOUT,
            ).decode("utf-8", errors="replace")
        except Exception as exc:
            raise InfrastructureError(
                "Unable to create cpio archive %r: %s" % (filename, exc)
            )


def uncpio(filename, directory):
    which("cpio")
    with chdir(directory):
        try:
            subprocess.check_output(  # nosec
                [
                    "cpio",
                    "--extract",
                    "--make-directories",
                    "--unconditional",
                    "--file",
                    filename,
                ],
                stderr=subprocess.STDOUT,
            )
        except subprocess.SubprocessError as exc:
            raise InfrastructureError(
                "Unable to extract cpio archive %r: %s" % (filename, exc)
            )
