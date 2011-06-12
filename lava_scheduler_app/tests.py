import datetime
import json

from django.contrib.auth.models import User
from django.test import TestCase

from lava_scheduler_app.models import Device, DeviceType, TestJob

import cStringIO

from xmlrpclib import ServerProxy, Transport

from django.test.client import Client

class TestTransport(Transport):

    """ Handles connections to XML-RPC server through Django test client."""

    def __init__(self, user=None, password=None):

        self.client = Client()
        if user:
            self.client.login(user=user, password=password)
        self._use_datetime = True

    def request(self, host, handler, request_body, verbose=0):

        self.verbose = verbose

        response = self.client.post(handler,
                                    request_body,
                                    content_type="text/xml")

        res = cStringIO.StringIO(response.content)
        res.seek(0)

        return self.parse_response(res)


class TestTestJob(TestCase):

    def make_user(self):
        return User.objects.create_user(
            'username', 'e@mail.invalid', 'password')

    def test_from_json_and_user_sets_definition(self):
        DeviceType.objects.get_or_create(name='panda')
        definition = {'device_type':'panda'}
        job = TestJob.from_json_and_user(
            json.dumps(definition), self.make_user())
        self.assertEqual(definition, job.definition)

    def test_from_json_and_user_sets_submitter(self):
        DeviceType.objects.get_or_create(name='panda')
        user = self.make_user()
        job = TestJob.from_json_and_user(
            json.dumps({'device_type':'panda'}), user)
        self.assertEqual(user, job.submitter)

    def test_from_json_and_user_sets_device_type(self):
        panda_type = DeviceType.objects.get_or_create(name='panda')[0]
        job = TestJob.from_json_and_user(
            json.dumps({'device_type':'panda'}), self.make_user())
        self.assertEqual(panda_type, job.device_type)

    def test_from_json_and_user_sets_target(self):
        panda_type = DeviceType.objects.get_or_create(name='panda')[0]
        panda_board = Device(device_type=panda_type, hostname='panda01')
        panda_board.save()
        job = TestJob.from_json_and_user(
            json.dumps({'target':'panda01'}), self.make_user())
        self.assertEqual(panda_board, job.target)

    def test_from_json_and_user_sets_device_type_from_target(self):
        panda_type = DeviceType.objects.get_or_create(name='panda')[0]
        Device(device_type=panda_type, hostname='panda').save()
        job = TestJob.from_json_and_user(
            json.dumps({'target':'panda'}), self.make_user())
        self.assertEqual(panda_type, job.device_type)

    def test_from_json_and_user_sets_date_submitted(self):
        DeviceType.objects.get_or_create(name='panda')
        before = datetime.datetime.now()
        job = TestJob.from_json_and_user(
            json.dumps({'device_type':'panda'}), self.make_user())
        after = datetime.datetime.now()
        self.assertTrue(before < job.submit_time < after)

    def test_from_json_and_user_sets_status_to_SUBMITTED(self):
        DeviceType.objects.get_or_create(name='panda')
        job = TestJob.from_json_and_user(
            json.dumps({'device_type':'panda'}), self.make_user())
        self.assertEqual(job.status, TestJob.SUBMITTED)


class TestSchedulerAPI(TestCase):

    def server_proxy(self, user=None, password=None):
        return ServerProxy('http://localhost/RPC2/', transport=TestTransport(user=user, password=password))

    def test_api_rejects_anonymous(self):
        server = self.server_proxy()
        server.scheduler.submit_job("{}")
