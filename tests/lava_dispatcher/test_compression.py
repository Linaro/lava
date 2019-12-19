# Copyright (C) 2018 Linaro Limited
#
# Author: Matt Hart <matthew.hart@linaro.org>
#
# This file is part of LAVA Dispatcher.
#
# LAVA Dispatcher is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# LAVA Dispatcher is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along
# with this program; if not, see <http://www.gnu.org/licenses>.

import copy
import os
import hashlib
from lava_common.exceptions import InfrastructureError
from tests.lava_dispatcher.test_basic import Factory, StdoutTestCase
from lava_dispatcher.utils.compression import decompress_file
from lava_dispatcher.utils.compression import decompress_command_map


class TestDecompression(StdoutTestCase):
    def setUp(self):
        super().setUp()
        factory = Factory()
        self.job = factory.create_kvm_job("sample_jobs/compression.yaml")
        self.job.validate()

    def test_download_decompression(self):
        self.assertEqual(len(self.job.pipeline.describe()), 2)

        deployaction = [
            action
            for action in self.job.pipeline.actions
            if action.name == "deployimages"
        ][0]
        downloadactions = [
            action
            for action in deployaction.internal_pipeline.actions
            if action.name == "download-retry"
        ]
        self.assertEqual(len(downloadactions), 4)

        sha256sum = "31e00e0e4c233c89051cd748122fde2c98db0121ca09ba93a3820817ea037bc5"
        md5sum = "596c35b949baf46b721744a13f76a258"
        shazipsum = "27259c7aab942273931b71d1fa37e0c5115b6b0fcc969ee40c2e6bb1062af98f"
        md5zipsum = "ec769af027b3dd8145b75369bfb2698b"
        filesize = 10240000
        zipsize = 10109

        for downloadaction in downloadactions:
            httpaction = [
                action
                for action in downloadaction.internal_pipeline.actions
                if action.name == "http-download"
            ][0]
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

    def test_multiple_decompressions(self):
        """
        Previously had an issue with decompress_command_map being modified.
        This should be a constant. If this is modified during calling decompress_file
        then a regression has occurred.
        :return:
        """
        # Take a complete copy of decompress_command_map before it has been modified
        copy_of_command_map = copy.deepcopy(decompress_command_map)
        # Call decompress_file, we only need it to create the command required,
        # it doesn't need to complete successfully.
        with self.assertRaises(InfrastructureError):
            decompress_file("/tmp/test.xz", "zip")  # nosec - unit test only.
        self.assertEqual(copy_of_command_map, decompress_command_map)
