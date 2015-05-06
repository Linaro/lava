# Copyright (C) 2010, 2011 Linaro Limited
#
# Author: Zygmunt Krynicki <zygmunt.krynicki@linaro.org>
#
# This file is part of Lava Dashboard.
#
# Lava Dashboard is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License version 3
# as published by the Free Software Foundation
#
# Lava Dashboard is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with Lava Dashboard.  If not, see <http://www.gnu.org/licenses/>.
#
from django.core.files.base import ContentFile
from django.db import models, transaction, IntegrityError

import logging


class BundleManager(models.Manager):

    def create_with_content(self, bundle_stream, uploaded_by, content_filename, content):
        logger = logging.getLogger(__name__)
        logger.debug("Creating bundle object")
        bundle = self.create(
            bundle_stream=bundle_stream,
            uploaded_by=uploaded_by,
            is_deserialized=False,
            content_filename=content_filename)
        # XXX: this _can_ fail -- if content_sha1 is a duplicate
        logger.debug("Saving bundle object (this is safe so far)")
        bundle.save()
        try:
            logger.debug("saving bundle content (file) and bundle object")
            bundle.content.save("bundle-{0}".format(bundle.pk),
                                ContentFile(content))
        except IntegrityError as exc:
            logger.debug("integrity error: %r", exc)
            # https://docs.djangoproject.com/en/dev/topics/db/transactions/#handling-exceptions-within-postgresql-transactions
            # Explicit handling is relevant only if you're implementing your own transaction management.
            # This problem cannot occur in Django's default mode and atomic() handles it automatically.
            logger.debug("deleting content file")
            bundle.content.delete(save=False)
            raise
        else:
            return bundle


class TestRunDenormalizationManager(models.Manager):

    def create_from_test_run(self, test_run):
        from dashboard_app.models import TestResult
        stats = test_run.test_results.values('result').annotate(
            count=models.Count('result')).order_by()
        result = dict([
            (TestResult.RESULT_MAP[item['result']], item['count'])
            for item in stats])
        return self.create(
            test_run=test_run,
            count_pass=result.get('pass', 0),
            count_fail=result.get('fail', 0),
            count_skip=result.get('skip', 0),
            count_unknown=result.get('unknown', 0))
