# Copyright (C) 2016 Linaro Limited
#
# Author: Matthew Hart <matthew.hart@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later


# ramdisk, always cpio, comp: gz,xz
# rootfs, always tar, comp: gz,xz,bzip2
# android images: tar + xz,bz2,gz, or just gz,xz,bzip2
# vexpress recovery images: any compression though usually zip
from __future__ import annotations

import subprocess  # nosec - internal use.
import tarfile
from pathlib import Path
from typing import TYPE_CHECKING

from lava_common.exceptions import InfrastructureError, JobError
from lava_dispatcher.utils.contextmanager import chdir
from lava_dispatcher.utils.shell import which

if TYPE_CHECKING:
    from collections.abc import Mapping

# https://www.kernel.org/doc/Documentation/xz.txt
compress_command_map: Mapping[str, tuple[str, ...]] = {
    "xz": ("xz", "--check=crc32"),
    "gz": ("gzip",),
    "bz2": ("bzip2",),
    "zstd": ("zstd", "-T0"),
}
decompress_command_map: Mapping[str, tuple[str, ...]] = {
    "xz": ("unxz",),
    "gz": ("gunzip",),
    "bz2": ("bunzip2",),
    "zip": ("unzip",),
    "zstd": ("unzstd", "-T0"),
}


def compress_file(infile: str, compression: str) -> str:
    if not compression:
        return infile
    if compression not in compress_command_map.keys():
        raise JobError("Cannot find shell command to compress: %s" % compression)

    # Assume infile is an absolute path
    out_file_path = f"{infile}.{compression}"

    # Check that the command does exists
    which(compress_command_map[compression][0])
    # local copy for idempotency
    cmd = compress_command_map[compression][:]

    try:
        with open(infile, mode="rb") as in_file, open(
            out_file_path, mode="wb"
        ) as out_file:
            subprocess.run(
                args=cmd,
                stdin=in_file,
                stdout=out_file,
                check=True,
                stderr=subprocess.PIPE,
                text=True,
            )
        return out_file_path
    except subprocess.CalledProcessError as proc_exc:
        raise InfrastructureError(
            f"unable to compress file {infile!r}, "
            f"exit code {proc_exc.returncode}: {proc_exc.stderr!r}"
        )
    except OSError as os_exc:
        raise InfrastructureError(f"unable to compress file {infile!r}") from os_exc


def decompress_file(infile: str, compression: str | None) -> str:
    if not compression:
        return infile
    if compression not in decompress_command_map.keys():
        raise JobError("Cannot find shell command to decompress: %s" % compression)

    # Assume infile is an absolute path
    out_file_path = infile.removesuffix(f".{compression}")

    # Check that the command does exists
    which(decompress_command_map[compression][0])
    # local copy for idempotency
    cmd = decompress_command_map[compression][:]

    try:
        with open(infile, mode="rb") as in_file, open(
            out_file_path, mode="wb"
        ) as out_file:
            subprocess.run(
                args=cmd,
                stdin=in_file,
                stdout=out_file,
                check=True,
                stderr=subprocess.PIPE,
                text=True,
            )
        return out_file_path
    except subprocess.CalledProcessError as proc_exc:
        raise JobError(
            f"unable to decompress file {infile!r}, "
            f"exit code {proc_exc.returncode}: {proc_exc.stderr!r}"
        )
    except OSError as os_exc:
        raise InfrastructureError(f"unable to decompress file {infile!r}") from os_exc


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
