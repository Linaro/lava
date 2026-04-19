# Copyright (C) 2026 Linaro Limited
#
# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

import io
import json
import os
import subprocess
import tarfile
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from lava_common.exceptions import InfrastructureError, JobError
from lava_dispatcher.utils.ext4 import (
    DEBUGFS_BATCH_SIZE,
    _ext4_free_bytes,
    _is_debugfs_error,
    _is_out_of_space,
    _path_parents,
    _resolve_symlink,
    _run_debugfs,
    _run_debugfs_batched,
    _stat_path,
    _summarise_error_lines,
    _tar_payload_bytes,
    _tar_to_debugfs_commands,
    _validate_tar_member,
    copy_out,
    copy_out_iso,
    create_ext4,
    extract_partition,
    inject_file,
    inject_tar,
    write_partition_back,
)


class TestPathParents(unittest.TestCase):
    def test_simple(self):
        self.assertEqual(_path_parents("/a/b/c"), ["/a", "/a/b", "/a/b/c"])

    def test_root(self):
        self.assertEqual(_path_parents("/"), [])

    def test_single_level(self):
        self.assertEqual(_path_parents("/foo"), ["/foo"])


class TestValidateTarMember(unittest.TestCase):
    def test_valid_name(self):
        info = tarfile.TarInfo(name="usr/lib/file.so")
        _validate_tar_member(info)

    def test_newline_rejected(self):
        info = tarfile.TarInfo(name="usr/lib/file\n.so")
        with self.assertRaises(JobError) as ctx:
            _validate_tar_member(info)
        self.assertIn("newline", str(ctx.exception))

    def test_carriage_return_rejected(self):
        info = tarfile.TarInfo(name="usr/lib/file\r.so")
        with self.assertRaises(JobError) as ctx:
            _validate_tar_member(info)
        self.assertIn("newline", str(ctx.exception))

    def test_space_accepted(self):
        info = tarfile.TarInfo(name="devices/probe/boards/Dell Inc.,XPS 13 9300.yaml")
        _validate_tar_member(info)

    def test_double_quote_rejected(self):
        info = tarfile.TarInfo(name='usr/lib/bad".so')
        with self.assertRaises(JobError) as ctx:
            _validate_tar_member(info)
        self.assertIn("unsupported character", str(ctx.exception))

    def test_backslash_rejected(self):
        info = tarfile.TarInfo(name="usr/lib/bad\\.so")
        with self.assertRaises(JobError) as ctx:
            _validate_tar_member(info)
        self.assertIn("unsupported character", str(ctx.exception))

    def test_linkname_newline_rejected(self):
        info = tarfile.TarInfo(name="usr/lib/link.so")
        info.linkname = "target\n.so"
        with self.assertRaises(JobError) as ctx:
            _validate_tar_member(info)
        self.assertIn("linkname", str(ctx.exception))
        self.assertIn("newline", str(ctx.exception))

    def test_linkname_space_accepted(self):
        info = tarfile.TarInfo(name="usr/lib/link.so")
        info.linkname = "my target.so"
        _validate_tar_member(info)

    def test_hardlink_linkname_newline_rejected(self):
        info = tarfile.TarInfo(name="usr/lib/link.so")
        info.type = tarfile.LNKTYPE
        info.linkname = "usr/lib/target\n.so"
        with self.assertRaises(JobError) as ctx:
            _validate_tar_member(info)
        self.assertIn("linkname", str(ctx.exception))
        self.assertIn("newline", str(ctx.exception))

    def test_hardlink_linkname_space_accepted(self):
        info = tarfile.TarInfo(name="usr/lib/link.so")
        info.type = tarfile.LNKTYPE
        info.linkname = "usr/lib/my target.so"
        _validate_tar_member(info)


class TestRunDebugfs(unittest.TestCase):
    @patch("lava_dispatcher.utils.ext4.subprocess.run")
    def test_success(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stderr="", stdout="")
        result = _run_debugfs("/tmp/test.img", ["ls /"])
        self.assertEqual(result.returncode, 0)
        args = mock_run.call_args[0][0]
        self.assertEqual(args[0], "debugfs")
        self.assertIn("-w", args)

    @patch("lava_dispatcher.utils.ext4.subprocess.run")
    def test_read_only(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stderr="", stdout="")
        _run_debugfs("/tmp/test.img", ["ls /"], read_only=True)
        args = mock_run.call_args[0][0]
        self.assertNotIn("-w", args)

    @patch("lava_dispatcher.utils.ext4.subprocess.run")
    def test_failure_with_error_lines(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=1, stderr="Fatal error: bad magic\n", stdout=""
        )
        with self.assertRaises(InfrastructureError) as ctx:
            _run_debugfs("/tmp/test.img", ["ls /"])
        self.assertIn("bad magic", str(ctx.exception))

    @patch("lava_dispatcher.utils.ext4.subprocess.run")
    def test_failure_generic(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=1, stderr="something went wrong\n", stdout=""
        )
        with self.assertRaises(InfrastructureError) as ctx:
            _run_debugfs("/tmp/test.img", ["ls /"])
        self.assertIn("rc=1", str(ctx.exception))

    @patch("lava_dispatcher.utils.ext4.subprocess.run")
    def test_stderr_errors_with_zero_rc(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stderr="write: File not found by ext2_lookup\n",
            stdout="",
        )
        with self.assertRaises(InfrastructureError) as ctx:
            _run_debugfs("/tmp/test.img", ["write /tmp/f /f"])
        self.assertIn("not found", str(ctx.exception))

    @patch("lava_dispatcher.utils.ext4.subprocess.run")
    def test_rm_not_found_ignored(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stderr="rm: File not found by ext2_lookup while trying to resolve filename\n",
            stdout="",
        )
        result = _run_debugfs("/tmp/test.img", ["rm /nonexistent", "write /tmp/f /f"])
        self.assertEqual(result.returncode, 0)

    @patch("lava_dispatcher.utils.ext4.subprocess.run")
    def test_filename_containing_error_not_flagged(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stderr=(
                "Allocated 12 blocks starting at 42048 "
                "(/lib/modules/7.0.0/kernel/drivers/crypto/caam/error.ko)\n"
            ),
            stdout="",
        )
        result = _run_debugfs("/tmp/test.img", ["write /tmp/f /f"])
        self.assertEqual(result.returncode, 0)

    @patch("lava_dispatcher.utils.ext4.subprocess.run")
    def test_short_read_flagged_as_error(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=1,
            stderr=(
                "debugfs: Attempt to read block from filesystem resulted in "
                "short read while reading inode table\n"
            ),
            stdout="",
        )
        with self.assertRaises(InfrastructureError) as ctx:
            _run_debugfs("/tmp/test.img", ["ls /"])
        self.assertIn("short read", str(ctx.exception))


class TestIsDebugfsError(unittest.TestCase):
    def test_debugfs_prefix(self):
        self.assertTrue(_is_debugfs_error("debugfs: Attempt to read block"))

    def test_write_prefix(self):
        self.assertTrue(_is_debugfs_error("write: No space left on device"))

    def test_ext2fs_prefix(self):
        self.assertTrue(_is_debugfs_error("ext2fs_read_inode_full: bad magic"))

    def test_fatal_error(self):
        self.assertTrue(_is_debugfs_error("Fatal error: bad magic number"))

    def test_rm_not_found_benign(self):
        self.assertFalse(_is_debugfs_error("rm: File not found by ext2_lookup"))

    def test_rm_real_error(self):
        self.assertTrue(_is_debugfs_error("rm: Invalid argument"))

    def test_informational_with_error_in_filename(self):
        self.assertFalse(
            _is_debugfs_error(
                "Allocated 12 blocks: /lib/modules/x/kernel/crypto/error.ko"
            )
        )

    def test_empty_line(self):
        self.assertFalse(_is_debugfs_error(""))


class TestStatPath(unittest.TestCase):
    @patch("lava_dispatcher.utils.ext4.subprocess.run")
    def test_directory(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="Inode: 2   Type: directory    Mode:  0755",
            stderr="",
        )
        info = _stat_path("/tmp/img.ext4", "/lib")
        self.assertEqual(info, {"type": "directory", "target": None})

    @patch("lava_dispatcher.utils.ext4.subprocess.run")
    def test_symlink_fast(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=(
                "Inode: 794   Type: symlink    Mode:  0777\n"
                'Fast link dest: "usr/lib"\n'
            ),
            stderr="",
        )
        info = _stat_path("/tmp/img.ext4", "/lib")
        self.assertEqual(info, {"type": "symlink", "target": "usr/lib"})

    @patch("lava_dispatcher.utils.ext4.subprocess.run")
    def test_missing(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="",
            stderr="/foo: File not found by ext2_lookup\n",
        )
        self.assertIsNone(_stat_path("/tmp/img.ext4", "/foo"))


class TestResolveSymlink(unittest.TestCase):
    @patch("lava_dispatcher.utils.ext4._stat_path")
    def test_simple_directory_chain(self, mock_stat):
        mock_stat.return_value = {"type": "directory", "target": None}
        cache: dict[str, str] = {}
        self.assertEqual(
            _resolve_symlink("/tmp/img.ext4", "/lib/modules", cache),
            "/lib/modules",
        )

    @patch("lava_dispatcher.utils.ext4._stat_path")
    def test_relative_symlink(self, mock_stat):
        def stat(image, path):
            if path == "/lib":
                return {"type": "symlink", "target": "usr/lib"}
            if path == "/usr":
                return {"type": "directory", "target": None}
            if path == "/usr/lib":
                return {"type": "directory", "target": None}
            return None

        mock_stat.side_effect = stat
        cache: dict[str, str] = {}
        self.assertEqual(
            _resolve_symlink("/tmp/img.ext4", "/lib/modules/foo", cache),
            "/usr/lib/modules/foo",
        )

    @patch("lava_dispatcher.utils.ext4._stat_path")
    def test_absolute_symlink(self, mock_stat):
        def stat(image, path):
            if path == "/bin":
                return {"type": "symlink", "target": "/usr/bin"}
            if path == "/usr/bin":
                return {"type": "directory", "target": None}
            return None

        mock_stat.side_effect = stat
        cache: dict[str, str] = {}
        self.assertEqual(
            _resolve_symlink("/tmp/img.ext4", "/bin/ls", cache),
            "/usr/bin/ls",
        )

    @patch("lava_dispatcher.utils.ext4._stat_path")
    def test_cache_reuse(self, mock_stat):
        mock_stat.return_value = {"type": "directory", "target": None}
        cache: dict[str, str] = {}
        _resolve_symlink("/tmp/img.ext4", "/a/b/c", cache)
        calls_first = mock_stat.call_count
        _resolve_symlink("/tmp/img.ext4", "/a/b/c", cache)
        self.assertEqual(mock_stat.call_count, calls_first)


class TestRunDebugfsBatched(unittest.TestCase):
    @patch("lava_dispatcher.utils.ext4._run_debugfs")
    def test_single_batch(self, mock_run):
        _run_debugfs_batched("/tmp/image.ext4", ["mkdir /a", "mkdir /b"])
        self.assertEqual(mock_run.call_count, 1)
        self.assertEqual(mock_run.call_args[0][1], ["mkdir /a", "mkdir /b"])

    @patch("lava_dispatcher.utils.ext4._run_debugfs")
    def test_splits_large_batch(self, mock_run):
        commands = ["mkdir /d%d" % i for i in range(DEBUGFS_BATCH_SIZE * 2 + 10)]
        _run_debugfs_batched("/tmp/image.ext4", commands)
        self.assertEqual(mock_run.call_count, 3)
        self.assertEqual(len(mock_run.call_args_list[0][0][1]), DEBUGFS_BATCH_SIZE)
        self.assertEqual(len(mock_run.call_args_list[1][0][1]), DEBUGFS_BATCH_SIZE)
        self.assertEqual(len(mock_run.call_args_list[2][0][1]), 10)

    @patch("lava_dispatcher.utils.ext4._run_debugfs")
    def test_custom_batch_size(self, mock_run):
        commands = ["mkdir /d%d" % i for i in range(10)]
        _run_debugfs_batched("/tmp/image.ext4", commands, batch_size=3)
        self.assertEqual(mock_run.call_count, 4)

    @patch("lava_dispatcher.utils.ext4._run_debugfs")
    def test_empty_commands(self, mock_run):
        _run_debugfs_batched("/tmp/image.ext4", [])
        mock_run.assert_not_called()


class TestOutOfSpaceHandling(unittest.TestCase):
    def test_is_out_of_space_detects(self):
        self.assertTrue(
            _is_out_of_space(["write: Could not allocate block in ext2 filesystem"])
        )

    def test_is_out_of_space_ignores_other_errors(self):
        self.assertFalse(_is_out_of_space(["mkdir: Ext2 directory already exists"]))

    def test_summarise_collapses_duplicates(self):
        lines = ["write: Could not allocate block in ext2 filesystem"] * 34
        summary = _summarise_error_lines(lines)
        self.assertIn("(x34)", summary)
        self.assertEqual(summary.count(";"), 0)

    def test_summarise_truncates_many_distinct(self):
        lines = ["mkdir: err %d" % i for i in range(10)]
        summary = _summarise_error_lines(lines, limit=3)
        self.assertIn("(+7 more distinct errors)", summary)

    @patch("lava_dispatcher.utils.ext4.subprocess.run")
    def test_run_debugfs_raises_joberror_on_out_of_space(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=1,
            stderr=(
                "write: Could not allocate block in ext2 filesystem\n"
                "write: Could not allocate block in ext2 filesystem\n"
            ),
            stdout="",
        )
        with self.assertRaises(JobError) as ctx:
            _run_debugfs("/tmp/image.ext4", ["write /host /dest"])
        self.assertIn("No space left", str(ctx.exception))
        self.assertIn("Increase image size", str(ctx.exception))


class TestExt4FreeBytes(unittest.TestCase):
    @patch("lava_dispatcher.utils.ext4.subprocess.run")
    def test_parses_dumpe2fs(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=(
                "Filesystem OS type:       Linux\n"
                "Free blocks:              12345\n"
                "Block size:               4096\n"
            ),
        )
        self.assertEqual(_ext4_free_bytes("/tmp/img.ext4"), 12345 * 4096)

    @patch("lava_dispatcher.utils.ext4.subprocess.run")
    def test_returns_none_on_failure(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="bad")
        self.assertIsNone(_ext4_free_bytes("/tmp/img.ext4"))


class TestTarPayloadBytes(unittest.TestCase):
    def test_counts_file_sizes_rounded_up(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tar_path = os.path.join(tmpdir, "a.tar")
            with tarfile.open(tar_path, "w") as tar:
                for name, size in [("a", 1), ("b", 4096), ("c", 4097)]:
                    info = tarfile.TarInfo(name=name)
                    info.size = size
                    tar.addfile(info, io.BytesIO(b"\0" * size))
            self.assertEqual(_tar_payload_bytes(tar_path), 4096 + 4096 + 8192)

    def test_returns_zero_on_bad_tar(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bad = os.path.join(tmpdir, "bad.tar")
            with open(bad, "wb") as f:
                f.write(b"not a tar")
            self.assertEqual(_tar_payload_bytes(bad), 0)


class TestTarToDebugfsCommands(unittest.TestCase):
    def _make_tar(self, tmpdir, members):
        tar_path = os.path.join(tmpdir, "test.tar")
        with tarfile.open(tar_path, "w") as tar:
            for m in members:
                tar.addfile(m)
        return tar_path

    def test_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            info = tarfile.TarInfo(name="mydir")
            info.type = tarfile.DIRTYPE
            info.mode = 0o755
            info.uid = 0
            info.gid = 0
            tar_path = self._make_tar(tmpdir, [info])
            extract_dir = os.path.join(tmpdir, "extract")
            os.makedirs(extract_dir)
            commands = _tar_to_debugfs_commands(tar_path, "/", extract_dir)
            self.assertIn('mkdir "/mydir"', commands)
            self.assertIn('sif "/mydir" mode 040755', commands)
            self.assertIn('sif "/mydir" uid 0', commands)
            self.assertIn('sif "/mydir" gid 0', commands)

    def test_regular_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            info = tarfile.TarInfo(name="hello.txt")
            info.size = 5
            info.mode = 0o644
            info.uid = 1000
            info.gid = 1000
            content = io.BytesIO(b"hello")

            tar_path = os.path.join(tmpdir, "test.tar")
            with tarfile.open(tar_path, "w") as tar:
                tar.addfile(info, content)

            extract_dir = os.path.join(tmpdir, "extract")
            os.makedirs(extract_dir)
            commands = _tar_to_debugfs_commands(tar_path, "/", extract_dir)
            self.assertIn('rm "/hello.txt"', commands)
            self.assertTrue(
                any(
                    c.startswith("write ") and c.endswith(' "/hello.txt"')
                    for c in commands
                )
            )
            self.assertIn('sif "/hello.txt" mode 0100644', commands)
            self.assertIn('sif "/hello.txt" uid 1000', commands)
            self.assertIn('sif "/hello.txt" gid 1000', commands)
            host_path = os.path.join(extract_dir, "hello.txt")
            self.assertTrue(os.path.exists(host_path))
            with open(host_path) as f:
                self.assertEqual(f.read(), "hello")

    def test_symlink(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            info = tarfile.TarInfo(name="link")
            info.type = tarfile.SYMTYPE
            info.linkname = "target"
            info.uid = 0
            info.gid = 0
            tar_path = self._make_tar(tmpdir, [info])
            extract_dir = os.path.join(tmpdir, "extract")
            os.makedirs(extract_dir)
            commands = _tar_to_debugfs_commands(tar_path, "/", extract_dir)
            self.assertIn('symlink "/link" "target"', commands)
            self.assertIn('sif "/link" uid 0', commands)

    def test_hardlink(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            info = tarfile.TarInfo(name="hardlink")
            info.type = tarfile.LNKTYPE
            info.linkname = "original"
            tar_path = self._make_tar(tmpdir, [info])
            extract_dir = os.path.join(tmpdir, "extract")
            os.makedirs(extract_dir)
            commands = _tar_to_debugfs_commands(tar_path, "/", extract_dir)
            self.assertIn('ln "/original" "/hardlink"', commands)

    def test_nested_creates_parents(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            info = tarfile.TarInfo(name="a/b/c")
            info.type = tarfile.DIRTYPE
            info.mode = 0o755
            info.uid = 0
            info.gid = 0
            tar_path = self._make_tar(tmpdir, [info])
            extract_dir = os.path.join(tmpdir, "extract")
            os.makedirs(extract_dir)
            commands = _tar_to_debugfs_commands(tar_path, "/", extract_dir)
            mkdir_cmds = [c for c in commands if c.startswith("mkdir")]
            self.assertIn('mkdir "/a"', mkdir_cmds)
            self.assertIn('mkdir "/a/b"', mkdir_cmds)
            self.assertIn('mkdir "/a/b/c"', mkdir_cmds)

    def test_path_traversal_rejected(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            info = tarfile.TarInfo(name="../../../etc/passwd")
            info.size = 5
            info.mode = 0o644
            info.uid = 0
            info.gid = 0
            content = io.BytesIO(b"evil!")
            tar_path = os.path.join(tmpdir, "test.tar")
            with tarfile.open(tar_path, "w") as tar:
                tar.addfile(info, content)
            extract_dir = os.path.join(tmpdir, "extract")
            os.makedirs(extract_dir)
            with self.assertRaises(JobError) as ctx:
                _tar_to_debugfs_commands(tar_path, "/", extract_dir)
            self.assertIn("Path traversal", str(ctx.exception))

    def test_invalid_tar_raises_job_error(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bad_tar = os.path.join(tmpdir, "bad.tar")
            with open(bad_tar, "wb") as f:
                f.write(b"not a tar file")
            extract_dir = os.path.join(tmpdir, "extract")
            os.makedirs(extract_dir)
            with self.assertRaises(JobError) as ctx:
                _tar_to_debugfs_commands(bad_tar, "/", extract_dir)
            self.assertIn("Failed to open tar", str(ctx.exception))

    def test_space_in_name_accepted_and_quoted(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            info = tarfile.TarInfo(name="Dell Inc.,XPS 13 9300.yaml")
            info.size = 0
            info.mode = 0o644
            info.uid = 0
            info.gid = 0
            tar_path = self._make_tar(tmpdir, [info])
            extract_dir = os.path.join(tmpdir, "extract")
            os.makedirs(extract_dir)
            commands = _tar_to_debugfs_commands(tar_path, "/", extract_dir)
            self.assertIn('rm "/Dell Inc.,XPS 13 9300.yaml"', commands)
            self.assertTrue(
                any(
                    c.startswith("write ")
                    and c.endswith(' "/Dell Inc.,XPS 13 9300.yaml"')
                    for c in commands
                )
            )


class TestExtractPartition(unittest.TestCase):
    @patch("lava_dispatcher.utils.ext4.subprocess.run")
    def test_success(self, mock_run):
        sfdisk_output = json.dumps(
            {
                "partitiontable": {
                    "sectorsize": 512,
                    "partitions": [
                        {"start": 2048, "size": 1048576},
                        {"start": 1050624, "size": 2097152},
                    ],
                }
            }
        )
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout=sfdisk_output, stderr=""),
            MagicMock(returncode=0),
        ]
        part_file, start, sector_size = extract_partition(
            "/tmp/disk.img", 0, "/tmp/work"
        )
        self.assertEqual(part_file, "/tmp/work/partition.img")
        self.assertEqual(start, 2048)
        self.assertEqual(sector_size, 512)

    @patch("lava_dispatcher.utils.ext4.subprocess.run")
    def test_invalid_partition_index(self, mock_run):
        sfdisk_output = json.dumps(
            {
                "partitiontable": {
                    "sectorsize": 512,
                    "partitions": [{"start": 2048, "size": 1048576}],
                }
            }
        )
        mock_run.return_value = MagicMock(returncode=0, stdout=sfdisk_output, stderr="")
        with self.assertRaises(JobError) as ctx:
            extract_partition("/tmp/disk.img", 5, "/tmp/work")
        self.assertIn("Invalid partition number", str(ctx.exception))

    @patch("lava_dispatcher.utils.ext4.subprocess.run")
    def test_sfdisk_failure(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=1, stdout="", stderr="not a disk image"
        )
        with self.assertRaises(JobError) as ctx:
            extract_partition("/tmp/disk.img", 0, "/tmp/work")
        self.assertIn("sfdisk failed", str(ctx.exception))

    @patch("lava_dispatcher.utils.ext4.subprocess.run")
    def test_dd_failure(self, mock_run):
        sfdisk_output = json.dumps(
            {
                "partitiontable": {
                    "sectorsize": 512,
                    "partitions": [{"start": 2048, "size": 1048576}],
                }
            }
        )
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout=sfdisk_output, stderr=""),
            subprocess.CalledProcessError(1, "dd", stderr=b"write error"),
        ]
        with self.assertRaises(InfrastructureError) as ctx:
            extract_partition("/tmp/disk.img", 0, "/tmp/work")
        self.assertIn("Failed to extract partition", str(ctx.exception))


class TestWritePartitionBack(unittest.TestCase):
    @patch("lava_dispatcher.utils.ext4.subprocess.run")
    def test_success(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        write_partition_back("/tmp/disk.img", "/tmp/part.img", 2048, 512)
        args = mock_run.call_args[0][0]
        self.assertIn("if=/tmp/part.img", args)
        self.assertIn("of=/tmp/disk.img", args)
        self.assertIn("seek=2048", args)

    @patch("lava_dispatcher.utils.ext4.subprocess.run")
    def test_dd_failure(self, mock_run):
        mock_run.side_effect = subprocess.CalledProcessError(
            1, "dd", stderr=b"no space"
        )
        with self.assertRaises(InfrastructureError) as ctx:
            write_partition_back("/tmp/disk.img", "/tmp/part.img", 2048, 512)
        self.assertIn("Failed to write partition", str(ctx.exception))


class TestInjectTar(unittest.TestCase):
    @patch("lava_dispatcher.utils.ext4._run_debugfs")
    @patch("lava_dispatcher.utils.ext4._tar_to_debugfs_commands")
    def test_calls_debugfs(self, mock_cmds, mock_run):
        mock_cmds.return_value = ["mkdir /foo"]
        inject_tar("/tmp/image.ext4", "/tmp/overlay.tar", "/")
        mock_cmds.assert_called_once()
        mock_run.assert_called_once()
        self.assertEqual(mock_run.call_args[0][0], "/tmp/image.ext4")
        self.assertEqual(mock_run.call_args[0][1], ["mkdir /foo"])

    @patch("lava_dispatcher.utils.ext4._run_debugfs")
    @patch("lava_dispatcher.utils.ext4._tar_to_debugfs_commands")
    def test_empty_commands_skips_debugfs(self, mock_cmds, mock_run):
        mock_cmds.return_value = []
        inject_tar("/tmp/image.ext4", "/tmp/overlay.tar", "/")
        mock_run.assert_not_called()

    @patch("lava_dispatcher.utils.ext4._run_debugfs")
    @patch("lava_dispatcher.utils.ext4._tar_to_debugfs_commands")
    def test_large_tar_uses_batched_sessions(self, mock_cmds, mock_run):
        mock_cmds.return_value = [
            "mkdir /d%d" % i for i in range(DEBUGFS_BATCH_SIZE * 3 + 5)
        ]
        inject_tar("/tmp/image.ext4", "/tmp/overlay.tar", "/")
        self.assertEqual(mock_run.call_count, 4)

    @patch("lava_dispatcher.utils.ext4._run_debugfs")
    @patch("lava_dispatcher.utils.ext4._ext4_free_bytes", return_value=100 * 4096)
    @patch("lava_dispatcher.utils.ext4._tar_payload_bytes", return_value=500 * 4096)
    def test_preflight_rejects_insufficient_space(
        self, mock_payload, mock_free, mock_run
    ):
        with self.assertRaises(JobError) as ctx:
            inject_tar("/tmp/image.ext4", "/tmp/overlay.tar", "/")
        self.assertIn("Not enough free space", str(ctx.exception))
        mock_run.assert_not_called()

    @patch("lava_dispatcher.utils.ext4._run_debugfs")
    @patch("lava_dispatcher.utils.ext4._tar_to_debugfs_commands")
    @patch("lava_dispatcher.utils.ext4._ext4_free_bytes", return_value=None)
    def test_preflight_tolerates_missing_free_bytes(
        self, mock_free, mock_cmds, mock_run
    ):
        mock_cmds.return_value = ["mkdir /foo"]
        inject_tar("/tmp/image.ext4", "/tmp/overlay.tar", "/")
        mock_run.assert_called_once()

    @patch("lava_dispatcher.utils.ext4._run_debugfs")
    @patch("lava_dispatcher.utils.ext4._tar_to_debugfs_commands")
    @patch("lava_dispatcher.utils.compression.decompress_file")
    @patch("os.path.exists", return_value=False)
    @patch("os.unlink")
    def test_gzip_decompression(
        self, mock_unlink, mock_exists, mock_decompress, mock_cmds, mock_run
    ):
        mock_decompress.return_value = "/tmp/overlay.tar"
        mock_cmds.return_value = ["mkdir /foo"]
        inject_tar("/tmp/image.ext4", "/tmp/overlay.tar.gz", "/", compress="gzip")
        mock_decompress.assert_called_once_with("/tmp/overlay.tar.gz", "gz")

    def test_unsupported_compression(self):
        with self.assertRaises(JobError) as ctx:
            inject_tar("/tmp/image.ext4", "/tmp/overlay.tar.bz2", "/", compress="bzip2")
        self.assertIn("unsupported compression", str(ctx.exception))


class TestInjectFile(unittest.TestCase):
    @patch("lava_dispatcher.utils.ext4._run_debugfs")
    def test_calls_debugfs(self, mock_run):
        inject_file("/tmp/image.ext4", "/tmp/src.bin", "/boot/vmlinuz")
        commands = mock_run.call_args[0][1]
        self.assertIn('mkdir "/boot"', commands)
        self.assertIn('rm "/boot/vmlinuz"', commands)
        self.assertIn('write "/tmp/src.bin" "/boot/vmlinuz"', commands)


class TestCopyOut(unittest.TestCase):
    @patch("lava_dispatcher.utils.ext4.subprocess.run")
    def test_calls_debugfs_dump(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        copy_out("/tmp/image.ext4", ["/boot/vmlinuz", "/boot/initrd"], "/tmp/dest")
        self.assertEqual(mock_run.call_count, 2)
        first_call = mock_run.call_args_list[0]
        self.assertEqual(first_call[0][0][0], "debugfs")
        self.assertIn('dump "/boot/vmlinuz" "/tmp/dest/vmlinuz"', first_call[0][0][2])

    @patch("lava_dispatcher.utils.ext4.subprocess.run")
    def test_error_raises_job_error(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=1, stderr="dump: File not found by ext2_lookup\n"
        )
        with self.assertRaises(JobError):
            copy_out("/tmp/image.ext4", ["/missing"], "/tmp/dest")

    @patch("lava_dispatcher.utils.ext4.subprocess.run")
    def test_filename_with_error_not_flagged(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stderr="dumped /lib/modules/x/error.ko\n",
        )
        copy_out("/tmp/image.ext4", ["/lib/modules/x/error.ko"], "/tmp/dest")


class TestCopyOutIso(unittest.TestCase):
    @patch("os.path.exists", return_value=False)
    @patch("lava_dispatcher.utils.ext4.subprocess.run")
    def test_calls_bsdtar(self, mock_run, mock_exists):
        mock_run.return_value = MagicMock(returncode=0)
        copy_out_iso("/tmp/image.iso", ["/install/vmlinuz"], "/tmp/dest")
        args = mock_run.call_args[0][0]
        self.assertEqual(args[0], "bsdtar")
        self.assertIn("-xf", args)

    @patch("lava_dispatcher.utils.ext4.subprocess.run")
    def test_bsdtar_not_found(self, mock_run):
        mock_run.side_effect = FileNotFoundError()
        with self.assertRaises(InfrastructureError) as ctx:
            copy_out_iso("/tmp/image.iso", ["/install/vmlinuz"], "/tmp/dest")
        self.assertIn("bsdtar not found", str(ctx.exception))

    @patch("lava_dispatcher.utils.ext4.subprocess.run")
    def test_bsdtar_failure(self, mock_run):
        mock_run.side_effect = subprocess.CalledProcessError(
            1, "bsdtar", stderr=b"file not found"
        )
        with self.assertRaises(JobError) as ctx:
            copy_out_iso("/tmp/image.iso", ["/install/vmlinuz"], "/tmp/dest")
        self.assertIn("Failed to extract", str(ctx.exception))


class TestCreateExt4(unittest.TestCase):
    @patch("lava_dispatcher.utils.ext4.subprocess.run")
    def test_creates_and_returns_uuid(self, mock_run):
        mock_run.side_effect = [
            MagicMock(returncode=0),
            MagicMock(returncode=0),
            MagicMock(returncode=0, stdout="abc-123\n"),
        ]
        uuid = create_ext4("/tmp/test.ext4", 256)
        self.assertEqual(uuid, "abc-123")
        self.assertEqual(mock_run.call_count, 3)
        truncate_call = mock_run.call_args_list[0]
        self.assertEqual(
            truncate_call[0][0], ["truncate", "-s", "256M", "/tmp/test.ext4"]
        )
        mkfs_call = mock_run.call_args_list[1]
        self.assertEqual(
            mkfs_call[0][0],
            ["mkfs.ext4", "-q", "-L", "LAVA", "-F", "/tmp/test.ext4"],
        )

    @patch("lava_dispatcher.utils.ext4.subprocess.run")
    def test_mkfs_failure(self, mock_run):
        mock_run.side_effect = [
            MagicMock(returncode=0),
            subprocess.CalledProcessError(1, "mkfs.ext4", stderr=b"failed"),
        ]
        with self.assertRaises(InfrastructureError) as ctx:
            create_ext4("/tmp/test.ext4", 256)
        self.assertIn("Failed to create ext4", str(ctx.exception))
