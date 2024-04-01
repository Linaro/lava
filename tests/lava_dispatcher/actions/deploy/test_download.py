# Copyright (C) 2019 Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlparse

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

from ...test_basic import Factory, LavaDispatcherTestCase


class TestDowload(LavaDispatcherTestCase):
    def test_downloader_populate_http(self):
        job = self.create_simple_job()
        # "images.key" with http
        action = DownloaderAction(
            job, "key", "/path/to/save", params={"url": "http://url.org/resource.img"}
        )
        action.level = 1
        action.populate({"images": {"key": {"url": "http://url.org/resource.img"}}})
        self.assertEqual(len(action.pipeline.actions), 1)
        self.assertIsInstance(action.pipeline.actions[0], HttpDownloadAction)
        self.assertEqual(
            action.pipeline.actions[0].url, urlparse("http://url.org/resource.img")
        )

        # "key" with http
        action = DownloaderAction(
            job, "key", "/path/to/save", params={"url": "http://url.org/resource.img"}
        )
        action.level = 1
        action.populate({"key": {"url": "http://url.org/resource.img"}})
        self.assertEqual(len(action.pipeline.actions), 1)
        self.assertIsInstance(action.pipeline.actions[0], HttpDownloadAction)
        self.assertEqual(
            action.pipeline.actions[0].url, urlparse("http://url.org/resource.img")
        )

    def test_downloader_populate_https(self):
        job = self.create_simple_job()
        # "images.key" with https
        action = DownloaderAction(
            job, "key", "/path/to/save", params={"url": "https://url.org/resource.img"}
        )
        action.level = 1
        action.populate({"images": {"key": {"url": "https://url.org/resource.img"}}})
        self.assertEqual(len(action.pipeline.actions), 1)
        self.assertIsInstance(action.pipeline.actions[0], HttpDownloadAction)
        self.assertEqual(
            action.pipeline.actions[0].url, urlparse("https://url.org/resource.img")
        )

        # "key" with https
        action = DownloaderAction(
            job, "key", "/path/to/save", params={"url": "https://url.org/resource.img"}
        )
        action.level = 1
        action.populate({"key": {"url": "https://url.org/resource.img"}})
        self.assertEqual(len(action.pipeline.actions), 1)
        self.assertIsInstance(action.pipeline.actions[0], HttpDownloadAction)
        self.assertEqual(
            action.pipeline.actions[0].url, urlparse("https://url.org/resource.img")
        )

    def test_downloader_populate_scp(self):
        job = self.create_simple_job()
        # "images.key" with scp
        action = DownloaderAction(
            job, "key", "/path/to/save", params={"url": "scp://user@host:/resource.img"}
        )
        action.level = 1
        action.populate({"images": {"key": {"url": "scp://user@host:/resource.img"}}})
        self.assertEqual(len(action.pipeline.actions), 1)
        self.assertIsInstance(action.pipeline.actions[0], ScpDownloadAction)
        self.assertEqual(
            action.pipeline.actions[0].url, urlparse("scp://user@host:/resource.img")
        )

        # "key" with scp
        action = DownloaderAction(
            job, "key", "/path/to/save", params={"url": "scp://user@host:/resource.img"}
        )
        action.level = 1
        action.populate({"key": {"url": "scp://user@host:/resource.img"}})
        self.assertEqual(len(action.pipeline.actions), 1)
        self.assertIsInstance(action.pipeline.actions[0], ScpDownloadAction)
        self.assertEqual(
            action.pipeline.actions[0].url, urlparse("scp://user@host:/resource.img")
        )

    def test_downloader_populate_image_file(self):
        job = self.create_simple_job()
        # "images.key" with file
        action = DownloaderAction(
            job, "key", "/path/to/save", params={"url": "file:///resource.img"}
        )
        action.level = 1
        action.populate({"images": {"key": {"url": "file:///resource.img"}}})
        self.assertEqual(len(action.pipeline.actions), 1)
        self.assertIsInstance(action.pipeline.actions[0], FileDownloadAction)
        self.assertEqual(
            action.pipeline.actions[0].url, urlparse("file:///resource.img")
        )

        # "key" with file
        action = DownloaderAction(
            job, "key", "/path/to/save", params={"url": "file:///resource.img"}
        )
        action.level = 1
        action.populate({"key": {"url": "file:///resource.img"}})
        self.assertEqual(len(action.pipeline.actions), 1)
        self.assertIsInstance(action.pipeline.actions[0], FileDownloadAction)
        self.assertEqual(
            action.pipeline.actions[0].url, urlparse("file:///resource.img")
        )

    def test_downloader_populate_lxc_file(self):
        job = self.create_simple_job()
        # "images.key" with lxc
        action = DownloaderAction(
            job, "key", "/path/to/save", params={"url": "lxc:///resource.img"}
        )
        action.level = 1
        action.populate({"images": {"key": {"url": "lxc:///resource.img"}}})
        self.assertEqual(len(action.pipeline.actions), 1)
        self.assertIsInstance(action.pipeline.actions[0], LxcDownloadAction)
        self.assertEqual(
            action.pipeline.actions[0].url, urlparse("lxc:///resource.img")
        )

        # "key" with lxc
        action = DownloaderAction(
            job, "key", "/path/to/save", params={"url": "lxc:///resource.img"}
        )
        action.level = 1
        action.populate({"key": {"url": "lxc:///resource.img"}})
        self.assertEqual(len(action.pipeline.actions), 1)
        self.assertIsInstance(action.pipeline.actions[0], LxcDownloadAction)
        self.assertEqual(
            action.pipeline.actions[0].url, urlparse("lxc:///resource.img")
        )

    def test_downloader_unsupported_scheme(self):
        # Test raise
        # 1. unsupported scheme
        action = DownloaderAction(
            self.create_job_mock(),
            "key",
            "/path/to/save",
            params={"url": "ftp://user@host:/resource.img"},
        )
        action.level = 1
        with self.assertRaisesRegex(JobError, "Unsupported url protocol scheme: ftp"):
            action.populate({"key": {"url": "ftp://user@host:/resource.img"}})

    def test_downloader_no_url(self):
        # 1. no url available
        action = DownloaderAction(
            self.create_job_mock(), "key", "/path/to/save", params={}
        )
        action.level = 1
        with self.assertRaisesRegex(
            JobError, "Invalid deploy action: 'url' is missing for 'key'"
        ):
            action.populate({"key": {}})

    def test_download_handler_validate_simple(self):
        # "images.key" without extra parameters
        job = self.create_simple_job()
        action = DownloadHandler(
            job, "key", "/path/to/save", urlparse("http://example.com/resource.img")
        )
        action.parameters = {
            "images": {"key": {"url": "http://example.com/resource.img"}},
            "namespace": "common",
        }
        action.params = action.parameters["images"]["key"]
        action.validate()
        self.assertEqual(
            action.data,
            {
                "common": {
                    "download-action": {
                        "key": {
                            "file": "/path/to/save/key/resource.img",
                            "compression": None,
                        }
                    }
                }
            },
        )

        # "key" without extra parameters
        job = self.create_simple_job()
        action = DownloadHandler(
            job, "key", "/path/to/save", urlparse("http://example.com/resource.img")
        )
        action.parameters = {
            "key": {"url": "http://example.com/resource.img"},
            "namespace": "common",
        }
        action.params = action.parameters["key"]
        action.validate()
        self.assertEqual(
            action.data,
            {
                "common": {
                    "download-action": {
                        "key": {
                            "file": "/path/to/save/key/resource.img",
                            "compression": None,
                        }
                    }
                }
            },
        )

    def test_download_handler_validate_kernel(self):
        # "images.key" for kernel
        # In this case, the "kernel.type" is not taken into account
        job = self.create_simple_job()
        action = DownloadHandler(
            job, "kernel", "/path/to/save", urlparse("http://example.com/kernel")
        )
        action.parameters = {
            "images": {
                "kernel": {"url": "http://example.com/kernel", "type": "zimage"}
            },
            "namespace": "common",
        }
        action.params = action.parameters["images"]["kernel"]
        action.validate()
        self.assertEqual(
            action.data,
            {
                "common": {
                    "download-action": {
                        "kernel": {
                            "file": "/path/to/save/kernel/kernel",
                            "compression": None,
                        }
                    }
                }
            },
        )

        # "key" for kernel
        job = self.create_simple_job()
        action = DownloadHandler(
            job, "kernel", "/path/to/save", urlparse("http://example.com/kernel")
        )
        action.parameters = {
            "kernel": {"url": "http://example.com/kernel", "type": "zimage"},
            "namespace": "common",
        }
        action.params = action.parameters["kernel"]
        action.validate()
        self.assertEqual(
            action.data,
            {
                "common": {
                    "download-action": {
                        "kernel": {
                            "file": "/path/to/save/kernel/kernel",
                            "compression": None,
                        },
                        "type": {"kernel": "zimage"},
                    }
                }
            },
        )

    def test_download_handler_validate_extra_arguments(self):
        # "images.key" with compression, image_arg, overlay, ...
        job = self.create_simple_job()
        action = DownloadHandler(
            job, "key", "/path/to/save", urlparse("http://example.com/resource.img.gz")
        )
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
        self.assertEqual(
            action.data,
            {
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
            },
        )

        # "key" with compression, image_arg, overlay, ...
        job = self.create_simple_job()
        action = DownloadHandler(
            job, "key", "/path/to/save", urlparse("http://example.com/resource.img.gz")
        )
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
        self.assertEqual(
            action.data,
            {
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
            },
        )

    def test_download_handler_errors(self):
        job = self.create_simple_job()
        # "key" downloading a directory
        # TODO: is this a good idea to keep this feature?

        action = DownloadHandler(
            job, "key", "/path/to/save", urlparse("http://example.com/resource/")
        )
        action.section = "deploy"
        action.parameters = {
            "key": {"url": "http://example.com/resource/"},
            "namespace": "common",
        }
        action.params = action.parameters["key"]
        with self.assertRaisesRegex(JobError, "Cannot download a directory for key"):
            action.validate()

        # Unknown compression format
        job = self.create_simple_job()
        action = DownloadHandler(
            job, "key", "/path/to/save", urlparse("http://example.com/resource.img")
        )
        action.section = "deploy"
        action.parameters = {
            "key": {
                "url": "http://example.com/resource.img",
                "compression": "something",
            },
            "namespace": "common",
        }
        action.params = action.parameters["key"]
        action.validate()
        self.assertEqual(action.errors, ["Unknown 'compression' format 'something'"])

        # Unknown archive format
        job = self.create_simple_job()
        action = DownloadHandler(
            job, "key", "/path/to/save", urlparse("http://example.com/resource.img")
        )
        action.section = "deploy"
        action.parameters = {
            "key": {"url": "http://example.com/resource.img", "archive": "cpio"},
            "namespace": "common",
        }
        action.params = action.parameters["key"]
        action.validate()
        self.assertEqual(action.errors, ["Unknown 'archive' format 'cpio'"])

    def test_file_download_validate(self):
        job = self.create_simple_job(job_parameters={"dispatcher": {}})
        tmp_dir_path = self.create_temporary_directory()

        # Create the file to use
        (tmp_dir_path / "bla.img").write_text("hello", encoding="utf-8")

        # Working
        action = FileDownloadAction(
            job,
            "image",
            "/path/to/file",
            urlparse("file://" + str(tmp_dir_path) + "/bla.img"),
        )
        action.section = "deploy"
        action.parameters = {
            "image": {"url": "file://" + str(tmp_dir_path) + "/bla.img"},
            "namespace": "common",
        }
        action.params = action.parameters["image"]
        action.validate()
        self.assertEqual(action.errors, [])
        self.assertEqual(action.size, 5)

        # Missing file
        job = self.create_simple_job()
        action = FileDownloadAction(
            job,
            "image",
            "/path/to/file",
            urlparse("file://" + str(tmp_dir_path) + "/bla2.img"),
        )
        action.section = "deploy"
        action.parameters = {
            "image": {"url": "file://" + str(tmp_dir_path) + "/bla2.img"},
            "namespace": "common",
        }
        action.params = action.parameters["image"]
        action.validate()
        self.assertEqual(
            action.errors,
            [
                "Image file '"
                + str(tmp_dir_path)
                + "/bla2.img' does not exist or is not readable"
            ],
        )
        self.assertEqual(action.size, -1)

    def test_http_download_validate(self):
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
            self.assertIs(allow_redirects, True)
            self.assertEqual(headers, {"Accept-Encoding": ""})
            if url == "https://example.com/kernel":
                return DummyResponseOK()
            elif url == "https://example.com/dtb":
                return DummyResponseNOK()
            else:
                raise ValueError

        def dummyget(url, allow_redirects, stream, headers, timeout):
            self.assertIs(allow_redirects, True)
            self.assertIs(stream, True)
            self.assertEqual(headers, {"Accept-Encoding": ""})
            self.assertEqual(url, "https://example.com/dtb")
            return DummyResponseOK()

        job = self.create_simple_job(job_parameters={"dispatcher": {}})
        # HEAD is working
        action = HttpDownloadAction(
            job, "image", "/path/to/file", urlparse("https://example.com/kernel")
        )
        action.section = "deploy"
        action.parameters = {
            "image": {"url": "https://example.com/kernel"},
            "namespace": "common",
        }
        action.params = action.parameters["image"]
        with patch("requests.head", dummyhead), patch("requests.get", dummyget):
            action.validate()
        self.assertEqual(action.errors, [])
        self.assertEqual(action.size, 4212)

        # Only GET works
        action = HttpDownloadAction(
            job, "image", "/path/to/file", urlparse("https://example.com/dtb")
        )
        action.section = "deploy"
        action.parameters = {
            "image": {"url": "https://example.com/dtb"},
            "namespace": "common",
        }
        action.params = action.parameters["image"]
        with patch("requests.head", dummyhead), patch("requests.get", dummyget):
            action.validate()
        self.assertEqual(action.errors, [])
        self.assertEqual(action.size, 4212)

        # 404
        def response404(*args, **kwargs):
            print(args)
            print(str(kwargs))
            return DummyResponseNOK()

        action = HttpDownloadAction(
            job, "image", "/path/to/file", urlparse("https://example.com/kernel")
        )
        action.section = "deploy"
        action.parameters = {
            "image": {"url": "https://example.com/kernel"},
            "namespace": "common",
        }
        action.params = action.parameters["image"]
        with patch("requests.head", response404), patch("requests.get", response404):
            action.validate()
        self.assertEqual(
            action.errors,
            ["Resource unavailable at 'https://example.com/kernel' (404)"],
        )

        # Raising exceptions
        def raisinghead(url, allow_redirects, headers, timeout):
            raise requests.Timeout()

        action = HttpDownloadAction(
            job, "image", "/path/to/file", urlparse("https://example.com/kernel")
        )
        action.section = "deploy"
        action.parameters = {
            "image": {"url": "https://example.com/kernel"},
            "namespace": "common",
        }
        action.params = action.parameters["image"]
        with patch("requests.head", raisinghead):
            action.validate()
        self.assertEqual(action.errors, ["'https://example.com/kernel' timed out"])

        def raisinghead2(url, allow_redirects, headers, timeout):
            raise requests.RequestException("an error occurred")

        action = HttpDownloadAction(
            job, "image", "/path/to/file", urlparse("https://example.com/kernel")
        )
        action.section = "deploy"
        action.parameters = {
            "image": {"url": "https://example.com/kernel"},
            "namespace": "common",
        }
        action.params = action.parameters["image"]
        with patch("requests.head", raisinghead2):
            action.validate()
        self.assertEqual(
            action.errors,
            ["Unable to get 'https://example.com/kernel': an error occurred"],
        )

    def test_file_download_reader(self):
        tmpr_dir_path = self.create_temporary_directory()

        # Create the file to use
        (tmpr_dir_path / "bla.img").write_text("hello", encoding="utf-8")

        # Normal case
        action = FileDownloadAction(
            self.create_job_mock(),
            "image",
            "/path/to/file",
            urlparse("file://" + str(tmpr_dir_path) + "/bla.img"),
        )
        action.url = urlparse("file://" + str(tmpr_dir_path) + "/bla.img")
        ite = action.reader()
        self.assertEqual(next(ite), b"hello")
        with self.assertRaises(StopIteration):
            next(ite)

        # Error when reading
        action = FileDownloadAction(
            self.create_job_mock(),
            "image",
            "/path/to/file",
            urlparse("file://" + str(tmpr_dir_path) + "/bla2.img"),
        )
        action.url = urlparse("file://" + str(tmpr_dir_path) + "/bla2.img")
        ite = action.reader()
        with self.assertRaisesRegex(
            InfrastructureError,
            (
                "Unable to read from %s: \\[Errno 2\\] No such file or directory: '%s'"
                % (str(tmpr_dir_path / "bla2.img"), str(tmpr_dir_path / "bla2.img"))
            ),
        ):
            next(ite)

    def test_http_download_reader(self):
        # Working
        class DummyResponse:
            # pylint: disable=no-self-argument
            status_code = requests.codes.OK
            headers = {"content-length": "4212"}

            def iter_content(self_, size):
                self.assertEqual(size, HTTP_DOWNLOAD_CHUNK_SIZE)
                yield b"hello"

            def close(self_):
                pass

        def dummyget(url, allow_redirects, stream, headers, timeout):
            self.assertIs(allow_redirects, True)
            self.assertIs(stream, True)
            self.assertEqual(url, "https://example.com/dtb")
            return DummyResponse()

        action = HttpDownloadAction(
            self.create_job_mock(),
            "image",
            "/path/to/file",
            urlparse("https://example.com/dtb"),
        )
        action.url = urlparse("https://example.com/dtb")
        with patch("requests.get", dummyget):
            ite = action.reader()
            self.assertEqual(next(ite), b"hello")
        with self.assertRaises(StopIteration):
            next(ite)

        # Not working
        def dummygetraise(url, allow_redirects, stream, headers, timeout):
            raise requests.RequestException("error")

        action = HttpDownloadAction(
            self.create_job_mock(),
            "image",
            "/path/to/file",
            urlparse("https://example.com/dtb"),
        )
        action.url = urlparse("https://example.com/dtb")

        with patch("requests.get", dummygetraise), self.assertRaisesRegex(
            InfrastructureError, "Unable to download 'https://example.com/dtb': error"
        ):
            ite = action.reader()
            next(ite)

    def test_http_download_run(self):
        tmp_dir_path = self.create_temporary_directory()

        def reader():
            yield b"hello"
            yield b"world"

        action = HttpDownloadAction(
            self.create_job_mock(),
            "dtb",
            str(tmp_dir_path),
            urlparse("https://example.com/dtb"),
        )
        action.job = self.create_simple_job(job_parameters={"dispatcher": {}})
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
        action.fname = str(tmp_dir_path / "dtb/dtb")
        action.run(None, 4212)
        data = ""
        with open(str(tmp_dir_path / "dtb/dtb")) as f_in:
            data = f_in.read()
        self.assertEqual(data, "helloworld")
        self.assertEqual(
            dict(action.results),
            {
                "success": {
                    "sha512": "1594244d52f2d8c12b142bb61f47bc2eaf503d6d9ca8480cae9fcf112f66e4967dc5e8fa98285e36db8af1b8ffa8b84cb15e0fbcf836c3deb803c13f37659a60"
                },
                "label": "dtb",
                "size": 10,
            },
        )
        self.assertEqual(
            action.data,
            {
                "common": {
                    "download-action": {
                        "dtb": {
                            "decompressed": False,
                            "file": "%s/dtb/dtb" % str(tmp_dir_path),
                        },
                        "file": {"dtb": "%s/dtb/dtb" % str(tmp_dir_path)},
                    }
                }
            },
        )

    def test_http_download_run_compressed(self):
        tmp_dir_path = self.create_temporary_directory()

        def reader():
            yield b"\xfd7zXZ\x00\x00\x04\xe6\xd6\xb4F\x02\x00!\x01\x16\x00\x00"
            yield b"\x00t/\xe5\xa3\x01\x00\x0bhello world\n\x00\xa1\xf2\xff\xc4j"
            yield b"\x7f\xbf\xcf\x00\x01$\x0c\xa6\x18\xd8\xd8\x1f\xb6\xf3}\x01"
            yield b"\x00\x00\x00\x00\x04YZ"

        job = self.create_simple_job()
        action = HttpDownloadAction(
            job, "rootfs", str(tmp_dir_path), urlparse("https://example.com/rootfs.xz")
        )
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
        action.fname = str(tmp_dir_path / "rootfs/rootfs")
        action.run(None, 4212)
        data = ""
        with open(str(tmp_dir_path / "rootfs/rootfs")) as f_in:
            data = f_in.read()
        self.assertEqual(data, "hello world\n")
        self.assertEqual(
            dict(action.results),
            {
                "success": {
                    "sha512": "d0850c3e0c45bdf74995907a04f69806a070d79a4f0b2dd82d6b96adafdbfd85ce6c1daaff916ff089bdf9b04eba7805041c49afecdbeabca69fef802e60de35"
                },
                "label": "rootfs",
                "size": 68,
            },
        )

        self.assertEqual(
            action.data,
            {
                "common": {
                    "download-action": {
                        "rootfs": {
                            "decompressed": True,
                            "file": "%s/rootfs/rootfs" % str(tmp_dir_path),
                        },
                        "file": {"rootfs": "%s/rootfs/rootfs" % str(tmp_dir_path)},
                    }
                }
            },
        )

    def test_predownloaded_job_validation(self):
        factory = Factory()
        factory.validate_job_strict = True
        job = factory.create_job("kvm01", "sample_jobs/qemu-download-postprocess.yaml")
        job.validate()

    def test_predownloaded(self):
        params = {
            "to": "tmpfs",
            "rootfs": {"url": "downloads://rootfs.xz"},
            "namespace": "common",
        }
        job = self.create_simple_job()
        destdir = job.mkdtemp("some-other-action")
        action = PreDownloadedAction(
            job, "rootfs", urlparse("downloads://rootfs.xz"), destdir, params
        )
        action.parameters = params

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
        self.assertEqual(mapped_path, (destdir + "/rootfs.xz"))
        self.assertTrue(Path(mapped_path).exists())

    def test_predownloaded_subdirectory(self):
        params = {"to": "tmpfs", "rootfs": {"url": "downloads://subdir/rootfs.xz"}}
        job = self.create_simple_job()
        destdir = job.mkdtemp("some-other-action")
        action = PreDownloadedAction(
            job, "rootfs", urlparse("downloads://subdir/rootfs.xz"), destdir, params
        )
        action.parameters = params

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
        self.assertEqual(mapped_path, (destdir + "/subdir/rootfs.xz"))
        self.assertTrue(Path(mapped_path).exists())

    def test_predownloaded_missing_file(self):
        job = self.create_simple_job()
        destdir = job.mkdtemp("some-other-action")
        action = PreDownloadedAction(
            job, "rootfs", urlparse("downloads://missing.xz"), destdir
        )
        action.parameters = {"namespace": "common"}
        with self.assertRaises(JobError):
            action.run(None, 4242)

    def test_copy_to_lxc_without_lxc_should_do_nothing(self):
        job = self.create_simple_job()
        action = CopyToLxcAction(job)
        action.run(None, 4242)  # no crash = success

    def test_address_place_holder(self):
        factory = Factory()
        factory.validate_job_strict = True
        job = factory.create_job("kvm03", "sample_jobs/qemu-download-postprocess.yaml")
        action = DownloadHandler(
            job, "key", "/path/to/save", urlparse("http://example.com/resource.img")
        )

        action.parameters = {
            "images": {"key": {"url": "http://example.com/resource.img"}},
            "namespace": "common",
        }
        action.params = action.parameters["images"]["key"]
        action.validate()
        assert action.params["url"] == "http://example.com/resource.img"

        action.parameters = {
            "images": {"key": {"url": "http://{FILE_SERVER_IP}/resource.img"}},
            "namespace": "common",
        }
        action.params = action.parameters["images"]["key"]
        action.validate()
        assert action.params["url"] == "http://foobar/resource.img"
