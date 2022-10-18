import logging
import pytest

from lava_common.exceptions import JobError, LAVABug
from lava_dispatcher.actions.deploy.apply_overlay import AppendOverlays
from lava_dispatcher.job import Job


def test_append_overlays_validate():
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
    with pytest.raises(JobError) as exc:
        del params["format"]
        action.validate()
    assert exc.match("Unsupported image format None")

    with pytest.raises(JobError) as exc:
        params["overlays"]["modules"]["path"] = "../../"
        action.validate()
    assert exc.match("Invalid 'path': '../../'")

    with pytest.raises(JobError) as exc:
        del params["overlays"]["modules"]["path"]
        action.validate()
    assert exc.match("Missing 'path' for 'overlays.modules'")

    with pytest.raises(JobError) as exc:
        params["overlays"]["modules"]["format"] = "git"
        action.validate()
    assert exc.match("Invalid 'format' \\('git'\\) for 'overlays.modules'")

    with pytest.raises(JobError) as exc:
        params["overlays"] = ""
        action.validate()
    assert exc.match("'overlays' is not a dictionary")

    with pytest.raises(JobError) as exc:
        del params["overlays"]
        action.validate()
    assert exc.match("Missing 'overlays' dictionary")

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
    with pytest.raises(JobError) as exc:
        params["sparse"] = True
        action.validate()
    assert exc.match("sparse=True is only available for ext4 images")


def test_append_overlays_run(mocker):
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
    action.update_cpio = mocker.stub()
    action.update_guestfs = mocker.stub()
    action.update_tar = mocker.stub()
    assert action.run(None, 0) is None
    action.update_cpio.assert_called_once_with()

    params["format"] = "ext4"
    assert action.run(None, 0) is None
    action.update_guestfs.assert_called_once_with()

    params["format"] = "tar"
    assert action.run(None, 0) is None
    action.update_tar.assert_called_once_with()


def test_append_overlays_update_cpio(caplog, mocker, tmpdir):
    caplog.set_level(logging.DEBUG)
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
    action.job = Job(1234, {}, None)
    action.parameters = {
        "rootfs": {"url": "http://example.com/rootfs.cpio.gz", **params},
        "namespace": "common",
    }
    action.data = {
        "common": {
            "download-action": {
                "rootfs": {
                    "file": str(tmpdir / "rootfs.cpio.gz"),
                    "compression": "gz",
                    "decompressed": False,
                },
                "rootfs.modules": {"file": str(tmpdir / "modules.tar")},
            }
        }
    }
    action.mkdtemp = lambda: str(tmpdir)
    decompress_file = mocker.patch(
        "lava_dispatcher.actions.deploy.apply_overlay.decompress_file"
    )
    uncpio = mocker.patch("lava_dispatcher.actions.deploy.apply_overlay.uncpio")
    unlink = mocker.patch("os.unlink")
    untar_file = mocker.patch("lava_dispatcher.actions.deploy.apply_overlay.untar_file")
    cpio = mocker.patch("lava_dispatcher.actions.deploy.apply_overlay.cpio")
    compress_file = mocker.patch(
        "lava_dispatcher.actions.deploy.apply_overlay.compress_file"
    )

    action.update_cpio()

    decompress_file.assert_called_once_with(str(tmpdir / "rootfs.cpio.gz"), "gz")
    uncpio.assert_called_once_with(decompress_file(), str(tmpdir))
    unlink.assert_called_once_with(decompress_file())
    untar_file.assert_called_once_with(str(tmpdir / "modules.tar"), str(tmpdir) + "/")
    cpio.assert_called_once_with(str(tmpdir), decompress_file())
    compress_file.assert_called_once_with(decompress_file(), "gz")

    assert caplog.record_tuples == [
        ("dispatcher", 20, f"Modifying '{tmpdir}/rootfs.cpio.gz'"),
        ("dispatcher", 10, "* decompressing (gz)"),
        ("dispatcher", 10, f"* extracting {decompress_file()}"),
        ("dispatcher", 10, "Overlays:"),
        (
            "dispatcher",
            10,
            f"- rootfs.modules: untar '{tmpdir}/modules.tar' to '{tmpdir}/'",
        ),
        ("dispatcher", 10, f"* archiving {decompress_file()}"),
        ("dispatcher", 10, "* compressing (gz)"),
    ]


def test_append_overlays_update_guestfs(caplog, mocker, tmpdir):
    caplog.set_level(logging.DEBUG)
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
    action.job = Job(1234, {}, None)
    action.parameters = {
        "rootfs": {"url": "http://example.com/rootff.ext4", **params},
        "namespace": "common",
    }
    action.data = {
        "common": {
            "download-action": {
                "rootfs": {
                    "file": str(tmpdir / "rootfs.ext4"),
                    "compression": "gz",
                    "decompressed": True,
                },
                "rootfs.modules": {"file": str(tmpdir / "modules.tar")},
            }
        }
    }

    guestfs = mocker.MagicMock()
    guestfs.add_drive = mocker.MagicMock()
    mocker.patch(
        "lava_dispatcher.actions.deploy.apply_overlay.guestfs.GuestFS", guestfs
    )
    action.update_guestfs()

    guestfs.assert_called_once_with(python_return_dict=True)
    guestfs().launch.assert_called_once_with()
    guestfs().list_devices.assert_called_once_with()
    guestfs().add_drive.assert_called_once_with(str(tmpdir / "rootfs.ext4"))
    guestfs().mount.assert_called_once_with(guestfs().list_devices()[0], "/")
    guestfs().mkdir_p.assert_called_once_with("/lib")
    guestfs().tar_in.assert_called_once_with(
        str(tmpdir / "modules.tar"), "/lib", compress=None
    )
    assert caplog.record_tuples == [
        ("dispatcher", 20, f"Modifying '{tmpdir}/rootfs.ext4'"),
        ("dispatcher", 10, "Overlays:"),
        ("dispatcher", 10, f"- rootfs.modules: '{tmpdir}/modules.tar' to '/lib'"),
    ]


def test_append_lava_overlay_update_tar(caplog, mocker, tmpdir):
    caplog.set_level(logging.DEBUG)
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
    action.job = Job(1234, {}, None)
    action.parameters = {
        "nfsrootfs": {"url": "http://example.com/rootfs.tar.gz", **params},
        "namespace": "common",
    }
    action.data = {
        "common": {
            "download-action": {
                "nfsrootfs": {
                    "file": str(tmpdir / "rootfs.tar.gz"),
                    "compression": "gz",
                    "decompressed": False,
                },
                "nfsrootfs.modules": {"file": str(tmpdir / "modules.tar")},
            },
        }
    }
    action.mkdtemp = lambda: str(tmpdir)
    decompress_file = mocker.patch(
        "lava_dispatcher.actions.deploy.apply_overlay.decompress_file"
    )
    untar_file = mocker.patch("lava_dispatcher.actions.deploy.apply_overlay.untar_file")
    unlink = mocker.patch("os.unlink")
    create_tarfile = mocker.patch(
        "lava_dispatcher.actions.deploy.apply_overlay.create_tarfile"
    )
    compress_file = mocker.patch(
        "lava_dispatcher.actions.deploy.apply_overlay.compress_file"
    )

    action.update_tar()

    decompress_file.assert_called_once_with(str(tmpdir / "rootfs.tar.gz"), "gz")
    assert untar_file.mock_calls == [
        mocker.call(decompress_file(), str(tmpdir)),
        mocker.call(str(tmpdir / "modules.tar"), str(tmpdir) + "/"),
    ]
    unlink.assert_called_once_with(decompress_file())

    create_tarfile.assert_called_once_with(str(tmpdir), decompress_file())
    compress_file.assert_called_once_with(decompress_file(), "gz")

    assert caplog.record_tuples == [
        ("dispatcher", 20, f"Modifying '{tmpdir}/rootfs.tar.gz'"),
        ("dispatcher", 10, "* decompressing (gz)"),
        ("dispatcher", 10, f"* extracting {decompress_file()}"),
        ("dispatcher", 10, "Overlays:"),
        (
            "dispatcher",
            10,
            f"- nfsrootfs.modules: untar '{tmpdir}/modules.tar' to '{tmpdir}/'",
        ),
        ("dispatcher", 10, f"* archiving {decompress_file()}"),
        ("dispatcher", 10, "* compressing (gz)"),
    ]


def test_append_overlays_update_guestfs_sparse(caplog, mocker, tmpdir):
    caplog.set_level(logging.DEBUG)
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
    action.job = Job(1234, {}, None)
    action.parameters = {
        "rootfs": {"url": "http://example.com/rootff.ext4", **params},
        "namespace": "common",
    }
    action.data = {
        "common": {
            "download-action": {
                "rootfs": {
                    "file": str(tmpdir / "rootfs.ext4"),
                    "compression": "gz",
                    "decompressed": True,
                },
                "rootfs.modules": {"file": str(tmpdir / "modules.tar")},
            }
        }
    }
    action.run_cmd = mocker.MagicMock()
    replace = mocker.patch("lava_dispatcher.actions.deploy.apply_overlay.os.replace")

    guestfs = mocker.MagicMock()
    guestfs.add_drive = mocker.MagicMock()
    mocker.patch(
        "lava_dispatcher.actions.deploy.apply_overlay.guestfs.GuestFS", guestfs
    )
    action.update_guestfs()

    guestfs.assert_called_once_with(python_return_dict=True)
    guestfs().launch.assert_called_once_with()
    guestfs().list_devices.assert_called_once_with()
    guestfs().add_drive.assert_called_once_with(str(tmpdir / "rootfs.ext4"))
    guestfs().mount.assert_called_once_with(guestfs().list_devices()[0], "/")
    guestfs().mkdir_p.assert_called_once_with("/lib")
    guestfs().tar_in.assert_called_once_with(
        str(tmpdir / "modules.tar"), "/lib", compress=None
    )
    action.run_cmd.assert_called_once_with(
        ["/usr/bin/img2simg", f"{tmpdir}/rootfs.ext4", f"{tmpdir}/rootfs.ext4.sparse"],
        error_msg=f"img2simg failed for {tmpdir}/rootfs.ext4",
    )
    replace.assert_called_once_with(
        f"{tmpdir}/rootfs.ext4.sparse", f"{tmpdir}/rootfs.ext4"
    )

    assert caplog.record_tuples == [
        ("dispatcher", 20, f"Modifying '{tmpdir}/rootfs.ext4'"),
        ("dispatcher", 10, "Overlays:"),
        ("dispatcher", 10, f"- rootfs.modules: '{tmpdir}/modules.tar' to '/lib'"),
        ("dispatcher", 10, f"Calling img2simg on '{tmpdir}/rootfs.ext4'"),
    ]


def test_append_lava_overlay_update_cpio(caplog, mocker, tmpdir):
    caplog.set_level(logging.DEBUG)
    params = {"format": "cpio.newc", "overlays": {"lava": True}}

    action = AppendOverlays("rootfs", params)
    action.job = Job(1234, {}, None)
    action.parameters = {
        "rootfs": {"url": "http://example.com/rootfs.cpio.gz", **params},
        "namespace": "common",
    }
    action.data = {
        "common": {
            "compress-overlay": {"output": {"file": str(tmpdir / "overlay.tar.gz")}},
            "download-action": {
                "rootfs": {
                    "file": str(tmpdir / "rootfs.cpio.gz"),
                    "compression": "gz",
                    "decompressed": False,
                }
            },
        }
    }
    action.mkdtemp = lambda: str(tmpdir)
    decompress_file = mocker.patch(
        "lava_dispatcher.actions.deploy.apply_overlay.decompress_file"
    )
    uncpio = mocker.patch("lava_dispatcher.actions.deploy.apply_overlay.uncpio")
    unlink = mocker.patch("os.unlink")
    untar_file = mocker.patch("lava_dispatcher.actions.deploy.apply_overlay.untar_file")
    cpio = mocker.patch("lava_dispatcher.actions.deploy.apply_overlay.cpio")
    compress_file = mocker.patch(
        "lava_dispatcher.actions.deploy.apply_overlay.compress_file"
    )

    action.update_cpio()

    decompress_file.assert_called_once_with(str(tmpdir / "rootfs.cpio.gz"), "gz")
    uncpio.assert_called_once_with(decompress_file(), str(tmpdir))
    unlink.assert_called_once_with(decompress_file())
    untar_file.assert_called_once_with(
        str(tmpdir / "overlay.tar.gz"), str(tmpdir) + "/"
    )
    cpio.assert_called_once_with(str(tmpdir), decompress_file())
    compress_file.assert_called_once_with(decompress_file(), "gz")

    assert caplog.record_tuples == [
        ("dispatcher", 20, f"Modifying '{tmpdir}/rootfs.cpio.gz'"),
        ("dispatcher", 10, "* decompressing (gz)"),
        ("dispatcher", 10, f"* extracting {decompress_file()}"),
        ("dispatcher", 10, "Overlays:"),
        (
            "dispatcher",
            10,
            f"- rootfs.lava: untar '{tmpdir}/overlay.tar.gz' to '{tmpdir}/'",
        ),
        ("dispatcher", 10, f"* archiving {decompress_file()}"),
        ("dispatcher", 10, "* compressing (gz)"),
    ]


def test_append_lava_overlay_update_guestfs(caplog, mocker, tmpdir):
    caplog.set_level(logging.DEBUG)
    params = {"format": "ext4", "overlays": {"lava": True}}

    action = AppendOverlays("rootfs", params)
    action.job = Job(1234, {}, None)
    action.parameters = {
        "rootfs": {"url": "http://example.com/rootff.ext4", **params},
        "namespace": "common",
    }
    action.data = {
        "common": {
            "compress-overlay": {"output": {"file": str(tmpdir / "overlay.tar.gz")}},
            "download-action": {
                "rootfs": {
                    "file": str(tmpdir / "rootfs.ext4"),
                    "compression": "gz",
                    "decompressed": True,
                }
            },
        }
    }

    guestfs = mocker.MagicMock()
    guestfs.add_drive = mocker.MagicMock()
    mocker.patch(
        "lava_dispatcher.actions.deploy.apply_overlay.guestfs.GuestFS", guestfs
    )
    action.update_guestfs()

    guestfs.assert_called_once_with(python_return_dict=True)
    guestfs().launch.assert_called_once_with()
    guestfs().list_devices.assert_called_once_with()
    guestfs().add_drive.assert_called_once_with(str(tmpdir / "rootfs.ext4"))
    guestfs().mount.assert_called_once_with(guestfs().list_devices()[0], "/")
    guestfs().mkdir_p.assert_called_once_with("/")
    guestfs().tar_in.assert_called_once_with(
        str(tmpdir / "overlay.tar.gz"), "/", compress="gzip"
    )
    assert caplog.record_tuples == [
        ("dispatcher", 20, f"Modifying '{tmpdir}/rootfs.ext4'"),
        ("dispatcher", 10, "Overlays:"),
        ("dispatcher", 10, f"- rootfs.lava: '{tmpdir}/overlay.tar.gz' to '/'"),
    ]
