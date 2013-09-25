# Copyright (C) 2010, 2011 Linaro Limited
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
#
from django.core.files.base import ContentFile
from django.db import models, transaction, IntegrityError

import logging


class BundleManager(models.Manager):

    @transaction.commit_on_success
    def create_with_content(self, bundle_stream, uploaded_by, content_filename, content):
        logging.debug("Creating bundle object")
        bundle = self.create(
                bundle_stream=bundle_stream,
                uploaded_by=uploaded_by,
                content_filename=content_filename)
        # XXX: this _can_ fail -- if content_sha1 is a duplicate
        logging.debug("Saving bundle object (this is safe so far)")
        bundle.save()
        try:
            logging.debug("saving bundle content (file) and bundle object")
            bundle.content.save("bundle-{0}".format(bundle.pk),
                                ContentFile(content))
        except IntegrityError as exc:
            logging.debug("integrity error: %r", exc)
            # Note: we're not saving the deletion back to the database
            # because we are going to rollback anyway. In PostgreSQL this
            # would also always fail because the database is not going to
            # honor any other operations until we rollback.
            # See: 
            # http://docs.djangoproject.com/en/1.2/topics/db/transactions/#handling-exceptions-within-postgresql-transactions
            logging.debug("deleting content file")
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
