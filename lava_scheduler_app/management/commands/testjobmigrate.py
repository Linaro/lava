import sys

from django.core.management.base import BaseCommand
from django.db.models import Q

from dashboard_app.models import Bundle
from lava_scheduler_app.models import TestJob


class Command(BaseCommand):

    help = "Fill out results_bundle on old testjobs."

    option_list = BaseCommand.option_list

    def handle(self, *args, **options):
        count = 0
        query = TestJob.objects.filter(
            ~Q(_results_link=u''), _results_link__isnull=False,
            _results_bundle__isnull=True)
        print query.count()
        for job in query.all():
            count += 1
            if count % 100 == 0:
                sys.stdout.write('.')
                sys.stdout.flush()
            sha1 = job.results_link.strip('/').split('/')[-1]
            try:
                bundle = Bundle.objects.get(content_sha1=sha1)
            except Bundle.DoesNotExist:
                continue
            job._results_bundle = bundle
            job.save()
        print
