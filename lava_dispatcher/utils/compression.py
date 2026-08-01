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

import os
import subprocess  # nosec - internal use.
import tarfile
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

COMPRESSION_MAGIC: Mapping[str, bytes] = {
    "gz": b"\x1f\x8b",
    "xz": b"\xfd\x37\x7a\x58\x5a\x00",
    "bz2": b"BZ",
    "zstd": b"\x28\xb5\x2f\xfd",
}


def compress_file(infile: str, compression: str) -> str:
    if not compression:
        return infile
    if compression not in compress_command_map:
        raise JobError("Cannot find shell command to compress: %s" % compression)

    # Assume infile is an absolute path
    out_file_path = f"{infile}.{compression}"

    # Check that the command does exists
    which(compress_command_map[compression][0])
    # local copy for idempotency
    cmd = compress_command_map[compression][:]

    try:
        with (
            open(infile, mode="rb") as in_file,
            open(out_file_path, mode="wb") as out_file,
        ):
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
    if compression not in decompress_command_map:
        raise JobError("Cannot find shell command to decompress: %s" % compression)

    # Assume infile is an absolute path
    out_file_path = infile.removesuffix(f".{compression}")

    # Check that the command does exists
    which(decompress_command_map[compression][0])
    # local copy for idempotency
    cmd = decompress_command_map[compression][:]
    cmd += (infile,)

    try:
        with chdir(os.path.dirname(infile)):
            subprocess.check_output(cmd)
        return out_file_path
    except subprocess.CalledProcessError as proc_exc:
        raise JobError(
            f"unable to decompress file {infile!r}, "
            f"exit code {proc_exc.returncode}: {proc_exc.stderr!r}"
        )
    except OSError as os_exc:
        raise InfrastructureError(f"unable to decompress file {infile!r}") from os_exc


def create_tarfile(indir: str, outfile: str, arcname: str | None = None) -> None:
    try:
        with tarfile.open(outfile, "w") as tar:
            tar.add(indir, arcname=arcname)
    except tarfile.TarError as exc:
        raise InfrastructureError("Unable to create lava overlay tarball: %s" % exc)


def untar_file(infile: str, outdir: str, strip_components: int = 0) -> None:
    # Path-traversal safety is delegated to GNU tar, which by default refuses
    # to extract members with absolute paths or ".." components.
    which("tar")
    os.makedirs(outdir, exist_ok=True)
    args = ["tar", "-xf", infile]
    if strip_components:
        args.append(f"--strip-components={strip_components}")
    try:
        subprocess.run(
            args=args,
            check=True,
            stderr=subprocess.PIPE,
            encoding="utf-8",
            errors="replace",
            cwd=outdir,
        )
    except subprocess.CalledProcessError as proc_exc:
        raise JobError(
            f"unable to untar file {infile!r}, "
            f"exit code {proc_exc.returncode}: {proc_exc.stderr!r}"
        )


def cpio(directory: str, filename: str) -> str:
    which("cpio")
    which("find")
    which("fakeroot")

    try:
        find = subprocess.Popen(
            args=("find", ".", "-print0"),
            cwd=directory,
            stdout=subprocess.PIPE,
        )
        with find:
            # Use fakeroot to allow creation of device nodes and preserve ownership
            cpio = subprocess.run(
                args=(
                    "fakeroot",
                    "cpio",
                    "--create",
                    "--null",
                    "--format",
                    "newc",
                    "--file",
                    filename,
                ),
                cwd=directory,
                check=True,
                encoding="utf-8",
                errors="replace",
                stdin=find.stdout,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )
        return cpio.stdout
    except Exception as exc:
        raise InfrastructureError(
            f"Unable to create cpio archive {filename!r}: {exc}"
        ) from exc


def uncpio(filename: str, directory: str) -> None:
    which("cpio")
    which("fakeroot")
    try:
        # Use fakeroot to allow extraction of device nodes without root privileges
        subprocess.run(
            args=(
                "fakeroot",
                "cpio",
                "--extract",
                "--make-directories",
                "--unconditional",
                "--file",
                filename,
            ),
            check=True,
            cwd=directory,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except subprocess.CalledProcessError as exc:
        raise InfrastructureError(
            f"Unable to extract cpio archive {filename!r}: {exc}"
        ) from exc


# Cpio newc magic: "070701\n" (6 bytes)
CPIO_NEWC_MAGIC = b"070701"
CPIO_NEWC_HEADER_SIZE = 110
CPIO_TRAILER_NAME = b"TRAILER!!!"


def _decompress_if_needed(infile: str, compression: str | None) -> str:
    """
    Decompress a file if it's compressed, based on magic bytes or the
    provided compression algorithm.

    Used for multi-part initramfs where individual parts may have different
    compression (e.g., uncompressed cpio + gzipped cpio).

    Args:
        infile: Path to the file to decompress
        compression: Expected compression algorithm (None if uncompressed)

    Returns:
        Path to the (possibly decompressed) file
    """
    if not compression:
        return infile

    # Check magic bytes to detect actual compression
    try:
        with open(infile, "rb") as f:
            magic = f.read(6)
    except OSError:
        return infile

    comp = _detect_compression(magic)
    if comp is None:
        return infile
    if comp == compression:
        return decompress_file(infile, compression)
    return decompress_file(infile, comp)


def _detect_compression(data: bytes) -> str | None:
    """Detect compression algorithm from magic bytes.

    Args:
        data: File data to check

    Returns:
        Compression algorithm name (e.g. 'gz', 'xz') or None if uncompressed
    """
    for comp, magic in COMPRESSION_MAGIC.items():
        if data.startswith(magic[: min(6, len(magic))]):
            return comp
    return None


def split_initramfs(infile: str, outdir: str) -> list[str]:
    """
    Split a multi-part initramfs into individual cpio archives.

    Modern mkinitramfs (v0.146+) can produce initramfs files that are
    multiple cpio archives concatenated: an uncompressed cpio with kernel
    modules followed by a compressed cpio with the rest of the initrd.

    This function splits such files on cpio archive boundaries (detected
    via TRAILER!!! markers) and writes each part to outdir.

    Args:
        infile: Path to the multi-part initramfs file
        outdir: Directory to write split parts to (created if needed)

    Returns:
        List of paths to the split part files

    Raises:
        JobError: If the file is not a valid cpio archive
        InfrastructureError: If the file cannot be read
    """
    os.makedirs(outdir, exist_ok=True)

    try:
        with open(infile, "rb") as f:
            data = f.read()
    except OSError as exc:
        raise InfrastructureError(
            f"Unable to read initramfs file {infile!r}: {exc}"
        ) from exc

    if len(data) < CPIO_NEWC_HEADER_SIZE:
        raise JobError(f"Initramfs file {infile!r} is too small to be a cpio archive")

    # Find all TRAILER!!! markers
    trailer_marker = CPIO_TRAILER_NAME
    markers = []
    pos = 0
    while True:
        pos = data.find(trailer_marker, pos)
        if pos == -1:
            break
        markers.append(pos)
        pos += 1

    if not markers:
        raise JobError(f"No TRAILER!!! markers found in {infile!r}")

    # Each TRAILER!!! is the filename of the last entry in a cpio archive.
    # In newc format, the filename starts at offset 110 within the entry.
    # The namesize field does NOT include the null terminator (contrary to
    # the POSIX spec), so the actual filename size is namesize + 1.
    # For TRAILER!!! (11 chars): filename + null = 12 bytes (aligned to 4).
    # Data is 0 bytes. So the entry is: 110 + 12 + 0 = 122 bytes.
    TRAILER_ENTRY_SIZE = 122

    # Find archive boundaries
    # Each TRAILER!!! marks the end of an archive.
    # The archive includes: entries + trailing null padding
    archive_ends = []
    for marker_pos in markers:
        entry_start = marker_pos - CPIO_NEWC_HEADER_SIZE
        if entry_start < 0 or entry_start + TRAILER_ENTRY_SIZE > len(data):
            continue
        if data[entry_start : entry_start + 6] != CPIO_NEWC_MAGIC:
            continue

        # Archive ends after TRAILER!!! entry + any trailing null padding
        archive_end = entry_start + TRAILER_ENTRY_SIZE

        # Skip trailing null bytes to find where next archive starts
        while archive_end < len(data) and data[archive_end] == 0:
            archive_end += 1

        archive_ends.append(archive_end)

    # Create parts
    parts = []
    part_index = 0
    archive_start = 0

    for archive_end in archive_ends:
        part_data = data[archive_start:archive_end]
        # Detect compression and name accordingly
        compression = _detect_compression(part_data)
        suffix = f".{compression}" if compression else "cpio"
        part_path = os.path.join(outdir, f"part_{part_index:02d}.{suffix}")
        with open(part_path, "wb") as f:
            f.write(part_data)
        parts.append(part_path)

        archive_start = archive_end
        part_index += 1

    # If there's remaining data after the last archive, it could be:
    # 1. A compressed archive (gzip/xz) with no visible TRAILER!!!
    # 2. Trailing garbage
    if archive_start < len(data):
        remaining = data[archive_start:]
        # Check if it looks like a new archive
        if remaining[:6] == CPIO_NEWC_MAGIC or remaining[:2] == b"\x1f\x8b":
            compression = _detect_compression(remaining)
            suffix = f".{compression}" if compression else "cpio"
            part_path = os.path.join(outdir, f"part_{part_index:02d}.{suffix}")
            with open(part_path, "wb") as f:
                f.write(remaining)
            parts.append(part_path)

    if not parts:
        raise JobError(f"No valid cpio archives found in {infile!r}")

    return parts
