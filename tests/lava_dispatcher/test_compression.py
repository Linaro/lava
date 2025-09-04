# Copyright (C) 2018 Linaro Limited
#
# Author: Matt Hart <matthew.hart@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

import hashlib
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

import responses
from responses import RequestsMock

from lava_common.exceptions import InfrastructureError, JobError
from lava_dispatcher.actions.deploy.download import HttpDownloadAction
from lava_dispatcher.utils.compression import (
    compress_command_map,
    compress_file,
    cpio,
    decompress_file,
    uncpio,
)
from tests.lava_dispatcher.test_basic import Factory, LavaDispatcherTestCase


def setup_responses() -> RequestsMock:
    download_artifacts_dir = Path(__file__).parent / "download_artifacts"
    requests_mock = RequestsMock(assert_all_requests_are_fired=True)

    for compression_postfix in ("gz", "xz", "zip", "bz2"):
        compression_file_path = download_artifacts_dir / f"10MB.{compression_postfix}"
        compression_file_contents = compression_file_path.read_bytes()
        download_url = (
            "http://example.com/functional-test-images/"
            f"compression/10MB.{compression_postfix}"
        )
        requests_mock.add(
            responses.GET,
            url=download_url,
            body=compression_file_contents,
        )
        requests_mock.add(
            responses.HEAD,
            url=download_url,
            headers={"Content-Length": str(len(compression_file_contents))},
        )

    return requests_mock


class TestDecompression(LavaDispatcherTestCase):
    def setUp(self):
        super().setUp()
        self.factory = Factory()
        self.requests_mock = setup_responses()
        self.requests_mock.start()

    def tearDown(self):
        self.requests_mock.stop()
        self.requests_mock.reset()

    def test_download_decompression(self):
        job = self.factory.create_kvm_job("sample_jobs/compression.yaml")
        job.validate()

        self.assertEqual(len(job.pipeline.describe()), 2)

        http_download_actions = job.pipeline.find_all_actions(HttpDownloadAction)
        self.assertEqual(len(http_download_actions), 4)

        sha256sum = "31e00e0e4c233c89051cd748122fde2c98db0121ca09ba93a3820817ea037bc5"
        md5sum = "596c35b949baf46b721744a13f76a258"
        shazipsum = "27259c7aab942273931b71d1fa37e0c5115b6b0fcc969ee40c2e6bb1062af98f"
        md5zipsum = "ec769af027b3dd8145b75369bfb2698b"
        filesize = 10240000
        zipsize = 10109

        for httpaction in http_download_actions:
            httpaction.validate()
            httpaction.parameters = httpaction.parameters["images"]
            httpaction.run(None, None)
            output = httpaction.get_namespace_data(
                action="download-action", label=httpaction.key, key="file"
            )
            outputfile = output.split("/")[-1]
            sha256hash = hashlib.sha256()
            md5sumhash = hashlib.md5()  # nosec - not used for cryptography
            with open(output, "rb", buffering=0) as f:
                for b in iter(lambda: f.read(128 * 1024), b""):
                    sha256hash.update(b)
                    md5sumhash.update(b)
            outputmd5 = md5sumhash.hexdigest()
            outputsha = sha256hash.hexdigest()
            outputsize = os.path.getsize(os.path.join(httpaction.path, output))
            self.assertIsInstance(httpaction.size, int)
            self.assertIsNot(httpaction.size, -1)
            if httpaction.key == "testzip":
                # zipfiles are NOT decompressed on the fly
                self.assertEqual(outputmd5, md5zipsum)
                self.assertEqual(outputsha, shazipsum)
                self.assertEqual(outputsize, zipsize)
                # zipfiles aren't decompressed, so shouldn't change name
                self.assertEqual(outputfile, "10MB.zip")
                # we know it's 10MB.zip for download size test
                self.assertEqual(httpaction.size, 10109)
            else:
                self.assertEqual(outputmd5, md5sum)
                self.assertEqual(outputsha, sha256sum)
                self.assertEqual(outputsize, filesize)
                self.assertEqual(outputfile, "10MB")

    def test_bad_download_decompression(self):
        job = self.factory.create_kvm_job("sample_jobs/compression_bad.yaml")
        job.validate()

        http_download_actions = job.pipeline.find_all_actions(HttpDownloadAction)

        tests_dict = {action.key: action for action in http_download_actions}
        test_bad_sha256sum = tests_dict["test_bad_sha256sum"]
        test_xz_bad_format = tests_dict["test_xz_bad_format"]
        test_gz_bad_format = tests_dict["test_gz_bad_format"]
        test_bz2_bad_format = tests_dict["test_bz2_bad_format"]
        test_multiple_bad_checksums = tests_dict["test_multiple_bad_checksums"]

        with self.subTest("Test bad sha256sum"), self.assertRaisesRegex(
            JobError, "does not match"
        ):
            test_bad_sha256sum.validate()
            test_bad_sha256sum.run(None, None)

        with self.subTest("Test bad XZ format"), self.assertRaisesRegex(
            JobError, "subprocess exited with non-zero code"
        ):
            test_xz_bad_format.validate()
            test_xz_bad_format.run(None, None)

        with self.subTest("Test bad GZ format"), self.assertRaisesRegex(
            JobError, "subprocess exited with non-zero code"
        ):
            test_gz_bad_format.validate()
            test_gz_bad_format.run(None, None)

        with self.subTest("Test bad BZ2 format"), self.assertRaisesRegex(
            JobError, "subprocess exited with non-zero code"
        ):
            test_bz2_bad_format.validate()
            test_bz2_bad_format.run(None, None)

        with self.subTest("Test multiple bad checksums"), self.assertRaisesRegex(
            JobError, "md5.*does not match"
        ):
            test_multiple_bad_checksums.validate()
            test_multiple_bad_checksums.run(None, None)


class TestCompressionBinaries(TestCase):
    def test_compression_binaries(self) -> None:
        for compression_format in compress_command_map.keys():
            with self.subTest(compression=compression_format), TemporaryDirectory(
                f"test-{compression_format}"
            ) as tmp_dir:
                test_str = f"Hello, {compression_format}!"
                tmp_dir_path = Path(tmp_dir)
                test_file_path = tmp_dir_path / f"{compression_format}_test"
                test_file_path.write_text(test_str)
                outfile = Path(compress_file(str(test_file_path), compression_format))
                self.assertNotEqual(
                    outfile.read_bytes(),
                    b"",  # Check that at least some bytes are written
                )

                test_file_path.unlink()
                self.assertFalse(test_file_path.exists())

                decompress_file(str(outfile), compression_format)

                self.assertEqual(test_str, test_file_path.read_text())

    def test_decompression_error(self) -> None:
        with TemporaryDirectory("test-decompression-failure") as tmp_dir:
            tmp_dir_path = Path(tmp_dir)

            test_input_file = tmp_dir_path / "test.zstd"
            test_input_file.write_text("🤡🤡🤡🤡🤡🤡🤡🤡🤡🤡🤡🤡🤡🤡🤡🤡🤡")

            with self.assertRaisesRegex(JobError, r"unable to decompress.*exit code"):
                decompress_file(str(test_input_file), "zstd")

            with self.subTest("decompression OSError"), self.assertRaisesRegex(
                InfrastructureError, r"unable to decompress"
            ):
                decompress_file("does_not_exist_dir/does_not_exist.zstd", "zstd")

    def test_compression_error(self) -> None:
        with TemporaryDirectory("test-compression-failure") as tmp_dir:
            tmp_dir_path = Path(tmp_dir)

            with self.assertRaisesRegex(InfrastructureError, r"unable to compress"):
                compress_file(str(tmp_dir_path / "does_not_exist.zstd"), "zstd")

    def test_zip_multiple_files(self) -> None:
        with TemporaryDirectory("test-decompression-zip-multiple") as tmp_dir:
            tmp_dir_path = Path(tmp_dir)

            archive_path = tmp_dir_path / "foobar.zip"

            import zipfile

            with zipfile.ZipFile(archive_path, mode="x") as zf:
                with zf.open("foo.txt", mode="w") as foo_f:
                    foo_f.write(b"foo")

                with zf.open("bar.txt", mode="w") as foo_f:
                    foo_f.write(b"bar")

            decompress_file(str(archive_path), "zip")

            foo_file_path = tmp_dir_path / "foo.txt"
            self.assertTrue(foo_file_path.exists())
            self.assertEqual(foo_file_path.read_text(), "foo")

            bar_file_path = tmp_dir_path / "bar.txt"
            self.assertTrue(bar_file_path.exists())
            self.assertEqual(bar_file_path.read_text(), "bar")


class TestCpio(TestCase):
    def test_cpio_cycle(self) -> None:
        with TemporaryDirectory("test-cpio") as tmp_dir:
            tmp_dir_path = Path(tmp_dir)

            test_dir = tmp_dir_path / "foo"
            test_dir.mkdir()

            test_file = test_dir / "bar"
            test_file.write_text("foobar")

            newline_file = test_dir / "foo\nbar"
            newline_file.write_text("one\ntwo\n")

            archive_file = tmp_dir_path / "foo.cpio"

            output = cpio(str(test_dir), str(archive_file))

            # Check that cpio stderr was captured
            self.assertIn("block", output)

            unpack_dir = tmp_dir_path / "unpack"
            unpack_dir.mkdir()

            uncpio(str(archive_file), str(unpack_dir))

            self.assertEqual((unpack_dir / "bar").read_text(), "foobar")
            self.assertEqual((unpack_dir / "foo\nbar").read_text(), "one\ntwo\n")
