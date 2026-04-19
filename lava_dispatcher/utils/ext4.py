# Copyright (C) 2026 Linaro Limited
#
# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import tarfile
import tempfile
from pathlib import Path

from lava_common.exceptions import InfrastructureError, JobError

logger = logging.getLogger("dispatcher")

DEBUGFS_BATCH_SIZE = 256

_DEBUGFS_ERROR_RE = re.compile(
    r"^(debugfs|ext2fs_\w+|mkdir|write|ln|symlink|dump|sif|close|Fatal error):"
)
_BENIGN_RM_RE = re.compile(r"^rm:.*not found", re.IGNORECASE)


def _is_debugfs_error(line: str) -> bool:
    if _DEBUGFS_ERROR_RE.match(line):
        return True
    if line.startswith("rm:") and not _BENIGN_RM_RE.match(line):
        return True
    return False


def _summarise_error_lines(lines: list[str], limit: int = 3) -> str:
    """Collapse repeated debugfs error lines into 'msg (xN)' form."""
    from collections import Counter

    counts = Counter(lines)
    parts = []
    for line, count in counts.most_common(limit):
        parts.append(line if count == 1 else "%s (x%d)" % (line, count))
    extras = len(counts) - limit
    if extras > 0:
        parts.append("(+%d more distinct errors)" % extras)
    return "; ".join(parts)


def _is_out_of_space(error_lines: list[str]) -> bool:
    return any("Could not allocate block" in line for line in error_lines)


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
            line for line in result.stderr.splitlines() if _is_debugfs_error(line)
        ]
        if _is_out_of_space(error_lines):
            raise JobError(
                "No space left in image %s while writing overlay "
                "(first error: %s). Increase image size or drop the overlay."
                % (image, error_lines[0])
            )
        if result.returncode != 0:
            if error_lines:
                raise InfrastructureError(
                    "debugfs failed on %s: %s"
                    % (image, _summarise_error_lines(error_lines))
                )
            raise InfrastructureError(
                "debugfs failed on %s (rc=%d): %s"
                % (image, result.returncode, result.stderr[:500])
            )
        if error_lines:
            raise InfrastructureError(
                "debugfs command errors on %s: %s"
                % (image, _summarise_error_lines(error_lines))
            )
        return result
    finally:
        os.unlink(cmdfile)


def _ext4_free_bytes(image: str) -> int | None:
    """Return free bytes reported by dumpe2fs, or None on failure."""
    result = subprocess.run(
        ["dumpe2fs", "-h", image], capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        return None
    free_blocks = 0
    block_size = 4096
    for line in result.stdout.splitlines():
        if line.startswith("Free blocks:"):
            free_blocks = int(line.split(":")[1].strip())
        elif line.startswith("Block size:"):
            block_size = int(line.split(":")[1].strip())
    return free_blocks * block_size


def _tar_payload_bytes(tar_path: str) -> int:
    """Sum the file-content bytes in a tar, rounded up to 4 KiB blocks."""
    total = 0
    try:
        with tarfile.open(tar_path) as tar:
            for member in tar:
                if member.isfile():
                    total += (member.size + 4095) & ~4095
    except (tarfile.TarError, OSError):
        return 0
    return total


def _run_debugfs_batched(
    image: str, commands: list[str], batch_size: int = DEBUGFS_BATCH_SIZE
) -> None:
    for start in range(0, len(commands), batch_size):
        _run_debugfs(image, commands[start : start + batch_size])


_STAT_TYPE_RE = re.compile(r"Type:\s+(\w+)")
_STAT_FAST_LINK_RE = re.compile(r'Fast link dest:\s+"([^"]+)"')
_STAT_NOT_FOUND_RE = re.compile(r"File not found", re.IGNORECASE)


def _stat_path(image: str, path: str) -> dict | None:
    """Return {'type': ..., 'target': ...} or None if the path does not exist."""
    result = subprocess.run(
        ["debugfs", "-R", 'stat "%s"' % path, image],
        capture_output=True,
        text=True,
        check=False,
    )
    combined = result.stdout + "\n" + result.stderr
    if _STAT_NOT_FOUND_RE.search(combined):
        return None
    m = _STAT_TYPE_RE.search(result.stdout)
    if not m:
        return None
    info = {"type": m.group(1), "target": None}
    if info["type"] == "symlink":
        tm = _STAT_FAST_LINK_RE.search(result.stdout)
        if tm:
            info["target"] = tm.group(1)
    return info


def _resolve_symlink(image: str, path: str, cache: dict[str, str]) -> str:
    """Resolve every component of *path* through fast symlinks found on *image*.

    Returns the resolved absolute path. Missing components stop resolution:
    anything below a missing component is treated as fresh and returned as-is.
    """
    if path in cache:
        return cache[path]
    parts = [p for p in path.split("/") if p]
    current = ""
    for idx, part in enumerate(parts):
        candidate = (current + "/" + part) if current else "/" + part
        if candidate in cache:
            current = cache[candidate]
            continue
        resolved = candidate
        for _ in range(40):
            info = _stat_path(image, resolved)
            if info is None or info["type"] != "symlink" or info["target"] is None:
                break
            target = info["target"]
            if target.startswith("/"):
                resolved = os.path.normpath(target)
            else:
                resolved = os.path.normpath(
                    os.path.join(os.path.dirname(resolved), target)
                )
        cache[candidate] = resolved
        # Nothing below a missing path is worth probing; short-circuit.
        if _stat_path(image, resolved) is None and idx < len(parts) - 1:
            rest = "/".join(parts[idx + 1 :])
            full = resolved.rstrip("/") + "/" + rest
            cache[path] = full
            return full
        current = resolved
    cache[path] = current or "/"
    return cache[path]


def _validate_tar_member(member: tarfile.TarInfo) -> None:
    # debugfs batch mode parses commands one per line, so newlines are fatal.
    # Double-quote and backslash would break our _q() quoting below, so we
    # reject them too; they shouldn't appear in legitimate filesystem paths.
    for attr in ("name", "linkname"):
        value = getattr(member, attr, "") or ""
        if "\n" in value or "\r" in value:
            raise JobError("Tar member %s contains newline: %r" % (attr, value))
        if '"' in value or "\\" in value:
            raise JobError(
                'Tar member %s contains unsupported character (" or \\): %r'
                % (attr, value)
            )


def _q(path: str) -> str:
    """Double-quote a path for debugfs batch mode."""
    return '"%s"' % path


def _tar_to_debugfs_commands(
    tar_path: str,
    target_path: str,
    tmpdir: str,
    image: str | None = None,
) -> list[str]:
    commands: list[str] = []
    seen_dirs: set[str] = set()
    tmpdir_base = Path(tmpdir).resolve()
    symlink_cache: dict[str, str] = {}

    def resolve(p: str) -> str:
        if image is None:
            return p
        return _resolve_symlink(image, p, symlink_cache)

    try:
        tar = tarfile.open(tar_path)
    except tarfile.TarError as exc:
        raise JobError("Failed to open tar %s: %s" % (tar_path, exc)) from exc

    try:
        members = sorted(tar.getmembers(), key=lambda m: m.name)
        for member in members:
            _validate_tar_member(member)

            raw_path = os.path.normpath(os.path.join(target_path, member.name))
            if raw_path == ".":
                raw_path = "/"
            if not raw_path.startswith("/"):
                raw_path = "/" + raw_path

            ext4_path = resolve(raw_path)

            parent = os.path.dirname(ext4_path)
            if parent and parent != "/" and parent not in seen_dirs:
                for part in _path_parents(parent):
                    if part in seen_dirs:
                        continue
                    seen_dirs.add(part)
                    if image is not None and _stat_path(image, part) is not None:
                        # Already present in the image — don't mkdir it.
                        continue
                    commands.append("mkdir %s" % _q(part))

            if member.isdir():
                if ext4_path not in seen_dirs:
                    seen_dirs.add(ext4_path)
                    already = (
                        image is not None and _stat_path(image, ext4_path) is not None
                    )
                    if not already:
                        commands.append("mkdir %s" % _q(ext4_path))
                mode = 0o040000 | (member.mode & 0o7777)
                commands.append("sif %s mode 0%o" % (_q(ext4_path), mode))
                commands.append("sif %s uid %d" % (_q(ext4_path), member.uid))
                commands.append("sif %s gid %d" % (_q(ext4_path), member.gid))

            elif member.issym():
                commands.append("symlink %s %s" % (_q(ext4_path), _q(member.linkname)))
                commands.append("sif %s uid %d" % (_q(ext4_path), member.uid))
                commands.append("sif %s gid %d" % (_q(ext4_path), member.gid))

            elif member.isfile():
                host_path = os.path.join(tmpdir, member.name)
                resolved_host = Path(host_path).resolve()
                if not resolved_host.is_relative_to(tmpdir_base):
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

                commands.append("rm %s" % _q(ext4_path))
                commands.append("write %s %s" % (_q(host_path), _q(ext4_path)))
                mode = 0o100000 | (member.mode & 0o7777)
                commands.append("sif %s mode 0%o" % (_q(ext4_path), mode))
                commands.append("sif %s uid %d" % (_q(ext4_path), member.uid))
                commands.append("sif %s gid %d" % (_q(ext4_path), member.gid))

            elif member.islnk():
                target_raw = os.path.normpath(
                    os.path.join(target_path, member.linkname)
                )
                commands.append("ln %s %s" % (_q(resolve(target_raw)), _q(ext4_path)))

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
    if compress is not None and compress not in ("gzip", "xz"):
        raise JobError("inject_tar: unsupported compression %r" % compress)

    actual_tar = tar_path
    decompressed = None

    if compress == "gzip" or (compress is None and tar_path.endswith(".gz")):
        from lava_dispatcher.utils.compression import decompress_file

        if os.path.exists(tar_path[:-3]):
            os.unlink(tar_path[:-3])
        actual_tar = decompress_file(tar_path, "gz")
        decompressed = actual_tar
    elif compress == "xz" or (compress is None and tar_path.endswith(".xz")):
        from lava_dispatcher.utils.compression import decompress_file

        if os.path.exists(tar_path[:-3]):
            os.unlink(tar_path[:-3])
        actual_tar = decompress_file(tar_path, "xz")
        decompressed = actual_tar

    logger.debug("Injecting %s into %s at %s", actual_tar, image, target_path)

    free_bytes = _ext4_free_bytes(image)
    needed_bytes = _tar_payload_bytes(actual_tar)
    if free_bytes is not None and needed_bytes and free_bytes < needed_bytes:
        raise JobError(
            "Not enough free space in %s: need ~%d MiB, have %d MiB. "
            "Increase the image size or drop the overlay."
            % (image, needed_bytes // (1024 * 1024), free_bytes // (1024 * 1024))
        )

    with tempfile.TemporaryDirectory(prefix="lava-ext4-") as tmpdir:
        commands = _tar_to_debugfs_commands(actual_tar, target_path, tmpdir, image)
        if commands:
            logger.debug(
                "Running %d debugfs commands on %s in batches of %d (need %d MiB, "
                "have %s MiB free)",
                len(commands),
                image,
                DEBUGFS_BATCH_SIZE,
                needed_bytes // (1024 * 1024),
                (str(free_bytes // (1024 * 1024)) if free_bytes is not None else "?"),
            )
            _run_debugfs_batched(image, commands)

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
            commands.append("mkdir %s" % _q(part))
    commands.append("rm %s" % _q(dest_path))
    commands.append("write %s %s" % (_q(src_path), _q(dest_path)))
    logger.debug("Injecting %s into %s at %s", src_path, image, dest_path)
    _run_debugfs(image, commands)


def copy_out(image: str, filenames: list[str], destination: str) -> None:
    for filename in filenames:
        basename = os.path.basename(filename)
        host_path = os.path.join(destination, basename)
        logger.debug("Extracting %s from %s", filename, image)
        result = subprocess.run(
            ["debugfs", "-R", 'dump "%s" "%s"' % (filename, host_path), image],
            capture_output=True,
            text=True,
            check=False,
        )
        error_lines = [
            line for line in result.stderr.splitlines() if _is_debugfs_error(line)
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
