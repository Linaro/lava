# Copyright (C) 2010 Linaro Limited
#
# Author: Zygmunt Krynicki <zygmunt.krynicki@linaro.org>
#
# This file is part of Launch Control.
#
# Launch Control is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License version 3
# as published by the Free Software Foundation
#
# Launch Control is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with Launch Control.  If not, see <http://www.gnu.org/licenses/>.

"""
Tests for the Attachment model
"""
from django.contrib.contenttypes import generic
from django.core.files.base import ContentFile
from django.db import models
from django.test import TestCase

from dashboard_app.models import Attachment


class ModelWithAttachments(models.Model):
    """
    Test model that uses attachments
    """
    attachments = generic.GenericRelation(Attachment)

    class Meta:
        app_label = "dashboard_app"


class AttachmentTestCase(TestCase):
    _CONTENT = "text"
    _FILENAME = "filename"

    def setUp(self):
        self.obj = ModelWithAttachments.objects.create()

    def test_attachment_can_be_added_to_models(self):
        attachment = self.obj.attachments.create(
            content_filename = self._FILENAME, content=None)
        self.assertEqual(attachment.content_object, self.obj)

    def test_attachment_can_be_accessed_via_model(self):
        self.obj.attachments.create(
            content_filename = self._FILENAME, content=None)
        self.assertEqual(self.obj.attachments.count(), 1)
        retrieved_attachment = self.obj.attachments.all()[0]
        self.assertEqual(retrieved_attachment.content_object, self.obj)

    def test_attachment_stores_data(self):
        attachment = self.obj.attachments.create(
            content_filename = self._FILENAME, content=None)
        attachment.content.save(
            self._FILENAME,
            ContentFile(self._CONTENT))
        self.assertEqual(attachment.content_filename, self._FILENAME)
        attachment.content.open()
        try:
            self.assertEqual(attachment.content.read(), self._CONTENT)
        finally:
            attachment.content.close()
            attachment.content.delete(save=False)

    def test_unicode(self):
        obj = Attachment(content_filename="test.json")
        self.assertEqual(unicode(obj), "test.json")
