import json

from django.contrib.auth.models import User
from django.test import TestCase

from lava_scheduler_app.models import DeviceType, TestJob


class TestTestJob(TestCase):

    def test_from_json_and_user(self):
        DeviceType.objects.get_or_create(name='panda')
        user = User.objects.create_user(
            'john', 'lennon@thebeatles.com', 'johnpassword')
        job = TestJob.from_json_and_user(
            json.dumps({'device_type':'panda'}), user)
        self.assertEqual(user, job.submitter)
