# Copyright (C) 2010, 2011 Linaro Limited
#
# Author: Zygmunt Krynicki <zygmunt.krynicki@linaro.org>
#
# This file is part of linaro-dashboard-bundle.
#
# linaro-dashboard-bundle is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License version 3
# as published by the Free Software Foundation
#
# linaro-dashboard-bundle is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with linaro-dashboard-bundle.  If not, see <http://www.gnu.org/licenses/>.


import base64


class DocumentEvolution(object):
    """
    Document Evolution encapsulates format changes between subsequent
    document format versions. This is useful when your code is designed
    to handle single, for example the most recent, format of the
    document but would like to interact with any previous format
    transparently.
    """

    @classmethod
    def is_latest(cls, doc):
        """
        Check if the document is at the latest known version
        """
        # The last element of the evolution path, the second item in the
        # tuple is final format
        return cls.EVOLUTION_PATH[-1][1] == doc.get("format")

    @classmethod
    def evolve_document(cls, doc, one_step=False):
        """
        Evolve document to the latest known version.

        Runs an in-place evolution of the document `doc` converting it
        to more recent versions. The conversion process is lossless.

        :param doc: document (changed in place)
        :type doc: JSON document, usually python dictionary
        :param one_step: if true then just one step of the evolution path is taken before exiting.
        :rtype: None
        """
        for src_fmt, dst_fmt, convert_fn in cls.EVOLUTION_PATH:
            if doc.get("format") == src_fmt:
                convert_fn(doc)
                if one_step:
                    break

    def _evolution_from_1_0_to_1_0_1(doc):
        """
        Evolution method for 1.0 -> 1.0.1:

            * TestRun's sw_context is changed to software_context
            * TestRun's hw_context is changed to hardware_context
            * Format is upgraded to "Dashboard Bundle Format 1.0.1"
        """
        assert doc.get("format") == "Dashboard Bundle Format 1.0"
        for test_run in doc.get("test_runs", []):
            if "hw_context" in test_run:
                test_run["hardware_context"] = test_run["hw_context"]
                del test_run["hw_context"]
            if "sw_context" in test_run:
                test_run["software_context"] = test_run["sw_context"]
                del test_run["sw_context"]
        doc["format"] = "Dashboard Bundle Format 1.0.1"

    def _evolution_from_1_0_1_to_1_1(doc):
        """
        Evolution method for 1.0.1 -> 1.1:

            * SoftwareContext "sw_image" is changed to "image"
            * SoftwareContext "image"."desc" is changed to "name"
            * Attachments are converted to new format, see below for details
            * Format is upgraded to "Dashboard Bundle Format 1.1"

        Attachment storage in 1.1 format

            Previously all attachments were plain-text files. They were stored
            in a dictionary where the name denoted the pathname of the attachment
            and the value was an array-of-strings. Each array item was a separate
            line from the text file. Line terminators were preserved.
            
            The new format is much more flexible and allows to store binary
            files and their mime type. The format stores attachments as an
            array of objects. Each attachment object has tree mandatory
            properties (pathname, contents (base64), and mime_type).

            All existing attachments are migrated to "text/plain" mime type.
            All strings that were previously unicode are encoded to UTF-8,
            concatenated and encoded as base64 (RFC3548) string with standard
            encoding. Previously attachments would be in arbitrary order as
            python dictionaries are not oder-preserving (and indeed json
            recommends that implementations need not retain ordering), in the
            new format attachments are sorted by pathname (just once during the
            conversion process, not in general)
        """
        assert doc.get("format") == "Dashboard Bundle Format 1.0.1"
        for test_run in doc.get("test_runs", []):
            if "software_context" in test_run:
                software_context = test_run["software_context"]
                if "sw_image" in software_context:
                    image = software_context["image"] = software_context["sw_image"]
                    del software_context["sw_image"]
                    if "desc" in image:
                        image["name"] = image["desc"]
                        del image["desc"]
            if "attachments" in test_run:
                legacy_attachments = test_run["attachments"]
                attachments = []
                for pathname in sorted(legacy_attachments.iterkeys()):
                    content = base64.standard_b64encode(
                        r''.join(
                            (line.encode('UTF-8') for line in legacy_attachments[pathname])
                        )
                    )
                    attachment = {
                        "mime_type": "text/plain",
                        "pathname": pathname,
                        "content": content
                    }
                    attachments.append(attachment)
                test_run["attachments"] = attachments
        doc["format"] = "Dashboard Bundle Format 1.1"

    def _evolution_from_1_1_to_1_2(doc):
        """
        Evolution method for 1.1 -> 1.2:
            
            * No changes required
        """
        assert doc.get("format") == "Dashboard Bundle Format 1.1"
        doc["format"] = "Dashboard Bundle Format 1.2"

    EVOLUTION_PATH = [
        ("Dashboard Bundle Format 1.0",
         "Dashboard Bundle Format 1.0.1",
         _evolution_from_1_0_to_1_0_1),
        ("Dashboard Bundle Format 1.0.1",
         "Dashboard Bundle Format 1.1",
         _evolution_from_1_0_1_to_1_1),
        ("Dashboard Bundle Format 1.1",
         "Dashboard Bundle Format 1.2",
         _evolution_from_1_1_to_1_2),
    ]
