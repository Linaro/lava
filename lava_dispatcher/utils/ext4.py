# Copyright (C) 2026 Linaro Limited
#
# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

import json
import logging
import os
import subprocess
import tarfile
import tempfile
from pathlib import Path

from lava_common.exceptions import InfrastructureError, JobError

logger = logging.getLogger("dispatcher")


def _run_debugfs(
    image: str, commands: list[str], read_only: bool = False
) -> subprocess.CompletedProcess:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".debugfs", delete=False) as f:
        f.write("\n".join(commands) + "\n")
        cmdfile = f.name
    try:
        args = ["debugfs"]
        if not read_only:
            args.append("-w")
        args.extend(["-f", cmdfile, image])
        result = subprocess.run(args, capture_output=True, text=True, check=False)
        error_lines = [
            line
            for line in result.stderr.splitlines()
            if (
                "error" in line.lower()
                or "fatal" in line.lower()
                or "not found" in line.lower()
            )
            and not line.startswith("rm:")
        ]
        if result.returncode != 0:
            if error_lines:
                raise InfrastructureError(
                    "debugfs failed on %s: %s" % (image, "; ".join(error_lines))
                )
            raise InfrastructureError(
                "debugfs failed on %s (rc=%d): %s"
                % (image, result.returncode, result.stderr[:500])
            )
        if error_lines:
            raise InfrastructureError(
                "debugfs command errors on %s: %s" % (image, "; ".join(error_lines))
            )
        return result
    finally:
        os.unlink(cmdfile)


def _validate_tar_member(member: tarfile.TarInfo) -> None:
    if "\n" in member.name or "\r" in member.name:
        raise JobError("Tar member name contains newline: %r" % member.name)
    if " " in member.name:
        raise JobError(
            "Tar member name contains spaces (unsupported by debugfs): %r" % member.name
        )


def _tar_to_debugfs_commands(tar_path: str, target_path: str, tmpdir: str) -> list[str]:
    commands: list[str] = []
    seen_dirs: set[str] = set()
    tmpdir_base = Path(tmpdir).resolve()

    try:
        tar = tarfile.open(tar_path)
    except tarfile.TarError as exc:
        raise JobError("Failed to open tar %s: %s" % (tar_path, exc)) from exc

    try:
        members = sorted(tar.getmembers(), key=lambda m: m.name)
        for member in members:
            _validate_tar_member(member)

            ext4_path = os.path.normpath(os.path.join(target_path, member.name))
            if ext4_path == ".":
                ext4_path = "/"
            if not ext4_path.startswith("/"):
                ext4_path = "/" + ext4_path

            parent = os.path.dirname(ext4_path)
            if parent and parent != "/" and parent not in seen_dirs:
                for part in _path_parents(parent):
                    if part not in seen_dirs:
                        commands.append("mkdir %s" % part)
                        seen_dirs.add(part)

            if member.isdir():
                if ext4_path not in seen_dirs:
                    commands.append("mkdir %s" % ext4_path)
                    seen_dirs.add(ext4_path)
                mode = 0o040000 | (member.mode & 0o7777)
                commands.append("sif %s mode 0%o" % (ext4_path, mode))
                commands.append("sif %s uid %d" % (ext4_path, member.uid))
                commands.append("sif %s gid %d" % (ext4_path, member.gid))

            elif member.issym():
                commands.append("symlink %s %s" % (ext4_path, member.linkname))
                commands.append("sif %s uid %d" % (ext4_path, member.uid))
                commands.append("sif %s gid %d" % (ext4_path, member.gid))

            elif member.isfile():
                host_path = os.path.join(tmpdir, member.name)
                resolved = Path(host_path).resolve()
                if not resolved.is_relative_to(tmpdir_base):
                    raise JobError("Path traversal in tar member: %s" % member.name)
                host_dir = os.path.dirname(host_path)
                os.makedirs(host_dir, exist_ok=True)
                src = tar.extractfile(member)
                if src is not None:
                    with open(host_path, "wb") as dst:
                        while True:
                            chunk = src.read(65536)
                            if not chunk:
                                break
                            dst.write(chunk)
                    src.close()
                else:
                    with open(host_path, "wb") as dst:
                        pass

                commands.append("rm %s" % ext4_path)
                commands.append("write %s %s" % (host_path, ext4_path))
                mode = 0o100000 | (member.mode & 0o7777)
                commands.append("sif %s mode 0%o" % (ext4_path, mode))
                commands.append("sif %s uid %d" % (ext4_path, member.uid))
                commands.append("sif %s gid %d" % (ext4_path, member.gid))

            elif member.islnk():
                commands.append(
                    "ln %s %s"
                    % (
                        os.path.normpath(os.path.join(target_path, member.linkname)),
                        ext4_path,
                    )
                )

            elif member.isblk() or member.ischr():
                logger.warning(
                    "Skipping device node %s (unsupported by debugfs batch mode)",
                    member.name,
                )

            elif member.isfifo():
                logger.warning("Skipping FIFO %s", member.name)
    finally:
        tar.close()

    return commands


def _path_parents(path: str) -> list[str]:
    parts = []
    current = path
    while current and current != "/":
        parts.append(current)
        current = os.path.dirname(current)
    parts.reverse()
    return parts


def extract_partition(
    image: str, partition_index: int, tmpdir: str
) -> tuple[str, int, int]:
    result = subprocess.run(
        ["sfdisk", "-J", image], capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        raise JobError(
            "sfdisk failed to read partition table from %s: %s"
            % (image, result.stderr[:500])
        )
    try:
        table = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise JobError("Failed to parse sfdisk output for %s" % image) from exc

    partitions = table.get("partitiontable", {}).get("partitions", [])
    sector_size = table.get("partitiontable", {}).get("sectorsize", 512)

    if partition_index >= len(partitions):
        raise JobError(
            "Invalid partition number %d (image has %d partitions)"
            % (partition_index, len(partitions))
        )

    partition = partitions[partition_index]
    start = partition["start"]
    size = partition["size"]

    part_file = os.path.join(tmpdir, "partition.img")
    try:
        subprocess.run(
            [
                "dd",
                "if=%s" % image,
                "of=%s" % part_file,
                "bs=%d" % sector_size,
                "skip=%d" % start,
                "count=%d" % size,
                "status=none",
            ],
            check=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError as exc:
        raise InfrastructureError(
            "Failed to extract partition %d from %s: %s"
            % (partition_index, image, exc.stderr[:500] if exc.stderr else str(exc))
        ) from exc
    return part_file, start, sector_size


def write_partition_back(
    image: str, partition_file: str, start_sector: int, sector_size: int
) -> None:
    try:
        subprocess.run(
            [
                "dd",
                "if=%s" % partition_file,
                "of=%s" % image,
                "bs=%d" % sector_size,
                "seek=%d" % start_sector,
                "conv=notrunc",
                "status=none",
            ],
            check=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError as exc:
        raise InfrastructureError(
            "Failed to write partition back to %s: %s"
            % (image, exc.stderr[:500] if exc.stderr else str(exc))
        ) from exc


def inject_tar(
    image: str, tar_path: str, target_path: str = "/", compress: str | None = None
) -> None:
    if compress is not None and compress != "gzip":
        raise JobError("inject_tar: unsupported compression %r" % compress)

    actual_tar = tar_path
    decompressed = None

    if compress == "gzip" or (compress is None and tar_path.endswith(".gz")):
        from lava_dispatcher.utils.compression import decompress_file

        if os.path.exists(tar_path[:-3]):
            os.unlink(tar_path[:-3])
        actual_tar = decompress_file(tar_path, "gz")
        decompressed = actual_tar

    logger.debug("Injecting %s into %s at %s", actual_tar, image, target_path)

    with tempfile.TemporaryDirectory(prefix="lava-ext4-") as tmpdir:
        commands = _tar_to_debugfs_commands(actual_tar, target_path, tmpdir)
        if commands:
            logger.debug("Running %d debugfs commands on %s", len(commands), image)
            _run_debugfs(image, commands)

    if decompressed and decompressed != tar_path:
        try:
            os.unlink(decompressed)
        except OSError:
            pass


def inject_file(image: str, src_path: str, dest_path: str) -> None:
    parent = os.path.dirname(dest_path)
    commands: list[str] = []
    if parent and parent != "/":
        for part in _path_parents(parent):
            commands.append("mkdir %s" % part)
    commands.append("rm %s" % dest_path)
    commands.append("write %s %s" % (src_path, dest_path))
    logger.debug("Injecting %s into %s at %s", src_path, image, dest_path)
    _run_debugfs(image, commands)


def copy_out(image: str, filenames: list[str], destination: str) -> None:
    for filename in filenames:
        basename = os.path.basename(filename)
        host_path = os.path.join(destination, basename)
        logger.debug("Extracting %s from %s", filename, image)
        result = subprocess.run(
            ["debugfs", "-R", "dump %s %s" % (filename, host_path), image],
            capture_output=True,
            text=True,
            check=False,
        )
        error_lines = [
            line
            for line in result.stderr.splitlines()
            if "error" in line.lower() or "not found" in line.lower()
        ]
        if error_lines:
            raise JobError(
                "debugfs dump failed for %s: %s" % (filename, "; ".join(error_lines))
            )


def copy_out_iso(image: str, filenames: list[str], destination: str) -> None:
    for filename in filenames:
        basename = os.path.basename(filename)
        host_path = os.path.join(destination, basename)
        logger.debug("Extracting %s from ISO %s", filename, image)
        try:
            subprocess.run(
                ["bsdtar", "-xf", image, "-C", destination, filename.lstrip("/")],
                check=True,
                capture_output=True,
            )
        except FileNotFoundError:
            raise InfrastructureError(
                "bsdtar not found; install libarchive-tools to extract files from ISOs"
            )
        except subprocess.CalledProcessError as exc:
            raise JobError(
                "Failed to extract %s from %s: %s"
                % (filename, image, exc.stderr[:500] if exc.stderr else str(exc))
            ) from exc
        extracted = os.path.join(destination, filename.lstrip("/"))
        if extracted != host_path and os.path.exists(extracted):
            os.rename(extracted, host_path)


def create_ext4(path: str, size_mb: int, label: str = "LAVA") -> str:
    try:
        subprocess.run(
            ["truncate", "-s", "%dM" % size_mb, path],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["mkfs.ext4", "-q", "-L", label, "-F", path],
            check=True,
            capture_output=True,
        )
        result = subprocess.run(
            ["blkid", "-s", "UUID", "-o", "value", path],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        raise InfrastructureError(
            "Failed to create ext4 filesystem at %s: %s"
            % (path, exc.stderr[:500] if exc.stderr else str(exc))
        ) from exc
    return result.stdout.strip()
