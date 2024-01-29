# Copyright (C) 2020 Linaro Limited
#
# Author: Rémi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

from unittest.mock import MagicMock
from unittest.mock import call as mock_call
from unittest.mock import patch

from lava_common.exceptions import JobError
from lava_dispatcher.actions.deploy.apply_overlay import AppendOverlays

from ...test_basic import LavaDispatcherTestCase


class TestApplyOverlay(LavaDispatcherTestCase):
    def test_append_overlays_validate(self):
        # 1/ Working setup
        params = {
            "format": "cpio.newc",
            "overlays": {
                "modules": {
                    "url": "http://example.com/modules.tar.xz",
                    "compression": "xz",
                    "format": "tar",
                    "path": "/",
                }
            },
        }
        action = AppendOverlays("rootfs", params)
        action.validate()

        # 2/ Check errors
        with self.assertRaisesRegex(JobError, "Unsupported image format None"):
            del params["format"]
            action.validate()

        with self.assertRaisesRegex(JobError, "Invalid 'path': '../../'"):
            params["overlays"]["modules"]["path"] = "../../"
            action.validate()

        with self.assertRaisesRegex(JobError, "Missing 'path' for 'overlays.modules'"):
            del params["overlays"]["modules"]["path"]
            action.validate()

        with self.assertRaisesRegex(
            JobError, "Invalid 'format' \\('git'\\) for 'overlays.modules'"
        ):
            params["overlays"]["modules"]["format"] = "git"
            action.validate()

        with self.assertRaisesRegex(JobError, "'overlays' is not a dictionary"):
            params["overlays"] = ""
            action.validate()

        with self.assertRaisesRegex(JobError, "Missing 'overlays' dictionary"):
            del params["overlays"]
            action.validate()

    def test_append_overlays_validate_sparse(self):
        params = {
            "format": "cpio.newc",
            "overlays": {
                "modules": {
                    "url": "http://example.com/modules.tar.xz",
                    "compression": "xz",
                    "format": "tar",
                    "path": "/",
                }
            },
        }

        action = AppendOverlays("rootfs", params)
        action.validate()
        with self.assertRaisesRegex(
            JobError, "sparse=True is only available for ext4 images"
        ):
            params["sparse"] = True
            action.validate()

    def test_append_overlays_run(self):
        params = {
            "format": "cpio.newc",
            "overlays": {
                "modules": {
                    "url": "http://example.com/modules.tar.xz",
                    "compression": "xz",
                    "format": "tar",
                    "path": "/",
                }
            },
        }
        action = AppendOverlays("rootfs", params)
        action.update_cpio = MagicMock()
        action.update_guestfs = MagicMock()
        action.update_tar = MagicMock()
        self.assertIsNone(action.run(None, 0))
        action.update_cpio.assert_called_once_with()

        params["format"] = "ext4"
        self.assertIsNone(action.run(None, 0))
        action.update_guestfs.assert_called_once_with()

        params["format"] = "tar"
        self.assertIsNone(action.run(None, 0))
        action.update_tar.assert_called_once_with()

    def test_append_overlays_update_cpio(self):
        job = self.create_simple_job()
        tmp_dir_path = self.create_temporary_directory()

        params = {
            "format": "cpio.newc",
            "overlays": {
                "modules": {
                    "url": "http://example.com/modules.tar.xz",
                    "compression": "xz",
                    "format": "tar",
                    "path": "/",
                }
            },
        }

        action = AppendOverlays("rootfs", params)
        action.job = job
        action.parameters = {
            "rootfs": {"url": "http://example.com/rootfs.cpio.gz", **params},
            "namespace": "common",
        }
        action.data = {
            "common": {
                "download-action": {
                    "rootfs": {
                        "file": str(tmp_dir_path / "rootfs.cpio.gz"),
                        "compression": "gz",
                        "decompressed": False,
                    },
                    "rootfs.modules": {"file": str(tmp_dir_path / "modules.tar")},
                }
            }
        }
        action.mkdtemp = MagicMock(return_value=str(tmp_dir_path))

        with patch(
            "lava_dispatcher.actions.deploy.apply_overlay.decompress_file"
        ) as decompress_file_mock, patch(
            "lava_dispatcher.actions.deploy.apply_overlay.uncpio"
        ) as uncpio_mock, patch(
            "os.unlink"
        ) as unlink_mock, patch(
            "lava_dispatcher.actions.deploy.apply_overlay.untar_file"
        ) as untar_file_mock, patch(
            "lava_dispatcher.actions.deploy.apply_overlay.cpio"
        ) as cpio_mock, patch(
            "lava_dispatcher.actions.deploy.apply_overlay.compress_file"
        ) as compress_file_mock, self.assertLogs(
            action.logger, level="DEBUG"
        ) as action_logs:
            action.update_cpio()

        decompress_file_mock.assert_called_once_with(
            str(tmp_dir_path / "rootfs.cpio.gz"), "gz"
        )
        uncpio_mock.assert_called_once_with(decompress_file_mock(), str(tmp_dir_path))
        unlink_mock.assert_called_once_with(decompress_file_mock())
        untar_file_mock.assert_called_once_with(
            str(tmp_dir_path / "modules.tar"), str(tmp_dir_path) + "/"
        )
        cpio_mock.assert_called_once_with(str(tmp_dir_path), decompress_file_mock())
        compress_file_mock.assert_called_once_with(decompress_file_mock(), "gz")

        self.assertEqual(
            [(r.name, r.levelno, r.message) for r in action_logs.records],
            [
                ("dispatcher", 20, f"Modifying '{tmp_dir_path}/rootfs.cpio.gz'"),
                ("dispatcher", 10, "* decompressing (gz)"),
                ("dispatcher", 10, f"* extracting {decompress_file_mock()}"),
                ("dispatcher", 10, "Overlays:"),
                (
                    "dispatcher",
                    10,
                    (
                        f"- rootfs.modules: untar '{tmp_dir_path}"
                        f"/modules.tar' to '{tmp_dir_path}/'"
                    ),
                ),
                ("dispatcher", 10, f"* archiving {decompress_file_mock()}"),
                ("dispatcher", 10, "* compressing (gz)"),
            ],
        )

    def test_append_overlays_update_guestfs(self):
        job = self.create_simple_job()
        tmp_dir_path = self.create_temporary_directory()

        params = {
            "format": "ext4",
            "overlays": {
                "modules": {
                    "url": "http://example.com/modules.tar.xz",
                    "compression": "xz",
                    "format": "tar",
                    "path": "/lib",
                }
            },
        }

        action = AppendOverlays("rootfs", params)
        action.job = job
        action.parameters = {
            "rootfs": {"url": "http://example.com/rootff.ext4", **params},
            "namespace": "common",
        }
        action.data = {
            "common": {
                "download-action": {
                    "rootfs": {
                        "file": str(tmp_dir_path / "rootfs.ext4"),
                        "compression": "gz",
                        "decompressed": True,
                    },
                    "rootfs.modules": {"file": str(tmp_dir_path / "modules.tar")},
                }
            }
        }

        with patch(
            "lava_dispatcher.actions.deploy.apply_overlay.guestfs.GuestFS"
        ) as guestfs_mock, self.assertLogs(action.logger, level="DEBUG") as action_logs:
            action.update_guestfs()

        guestfs_mock.assert_called_once_with(python_return_dict=True)
        guestfs_mock().launch.assert_called_once_with()
        guestfs_mock().list_devices.assert_called_once_with()
        guestfs_mock().add_drive.assert_called_once_with(
            str(tmp_dir_path / "rootfs.ext4")
        )
        guestfs_mock().mount.assert_called_once_with(
            guestfs_mock().list_devices()[0], "/"
        )
        guestfs_mock().mkdir_p.assert_called_once_with("/lib")
        guestfs_mock().tar_in.assert_called_once_with(
            str(tmp_dir_path / "modules.tar"), "/lib", compress=None
        )
        self.assertEqual(
            [(r.name, r.levelno, r.message) for r in action_logs.records],
            [
                ("dispatcher", 20, f"Modifying '{tmp_dir_path}/rootfs.ext4'"),
                ("dispatcher", 10, "Overlays:"),
                (
                    "dispatcher",
                    10,
                    f"- rootfs.modules: '{tmp_dir_path}/modules.tar' to '/lib'",
                ),
            ],
        )

    def test_append_lava_overlay_update_tar(self):
        job = self.create_simple_job()
        tmp_dir_path = self.create_temporary_directory()

        params = {
            "format": "tar",
            "overlays": {
                "modules": {
                    "url": "http://example.com/modules.tar.xz",
                    "compression": "xz",
                    "format": "tar",
                    "path": "/",
                }
            },
        }

        action = AppendOverlays("nfsrootfs", params)
        action.job = job
        action.parameters = {
            "nfsrootfs": {"url": "http://example.com/rootfs.tar.gz", **params},
            "namespace": "common",
        }
        action.data = {
            "common": {
                "download-action": {
                    "nfsrootfs": {
                        "file": str(tmp_dir_path / "rootfs.tar.gz"),
                        "compression": "gz",
                        "decompressed": False,
                    },
                    "nfsrootfs.modules": {"file": str(tmp_dir_path / "modules.tar")},
                },
            }
        }
        action.mkdtemp = MagicMock(return_value=str(tmp_dir_path))

        with patch(
            "lava_dispatcher.actions.deploy.apply_overlay.decompress_file"
        ) as decompress_file_mock, patch(
            "lava_dispatcher.actions.deploy.apply_overlay.untar_file"
        ) as untar_file_mock, patch(
            "os.unlink"
        ) as unlink_mock, patch(
            "lava_dispatcher.actions.deploy.apply_overlay.create_tarfile"
        ) as create_tarfile_mock, patch(
            "lava_dispatcher.actions.deploy.apply_overlay.compress_file"
        ) as compress_file_mock, self.assertLogs(
            action.logger, level="DEBUG"
        ) as action_logs:
            action.update_tar()

        decompress_file_mock.assert_called_once_with(
            str(tmp_dir_path / "rootfs.tar.gz"), "gz"
        )
        self.assertEqual(
            untar_file_mock.mock_calls,
            [
                mock_call(decompress_file_mock(), str(tmp_dir_path)),
                mock_call(str(tmp_dir_path / "modules.tar"), str(tmp_dir_path) + "/"),
            ],
        )
        unlink_mock.assert_called_once_with(decompress_file_mock())

        create_tarfile_mock.assert_called_once_with(
            str(tmp_dir_path), decompress_file_mock(), arcname="."
        )
        compress_file_mock.assert_called_once_with(decompress_file_mock(), "gz")

        self.assertEqual(
            [(r.name, r.levelno, r.message) for r in action_logs.records],
            [
                ("dispatcher", 20, f"Modifying '{tmp_dir_path}/rootfs.tar.gz'"),
                ("dispatcher", 10, "* decompressing (gz)"),
                ("dispatcher", 10, f"* extracting {decompress_file_mock()}"),
                ("dispatcher", 10, "Overlays:"),
                (
                    "dispatcher",
                    10,
                    (
                        f"- nfsrootfs.modules: untar '{tmp_dir_path}"
                        f"/modules.tar' to '{tmp_dir_path}/'"
                    ),
                ),
                ("dispatcher", 10, f"* archiving {decompress_file_mock()}"),
                ("dispatcher", 10, "* compressing (gz)"),
            ],
        )

    def test_append_overlays_update_guestfs_sparse(self):
        job = self.create_simple_job()
        tmp_dir_path = self.create_temporary_directory()

        params = {
            "format": "ext4",
            "sparse": True,
            "overlays": {
                "modules": {
                    "url": "http://example.com/modules.tar.xz",
                    "compression": "xz",
                    "format": "tar",
                    "path": "/lib",
                }
            },
        }

        action = AppendOverlays("rootfs", params)
        action.job = job
        action.parameters = {
            "rootfs": {"url": "http://example.com/rootff.ext4", **params},
            "namespace": "common",
        }
        action.data = {
            "common": {
                "download-action": {
                    "rootfs": {
                        "file": str(tmp_dir_path / "rootfs.ext4"),
                        "compression": "gz",
                        "decompressed": True,
                    },
                    "rootfs.modules": {"file": str(tmp_dir_path / "modules.tar")},
                }
            }
        }
        action.run_cmd = MagicMock()

        with patch(
            "lava_dispatcher.actions.deploy.apply_overlay.guestfs.GuestFS"
        ) as guestfs_mock, patch(
            "lava_dispatcher.actions.deploy.apply_overlay.os.replace"
        ) as replace_mock, self.assertLogs(
            action.logger, level="DEBUG"
        ) as action_logs:
            action.update_guestfs()

        guestfs_mock.assert_called_once_with(python_return_dict=True)
        guestfs_mock().launch.assert_called_once_with()
        guestfs_mock().list_devices.assert_called_once_with()
        guestfs_mock().add_drive.assert_called_once_with(
            str(tmp_dir_path / "rootfs.ext4")
        )
        guestfs_mock().mount.assert_called_once_with(
            guestfs_mock().list_devices()[0], "/"
        )
        guestfs_mock().mkdir_p.assert_called_once_with("/lib")
        guestfs_mock().tar_in.assert_called_once_with(
            str(tmp_dir_path / "modules.tar"), "/lib", compress=None
        )
        self.assertEqual(
            action.run_cmd.mock_calls,
            [
                mock_call(
                    [
                        "/usr/bin/simg2img",
                        f"{tmp_dir_path}/rootfs.ext4",
                        f"{tmp_dir_path}/rootfs.ext4.non-sparse",
                    ],
                    error_msg=f"simg2img failed for {tmp_dir_path}/rootfs.ext4",
                ),
                mock_call(
                    [
                        "/usr/bin/img2simg",
                        f"{tmp_dir_path}/rootfs.ext4",
                        f"{tmp_dir_path}/rootfs.ext4.sparse",
                    ],
                    error_msg=f"img2simg failed for {tmp_dir_path}/rootfs.ext4",
                ),
            ],
        )
        self.assertEqual(
            replace_mock.mock_calls,
            [
                mock_call(
                    f"{tmp_dir_path}/rootfs.ext4.non-sparse",
                    f"{tmp_dir_path}/rootfs.ext4",
                ),
                mock_call(
                    f"{tmp_dir_path}/rootfs.ext4.sparse", f"{tmp_dir_path}/rootfs.ext4"
                ),
            ],
        )

        self.assertEqual(
            [(r.name, r.levelno, r.message) for r in action_logs.records],
            [
                ("dispatcher", 20, f"Modifying '{tmp_dir_path}/rootfs.ext4'"),
                ("dispatcher", 10, f"Calling simg2img on '{tmp_dir_path}/rootfs.ext4'"),
                ("dispatcher", 10, "Overlays:"),
                (
                    "dispatcher",
                    10,
                    f"- rootfs.modules: '{tmp_dir_path}/modules.tar' to '/lib'",
                ),
                ("dispatcher", 10, f"Calling img2simg on '{tmp_dir_path}/rootfs.ext4'"),
            ],
        )

    def test_append_lava_overlay_update_cpio(self):
        job = self.create_simple_job()
        tmp_dir_path = self.create_temporary_directory()

        params = {"format": "cpio.newc", "overlays": {"lava": True}}

        action = AppendOverlays("rootfs", params)
        action.job = job
        action.parameters = {
            "rootfs": {"url": "http://example.com/rootfs.cpio.gz", **params},
            "namespace": "common",
        }
        action.data = {
            "common": {
                "compress-overlay": {
                    "output": {"file": str(tmp_dir_path / "overlay.tar.gz")}
                },
                "download-action": {
                    "rootfs": {
                        "file": str(tmp_dir_path / "rootfs.cpio.gz"),
                        "compression": "gz",
                        "decompressed": False,
                    }
                },
            }
        }
        action.mkdtemp = MagicMock(return_value=str(tmp_dir_path))
        with patch(
            "lava_dispatcher.actions.deploy.apply_overlay.decompress_file"
        ) as decompress_file_mock, patch(
            "lava_dispatcher.actions.deploy.apply_overlay.uncpio"
        ) as uncpio_mock, patch(
            "os.unlink"
        ) as unlick_mock, patch(
            "lava_dispatcher.actions.deploy.apply_overlay.untar_file"
        ) as untar_file_mock, patch(
            "lava_dispatcher.actions.deploy.apply_overlay.cpio"
        ) as cpio_mock, patch(
            "lava_dispatcher.actions.deploy.apply_overlay.compress_file"
        ) as compress_file_mock, self.assertLogs(
            action.logger, level="DEBUG"
        ) as action_logs:
            action.update_cpio()

        decompress_file_mock.assert_called_once_with(
            str(tmp_dir_path / "rootfs.cpio.gz"), "gz"
        )
        uncpio_mock.assert_called_once_with(decompress_file_mock(), str(tmp_dir_path))
        unlick_mock.assert_called_once_with(decompress_file_mock())
        untar_file_mock.assert_called_once_with(
            str(tmp_dir_path / "overlay.tar.gz"), str(tmp_dir_path) + "/"
        )
        cpio_mock.assert_called_once_with(str(tmp_dir_path), decompress_file_mock())
        compress_file_mock.assert_called_once_with(decompress_file_mock(), "gz")

        self.assertEqual(
            [(r.name, r.levelno, r.message) for r in action_logs.records],
            [
                ("dispatcher", 20, f"Modifying '{tmp_dir_path}/rootfs.cpio.gz'"),
                ("dispatcher", 10, "* decompressing (gz)"),
                ("dispatcher", 10, f"* extracting {decompress_file_mock()}"),
                ("dispatcher", 10, "Overlays:"),
                (
                    "dispatcher",
                    10,
                    (
                        f"- rootfs.lava: untar '{tmp_dir_path}"
                        f"/overlay.tar.gz' to '{tmp_dir_path}/'"
                    ),
                ),
                ("dispatcher", 10, f"* archiving {decompress_file_mock()}"),
                ("dispatcher", 10, "* compressing (gz)"),
            ],
        )

    def test_append_lava_overlay_update_guestfs(self):
        job = self.create_simple_job()
        tmp_dir_path = self.create_temporary_directory()

        params = {"format": "ext4", "overlays": {"lava": True}}

        action = AppendOverlays("rootfs", params)
        action.job = job
        action.parameters = {
            "rootfs": {"url": "http://example.com/rootff.ext4", **params},
            "namespace": "common",
        }
        action.data = {
            "common": {
                "compress-overlay": {
                    "output": {"file": str(tmp_dir_path / "overlay.tar.gz")}
                },
                "download-action": {
                    "rootfs": {
                        "file": str(tmp_dir_path / "rootfs.ext4"),
                        "compression": "gz",
                        "decompressed": True,
                    }
                },
            }
        }

        with patch(
            "lava_dispatcher.actions.deploy.apply_overlay.guestfs.GuestFS"
        ) as guestfs_mock, self.assertLogs(action.logger, level="DEBUG") as action_logs:
            action.update_guestfs()

        guestfs_mock.assert_called_once_with(python_return_dict=True)
        guestfs_mock().launch.assert_called_once_with()
        guestfs_mock().list_devices.assert_called_once_with()
        guestfs_mock().add_drive.assert_called_once_with(
            str(tmp_dir_path / "rootfs.ext4")
        )
        guestfs_mock().mount.assert_called_once_with(
            guestfs_mock().list_devices()[0], "/"
        )
        guestfs_mock().mkdir_p.assert_called_once_with("/")
        guestfs_mock().tar_in.assert_called_once_with(
            str(tmp_dir_path / "overlay.tar.gz"), "/", compress="gzip"
        )
        self.assertEqual(
            [(r.name, r.levelno, r.message) for r in action_logs.records],
            [
                ("dispatcher", 20, f"Modifying '{tmp_dir_path}/rootfs.ext4'"),
                ("dispatcher", 10, "Overlays:"),
                (
                    "dispatcher",
                    10,
                    f"- rootfs.lava: '{tmp_dir_path}/overlay.tar.gz' to '/'",
                ),
            ],
        )
