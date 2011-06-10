"""
This file demonstrates two different styles of tests (one doctest and one
unittest). These will both pass when you run "manage.py test".

Replace these with more appropriate tests for your application.
"""

from django.contrib.auth.models import User
from django.test import TestCase

from lava_scheduler_app.models import TestJob


class TestTestJob(TestCase):

    def test_from_json_and_user(self):
        user = User.objects.create_user(
            'john', 'lennon@thebeatles.com', 'johnpassword')
        job = TestJob.from_json_and_user({}, user)
        self.assertEqual(user, job.submitter)
