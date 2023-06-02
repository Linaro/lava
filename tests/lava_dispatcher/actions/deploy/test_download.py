# Copyright (C) 2019 Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from pathlib import Path
from urllib.parse import urlparse

import pytest
import requests

from lava_common.constants import HTTP_DOWNLOAD_CHUNK_SIZE
from lava_common.exceptions import InfrastructureError, JobError
from lava_dispatcher.actions.deploy.download import (
    CopyToLxcAction,
    DownloaderAction,
    DownloadHandler,
    FileDownloadAction,
    HttpDownloadAction,
    LxcDownloadAction,
    PreDownloadedAction,
    ScpDownloadAction,
)
from lava_dispatcher.job import Job
from tests.lava_dispatcher.test_basic import Factory


def test_downloader_populate_http():
    # "images.key" with http
    action = DownloaderAction(
        "key", "/path/to/save", params={"url": "http://url.org/resource.img"}
    )
    action.level = 1
    action.populate({"images": {"key": {"url": "http://url.org/resource.img"}}})
    assert len(action.pipeline.actions) == 1
    assert isinstance(action.pipeline.actions[0], HttpDownloadAction)
    assert action.pipeline.actions[0].url == urlparse("http://url.org/resource.img")

    # "key" with http
    action = DownloaderAction(
        "key", "/path/to/save", params={"url": "http://url.org/resource.img"}
    )
    action.level = 1
    action.populate({"key": {"url": "http://url.org/resource.img"}})
    assert len(action.pipeline.actions) == 1
    assert isinstance(action.pipeline.actions[0], HttpDownloadAction)
    assert action.pipeline.actions[0].url == urlparse("http://url.org/resource.img")


def test_downloader_populate_https():
    # "images.key" with https
    action = DownloaderAction(
        "key", "/path/to/save", params={"url": "https://url.org/resource.img"}
    )
    action.level = 1
    action.populate({"images": {"key": {"url": "https://url.org/resource.img"}}})
    assert len(action.pipeline.actions) == 1
    assert isinstance(action.pipeline.actions[0], HttpDownloadAction)
    assert action.pipeline.actions[0].url == urlparse("https://url.org/resource.img")

    # "key" with https
    action = DownloaderAction(
        "key", "/path/to/save", params={"url": "https://url.org/resource.img"}
    )
    action.level = 1
    action.populate({"key": {"url": "https://url.org/resource.img"}})
    assert len(action.pipeline.actions) == 1
    assert isinstance(action.pipeline.actions[0], HttpDownloadAction)
    assert action.pipeline.actions[0].url == urlparse("https://url.org/resource.img")


def test_downloader_populate_scp():
    # "images.key" with scp
    action = DownloaderAction(
        "key", "/path/to/save", params={"url": "scp://user@host:/resource.img"}
    )
    action.level = 1
    action.populate({"images": {"key": {"url": "scp://user@host:/resource.img"}}})
    assert len(action.pipeline.actions) == 1
    assert isinstance(action.pipeline.actions[0], ScpDownloadAction)
    assert action.pipeline.actions[0].url == urlparse("scp://user@host:/resource.img")

    # "key" with scp
    action = DownloaderAction(
        "key", "/path/to/save", params={"url": "scp://user@host:/resource.img"}
    )
    action.level = 1
    action.populate({"key": {"url": "scp://user@host:/resource.img"}})
    assert len(action.pipeline.actions) == 1
    assert isinstance(action.pipeline.actions[0], ScpDownloadAction)
    assert action.pipeline.actions[0].url == urlparse("scp://user@host:/resource.img")


def test_downloader_populate_file():
    # "images.key" with file
    action = DownloaderAction(
        "key", "/path/to/save", params={"url": "file:///resource.img"}
    )
    action.level = 1
    action.populate({"images": {"key": {"url": "file:///resource.img"}}})
    assert len(action.pipeline.actions) == 1
    assert isinstance(action.pipeline.actions[0], FileDownloadAction)
    assert action.pipeline.actions[0].url == urlparse("file:///resource.img")

    # "key" with file
    action = DownloaderAction(
        "key", "/path/to/save", params={"url": "file:///resource.img"}
    )
    action.level = 1
    action.populate({"key": {"url": "file:///resource.img"}})
    assert len(action.pipeline.actions) == 1
    assert isinstance(action.pipeline.actions[0], FileDownloadAction)
    assert action.pipeline.actions[0].url == urlparse("file:///resource.img")


def test_downloader_populate_file():
    # "images.key" with lxc
    action = DownloaderAction(
        "key", "/path/to/save", params={"url": "lxc:///resource.img"}
    )
    action.level = 1
    action.populate({"images": {"key": {"url": "lxc:///resource.img"}}})
    assert len(action.pipeline.actions) == 1
    assert isinstance(action.pipeline.actions[0], LxcDownloadAction)
    assert action.pipeline.actions[0].url == urlparse("lxc:///resource.img")

    # "key" with lxc
    action = DownloaderAction(
        "key", "/path/to/save", params={"url": "lxc:///resource.img"}
    )
    action.level = 1
    action.populate({"key": {"url": "lxc:///resource.img"}})
    assert len(action.pipeline.actions) == 1
    assert isinstance(action.pipeline.actions[0], LxcDownloadAction)
    assert action.pipeline.actions[0].url == urlparse("lxc:///resource.img")


def test_downloader_unsupported_scheme():
    # Test raise
    # 1. unsupported scheme
    action = DownloaderAction(
        "key", "/path/to/save", params={"url": "ftp://user@host:/resource.img"}
    )
    action.level = 1
    with pytest.raises(JobError) as exc:
        action.populate({"key": {"url": "ftp://user@host:/resource.img"}})
    assert exc.match("Unsupported url protocol scheme: ftp")


def test_downloader_no_url():
    # 1. no url available
    action = DownloaderAction("key", "/path/to/save", params={})
    action.level = 1
    with pytest.raises(JobError) as exc:
        action.populate({"key": {}})
    assert exc.match("Invalid deploy action: 'url' is missing for 'key'")


def test_download_handler_validate_simple():
    # "images.key" without extra parameters
    action = DownloadHandler(
        "key", "/path/to/save", urlparse("http://example.com/resource.img")
    )
    action.job = Job(1234, {}, None)
    action.parameters = {
        "images": {"key": {"url": "http://example.com/resource.img"}},
        "namespace": "common",
    }
    action.params = action.parameters["images"]["key"]
    action.validate()
    assert action.data == {
        "common": {
            "download-action": {
                "key": {"file": "/path/to/save/key/resource.img", "compression": None}
            }
        }
    }

    # "key" without extra parameters
    action = DownloadHandler(
        "key", "/path/to/save", urlparse("http://example.com/resource.img")
    )
    action.job = Job(1234, {}, None)
    action.parameters = {
        "key": {"url": "http://example.com/resource.img"},
        "namespace": "common",
    }
    action.params = action.parameters["key"]
    action.validate()
    assert action.data == {
        "common": {
            "download-action": {
                "key": {"file": "/path/to/save/key/resource.img", "compression": None}
            }
        }
    }


def test_download_handler_validate_kernel():
    # "images.key" for kernel
    # In this case, the "kernel.type" is not taken into account
    action = DownloadHandler(
        "kernel", "/path/to/save", urlparse("http://example.com/kernel")
    )
    action.job = Job(1234, {}, None)
    action.parameters = {
        "images": {"kernel": {"url": "http://example.com/kernel", "type": "zimage"}},
        "namespace": "common",
    }
    action.params = action.parameters["images"]["kernel"]
    action.validate()
    assert action.data == {
        "common": {
            "download-action": {
                "kernel": {"file": "/path/to/save/kernel/kernel", "compression": None}
            }
        }
    }

    # "key" for kernel
    action = DownloadHandler(
        "kernel", "/path/to/save", urlparse("http://example.com/kernel")
    )
    action.job = Job(1234, {}, None)
    action.parameters = {
        "kernel": {"url": "http://example.com/kernel", "type": "zimage"},
        "namespace": "common",
    }
    action.params = action.parameters["kernel"]
    action.validate()
    assert action.data == {
        "common": {
            "download-action": {
                "kernel": {"file": "/path/to/save/kernel/kernel", "compression": None},
                "type": {"kernel": "zimage"},
            }
        }
    }


def test_download_handler_validate_extra_arguments():
    # "images.key" with compression, image_arg, overlay, ...
    action = DownloadHandler(
        "key", "/path/to/save", urlparse("http://example.com/resource.img.gz")
    )
    action.job = Job(1234, {}, None)
    action.parameters = {
        "images": {
            "key": {
                "url": "http://example.com/resource.img.gz",
                "compression": "gz",
                "image_arg": "something",
                "overlay": True,
            }
        },
        "namespace": "common",
    }
    action.params = action.parameters["images"]["key"]
    action.validate()
    assert action.data == {
        "common": {
            "download-action": {
                "key": {
                    "file": "/path/to/save/key/resource.img",
                    "image_arg": "something",
                    "compression": "gz",
                    "overlay": True,
                }
            }
        }
    }

    # "key" with compression, image_arg, overlay, ...
    action = DownloadHandler(
        "key", "/path/to/save", urlparse("http://example.com/resource.img.gz")
    )
    action.job = Job(1234, {}, None)
    action.parameters = {
        "key": {
            "url": "http://example.com/resource.img.gz",
            "compression": "gz",
            "image_arg": "something",
            "overlay": True,
        },
        "namespace": "common",
    }
    action.params = action.parameters["key"]
    action.validate()
    assert action.data == {
        "common": {
            "download-action": {
                "key": {
                    "file": "/path/to/save/key/resource.img",
                    "compression": "gz",
                    "image_arg": "something",
                    "overlay": True,
                }
            }
        }
    }


def test_download_handler_errors():
    # "key" downloading a directory
    # TODO: is this a good idea to keep this feature?
    action = DownloadHandler(
        "key", "/path/to/save", urlparse("http://example.com/resource/")
    )
    action.section = "deploy"
    action.job = Job(1234, {}, None)
    action.parameters = {
        "key": {"url": "http://example.com/resource/"},
        "namespace": "common",
    }
    action.params = action.parameters["key"]
    with pytest.raises(JobError) as exc:
        action.validate()
    assert str(exc.value) == "Cannot download a directory for key"

    # Unknown compression format
    action = DownloadHandler(
        "key", "/path/to/save", urlparse("http://example.com/resource.img")
    )
    action.section = "deploy"
    action.job = Job(1234, {}, None)
    action.parameters = {
        "key": {"url": "http://example.com/resource.img", "compression": "something"},
        "namespace": "common",
    }
    action.params = action.parameters["key"]
    action.validate()
    assert action.errors == ["Unknown 'compression' format 'something'"]

    # Unknown archive format
    action = DownloadHandler(
        "key", "/path/to/save", urlparse("http://example.com/resource.img")
    )
    action.section = "deploy"
    action.job = Job(1234, {}, None)
    action.parameters = {
        "key": {"url": "http://example.com/resource.img", "archive": "cpio"},
        "namespace": "common",
    }
    action.params = action.parameters["key"]
    action.validate()
    assert action.errors == ["Unknown 'archive' format 'cpio'"]


def test_file_download_validate(tmp_path):
    # Create the file to use
    (tmp_path / "bla.img").write_text("hello", encoding="utf-8")

    # Working
    action = FileDownloadAction(
        "image", "/path/to/file", urlparse("file://" + str(tmp_path) + "/bla.img")
    )
    action.section = "deploy"
    action.job = Job(1234, {}, None)
    action.parameters = {
        "image": {"url": "file://" + str(tmp_path) + "/bla.img"},
        "namespace": "common",
    }
    action.params = action.parameters["image"]
    action.validate()
    assert action.errors == []
    assert action.size == 5

    # Missing file
    action = FileDownloadAction(
        "image", "/path/to/file", urlparse("file://" + str(tmp_path) + "/bla2.img")
    )
    action.section = "deploy"
    action.job = Job(1234, {}, None)
    action.parameters = {
        "image": {"url": "file://" + str(tmp_path) + "/bla2.img"},
        "namespace": "common",
    }
    action.params = action.parameters["image"]
    action.validate()
    assert action.errors == [
        "Image file '" + str(tmp_path) + "/bla2.img' does not exist or is not readable"
    ]
    assert action.size == -1


def test_http_download_validate(mocker):
    class DummyResponseNOK:
        status_code = 404

        def close(self):
            pass

    class DummyResponseOK:
        status_code = requests.codes.OK
        headers = {"content-length": "4212"}

        def close(self):
            pass

    def dummyhead(url, allow_redirects, headers, timeout):
        assert allow_redirects is True
        assert headers == {"Accept-Encoding": ""}
        if url == "https://example.com/kernel":
            return DummyResponseOK()
        elif url == "https://example.com/dtb":
            return DummyResponseNOK()
        assert 0

    def dummyget(url, allow_redirects, stream, headers, timeout):
        assert allow_redirects is True
        assert stream is True
        assert headers == {"Accept-Encoding": ""}
        assert url == "https://example.com/dtb"
        return DummyResponseOK()

    mocker.patch("requests.head", dummyhead)
    mocker.patch("requests.get", dummyget)

    # HEAD is working
    action = HttpDownloadAction(
        "image", "/path/to/file", urlparse("https://example.com/kernel")
    )
    action.section = "deploy"
    action.job = Job(1234, {"dispatcher": {}}, None)
    action.parameters = {
        "image": {"url": "https://example.com/kernel"},
        "namespace": "common",
    }
    action.params = action.parameters["image"]
    action.validate()
    assert action.errors == []
    assert action.size == 4212

    # Only GET works
    action = HttpDownloadAction(
        "image", "/path/to/file", urlparse("https://example.com/dtb")
    )
    action.section = "deploy"
    action.job = Job(1234, {"dispatcher": {}}, None)
    action.parameters = {
        "image": {"url": "https://example.com/dtb"},
        "namespace": "common",
    }
    action.params = action.parameters["image"]
    action.validate()
    assert action.errors == []
    assert action.size == 4212

    # 404
    def response404(*args, **kwargs):
        print(args)
        print(str(kwargs))
        return DummyResponseNOK()

    mocker.patch("requests.head", response404)
    mocker.patch("requests.get", response404)

    action = HttpDownloadAction(
        "image", "/path/to/file", urlparse("https://example.com/kernel")
    )
    action.section = "deploy"
    action.job = Job(1234, {"dispatcher": {}}, None)
    action.parameters = {
        "image": {"url": "https://example.com/kernel"},
        "namespace": "common",
    }
    action.params = action.parameters["image"]
    action.validate()
    assert action.errors == [
        "Resource unavailable at 'https://example.com/kernel' (404)"
    ]

    # Raising exceptions
    def raisinghead(url, allow_redirects, headers, timeout):
        raise requests.Timeout()

    mocker.patch("requests.head", raisinghead)
    action = HttpDownloadAction(
        "image", "/path/to/file", urlparse("https://example.com/kernel")
    )
    action.section = "deploy"
    action.job = Job(1234, {"dispatcher": {}}, None)
    action.parameters = {
        "image": {"url": "https://example.com/kernel"},
        "namespace": "common",
    }
    action.params = action.parameters["image"]
    action.validate()
    assert action.errors == ["'https://example.com/kernel' timed out"]

    def raisinghead2(url, allow_redirects, headers, timeout):
        raise requests.RequestException("an error occurred")

    mocker.patch("requests.head", raisinghead2)
    action = HttpDownloadAction(
        "image", "/path/to/file", urlparse("https://example.com/kernel")
    )
    action.section = "deploy"
    action.job = Job(1234, {"dispatcher": {}}, None)
    action.parameters = {
        "image": {"url": "https://example.com/kernel"},
        "namespace": "common",
    }
    action.params = action.parameters["image"]
    action.validate()
    assert action.errors == [
        "Unable to get 'https://example.com/kernel': an error occurred"
    ]


def test_file_download_reader(tmp_path):
    # Create the file to use
    (tmp_path / "bla.img").write_text("hello", encoding="utf-8")

    # Normal case
    action = FileDownloadAction(
        "image", "/path/to/file", urlparse("file://" + str(tmp_path) + "/bla.img")
    )
    action.url = urlparse("file://" + str(tmp_path) + "/bla.img")
    ite = action.reader()
    assert next(ite) == b"hello"
    with pytest.raises(StopIteration):
        next(ite)

    # Error when reading
    action = FileDownloadAction(
        "image", "/path/to/file", urlparse("file://" + str(tmp_path) + "/bla2.img")
    )
    action.url = urlparse("file://" + str(tmp_path) + "/bla2.img")
    ite = action.reader()
    with pytest.raises(InfrastructureError) as exc:
        next(ite)
    assert exc.match(
        "Unable to read from %s: \\[Errno 2\\] No such file or directory: '%s'"
        % (str(tmp_path / "bla2.img"), str(tmp_path / "bla2.img"))
    )


def test_http_download_reader(mocker):
    # Working
    class DummyResponse:
        status_code = requests.codes.OK
        headers = {"content-length": "4212"}

        def iter_content(self, size):
            assert size == HTTP_DOWNLOAD_CHUNK_SIZE
            yield b"hello"

        def close(self):
            pass

    def dummyget(url, allow_redirects, stream, headers, timeout):
        assert allow_redirects is True
        assert stream is True
        assert url == "https://example.com/dtb"
        return DummyResponse()

    mocker.patch("requests.get", dummyget)
    action = HttpDownloadAction(
        "image", "/path/to/file", urlparse("https://example.com/dtb")
    )
    action.url = urlparse("https://example.com/dtb")

    ite = action.reader()
    assert next(ite) == b"hello"
    with pytest.raises(StopIteration):
        next(ite)

    # Not working
    def dummygetraise(url, allow_redirects, stream, headers, timeout):
        raise requests.RequestException("error")

    mocker.patch("requests.get", dummygetraise)
    action = HttpDownloadAction(
        "image", "/path/to/file", urlparse("https://example.com/dtb")
    )
    action.url = urlparse("https://example.com/dtb")

    ite = action.reader()
    with pytest.raises(InfrastructureError) as exc:
        next(ite)
    assert exc.match("Unable to download 'https://example.com/dtb': error")


def test_http_download_run(tmp_path):
    def reader():
        yield b"hello"
        yield b"world"

    action = HttpDownloadAction(
        "dtb", str(tmp_path), urlparse("https://example.com/dtb")
    )
    action.job = Job(1234, {"dispatcher": {}}, None)
    action.url = urlparse("https://example.com/dtb")
    action.parameters = {
        "to": "download",
        "images": {
            "dtb": {
                "url": "https://example.com/dtb",
                "md5sum": "fc5e038d38a57032085441e7fe7010b0",
                "sha256sum": "936a185caaa266bb9cbe981e9e05cb78cd732b0b3280eb944412bb6f8f8f07af",
                "sha512sum": "1594244d52f2d8c12b142bb61f47bc2eaf503d6d9ca8480cae9fcf112f66e4967dc5e8fa98285e36db8af1b8ffa8b84cb15e0fbcf836c3deb803c13f37659a60",
            }
        },
        "namespace": "common",
    }
    action.params = action.parameters["images"]["dtb"]
    action.reader = reader
    action.fname = str(tmp_path / "dtb/dtb")
    action.run(None, 4212)
    data = ""
    with open(str(tmp_path / "dtb/dtb")) as f_in:
        data = f_in.read()
    assert data == "helloworld"
    assert dict(action.results) == {
        "success": {
            "sha512": "1594244d52f2d8c12b142bb61f47bc2eaf503d6d9ca8480cae9fcf112f66e4967dc5e8fa98285e36db8af1b8ffa8b84cb15e0fbcf836c3deb803c13f37659a60"
        },
        "label": "dtb",
        "size": 10,
        "md5sum": "fc5e038d38a57032085441e7fe7010b0",
        "sha256sum": "936a185caaa266bb9cbe981e9e05cb78cd732b0b3280eb944412bb6f8f8f07af",
        "sha512sum": "1594244d52f2d8c12b142bb61f47bc2eaf503d6d9ca8480cae9fcf112f66e4967dc5e8fa98285e36db8af1b8ffa8b84cb15e0fbcf836c3deb803c13f37659a60",
    }
    assert action.data == {
        "common": {
            "download-action": {
                "dtb": {
                    "decompressed": False,
                    "file": "%s/dtb/dtb" % str(tmp_path),
                    "md5": "fc5e038d38a57032085441e7fe7010b0",
                    "sha256": "936a185caaa266bb9cbe981e9e05cb78cd732b0b3280eb944412bb6f8f8f07af",
                    "sha512": "1594244d52f2d8c12b142bb61f47bc2eaf503d6d9ca8480cae9fcf112f66e4967dc5e8fa98285e36db8af1b8ffa8b84cb15e0fbcf836c3deb803c13f37659a60",
                },
                "file": {"dtb": "%s/dtb/dtb" % str(tmp_path)},
            }
        }
    }


def test_http_download_run_compressed(tmp_path):
    def reader():
        yield b"\xfd7zXZ\x00\x00\x04\xe6\xd6\xb4F\x02\x00!\x01\x16\x00\x00"
        yield b"\x00t/\xe5\xa3\x01\x00\x0bhello world\n\x00\xa1\xf2\xff\xc4j"
        yield b"\x7f\xbf\xcf\x00\x01$\x0c\xa6\x18\xd8\xd8\x1f\xb6\xf3}\x01"
        yield b"\x00\x00\x00\x00\x04YZ"

    action = HttpDownloadAction(
        "rootfs", str(tmp_path), urlparse("https://example.com/rootfs.xz")
    )
    action.job = Job(1234, {}, None)
    action.url = urlparse("https://example.com/rootfs.xz")
    action.parameters = {
        "to": "download",
        "rootfs": {
            "url": "https://example.com/rootfs.xz",
            "compression": "xz",
            "md5sum": "0107d527acf9b8de628b7b4d103c89d1",
            "sha256sum": "3275a39be7b717d548b66f3c8f23d940603a63b0f13d84a596d979a7f66feb2c",
            "sha512sum": "d0850c3e0c45bdf74995907a04f69806a070d79a4f0b2dd82d6b96adafdbfd85ce6c1daaff916ff089bdf9b04eba7805041c49afecdbeabca69fef802e60de35",
        },
        "namespace": "common",
    }
    action.params = action.parameters["rootfs"]
    action.reader = reader
    action.size = 68
    action.fname = str(tmp_path / "rootfs/rootfs")
    action.run(None, 4212)
    data = ""
    with open(str(tmp_path / "rootfs/rootfs")) as f_in:
        data = f_in.read()
    assert data == "hello world\n"
    assert dict(action.results) == {
        "success": {
            "sha512": "d0850c3e0c45bdf74995907a04f69806a070d79a4f0b2dd82d6b96adafdbfd85ce6c1daaff916ff089bdf9b04eba7805041c49afecdbeabca69fef802e60de35"
        },
        "label": "rootfs",
        "size": 68,
        "md5sum": "0107d527acf9b8de628b7b4d103c89d1",
        "sha256sum": "3275a39be7b717d548b66f3c8f23d940603a63b0f13d84a596d979a7f66feb2c",
        "sha512sum": "d0850c3e0c45bdf74995907a04f69806a070d79a4f0b2dd82d6b96adafdbfd85ce6c1daaff916ff089bdf9b04eba7805041c49afecdbeabca69fef802e60de35",
    }

    assert action.data == {
        "common": {
            "download-action": {
                "rootfs": {
                    "decompressed": True,
                    "file": "%s/rootfs/rootfs" % str(tmp_path),
                    "md5": "0107d527acf9b8de628b7b4d103c89d1",
                    "sha256": "3275a39be7b717d548b66f3c8f23d940603a63b0f13d84a596d979a7f66feb2c",
                    "sha512": "d0850c3e0c45bdf74995907a04f69806a070d79a4f0b2dd82d6b96adafdbfd85ce6c1daaff916ff089bdf9b04eba7805041c49afecdbeabca69fef802e60de35",
                },
                "file": {"rootfs": "%s/rootfs/rootfs" % str(tmp_path)},
            }
        }
    }


def test_predownloaded_job_validation():
    factory = Factory()
    factory.validate_job_strict = True
    job = factory.create_job(
        "kvm01.jinja2", "sample_jobs/qemu-download-postprocess.yaml"
    )
    job.validate()


def test_predownloaded():
    params = {
        "to": "tmpfs",
        "rootfs": {"url": "downloads://rootfs.xz"},
        "namespace": "common",
    }
    job = Job(1234, {}, None)
    destdir = job.mkdtemp("some-other-action")
    action = PreDownloadedAction(
        "rootfs", urlparse("downloads://rootfs.xz"), destdir, params
    )
    action.parameters = params
    action.job = job

    filename = Path(action.job.tmp_dir) / "downloads/common/rootfs.xz"
    filename.parent.mkdir(parents=True)
    filename.touch()

    action.data = {}
    action.parameters = {"namespace": "common"}
    action.validate()
    action.run(None, 4242)
    mapped_path = action.get_namespace_data(
        action="download-action", label="rootfs", key="file"
    )
    assert mapped_path == (destdir + "/rootfs.xz")
    assert Path(mapped_path).exists()


def test_predownloaded_subdirectory():
    params = {"to": "tmpfs", "rootfs": {"url": "downloads://subdir/rootfs.xz"}}
    job = Job(1234, {}, None)
    destdir = job.mkdtemp("some-other-action")
    action = PreDownloadedAction(
        "rootfs", urlparse("downloads://subdir/rootfs.xz"), destdir, params
    )
    action.parameters = params
    action.job = job

    filename = Path(action.job.tmp_dir) / "downloads/common/subdir/rootfs.xz"
    filename.parent.mkdir(parents=True)
    filename.touch()

    action.data = {}
    action.parameters = {"namespace": "common"}
    action.validate()
    action.run(None, 4242)
    mapped_path = action.get_namespace_data(
        action="download-action", label="rootfs", key="file"
    )
    assert mapped_path == (destdir + "/subdir/rootfs.xz")
    assert Path(mapped_path).exists()


def test_predownloaded_missing_file(tmp_path):
    job = Job(1234, {}, None)
    destdir = job.mkdtemp("some-other-action")
    action = PreDownloadedAction("rootfs", urlparse("downloads://missing.xz"), destdir)
    action.job = job
    action.parameters = {"namespace": "common"}
    with pytest.raises(JobError) as exc:
        action.run(None, 4242)


def test_copy_to_lxc_without_lxc_should_do_nothing():
    action = CopyToLxcAction()
    action.job = Job(1234, {}, None)
    action.run(None, 4242)  # no crash = success
