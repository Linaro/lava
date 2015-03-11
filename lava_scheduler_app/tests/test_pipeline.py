import os
import yaml
import jinja2
import logging
from lava_scheduler_app.models import (
    Device,
    DeviceType,
    DeviceDictionary,
    JobPipeline,
    PipelineStore,
    TestJob,
    Tag,
    DevicesUnavailableException,
)
from django.db import models
from django_testscenarios.ubertest import TestCase
from django.contrib.auth.models import Group, Permission, User
from lava_scheduler_app.tests.test_submission import ModelFactory, TestCaseWithFactory


class YamlFactory(ModelFactory):
    """
    Override some factory functions to supply YAML instead of JSON
    The YAML **must** be valid for the current pipeline to be able to
    save a TestJob into the database. Hence kvm.yaml.
    """

    def make_fake_qemu_device(self, hostname='fakeqemu1'):
        qemu = DeviceDictionary(hostname=hostname)
        qemu.parameters = {'extends': 'kvm.yaml', 'arch': 'amd64'}
        qemu.save()

    def make_device_type(self, name='kvm', health_check_job=None):
        device_type = DeviceType.objects.create(
            name=name, health_check_job=health_check_job)
        device_type.save()
        return device_type

    def make_device(self, device_type=None, hostname=None, tags=None, is_public=True, **kw):
        if device_type is None:
            device_type = self.ensure_device_type()
        if hostname is None:
            hostname = self.getUniqueString()
        if tags and type(tags) != list:
            tags = []
        # a hidden device type will override is_public
        device = Device(device_type=device_type, is_public=is_public, hostname=hostname, is_pipeline=True, **kw)
        self.make_fake_qemu_device(hostname)
        if tags:
            device.tags = tags
        logging.debug("making a device of type %s %s %s with tags '%s'"
                      % (device_type, device.is_public, device.hostname, ", ".join([x.name for x in device.tags.all()])))
        device.save()
        return device

    def make_job_data(self, actions=[], **kw):
        sample_job_file = os.path.join(os.path.dirname(__file__), 'kvm.yaml')
        with open(sample_job_file, 'r') as test_support:
            data = yaml.load(test_support)
        data.update(kw)
        return data

    def make_job_json(self, **kw):
        return self.make_job_yaml(**kw)

    def make_job_yaml(self, **kw):
        return yaml.safe_dump(self.make_job_data(**kw))


class PipelineDeviceTags(TestCaseWithFactory):
    """
    Test the extraction of device tags from submission YAML
    Same tests as test_submission but converted to use and look for YAML.
    """
    def setUp(self):
        super(PipelineDeviceTags, self).setUp()
        self.factory = YamlFactory()
        self.device_type = self.factory.make_device_type()

    def test_make_job_yaml(self):
        data = yaml.load(self.factory.make_job_yaml())
        self.assertIn('device_type', data)
        self.assertNotIn('timeout', data)
        self.assertIn('timeouts', data)
        self.assertIn('job', data['timeouts'])

    def test_no_tags(self):
        self.factory.make_device(self.device_type, 'fakeqemu3')
        TestJob.from_yaml_and_user(
            self.factory.make_job_json(),
            self.factory.make_user())

    def test_yaml_device_tags(self):
        data = yaml.load(self.factory.make_job_yaml(tags=['usb', 'controller']))
        self.assertIn('tags', data)
        self.assertEqual(type(data['tags']), list)
        self.assertIn('usb', data['tags'])

    def test_undefined_tags(self):
        self.factory.make_device(self.device_type, 'fakeqemu1')
        self.assertRaises(
            yaml.YAMLError,
            TestJob.from_yaml_and_user,
            self.factory.make_job_json(tags=['tag1', 'tag2']),
            self.factory.make_user())

    def test_from_yaml_unsupported_tags(self):
        self.factory.make_device(self.device_type, 'fakeqemu1')
        self.factory.ensure_tag('usb')
        self.factory.ensure_tag('sata')
        try:
            TestJob.from_yaml_and_user(
                self.factory.make_job_json(tags=['usb', 'sata']),
                self.factory.make_user())
        except DevicesUnavailableException:
            pass
        else:
            self.fail("Device tags failure: job submitted without any devices supporting the requested tags")

    def test_from_yaml_and_user_sets_multiple_tag_from_device_tags(self):
        tag_list = [
            self.factory.ensure_tag('tag1'),
            self.factory.ensure_tag('tag2')
        ]
        self.factory.make_device(self.device_type, hostname='fakeqemu1', tags=tag_list)
        job = TestJob.from_yaml_and_user(
            self.factory.make_job_json(tags=['tag1', 'tag2']),
            self.factory.make_user())
        self.assertEqual(
            set(tag.name for tag in job.tags.all()), {'tag1', 'tag2'})

    def test_from_yaml_and_user_reuses_tag_objects(self):
        self.factory.ensure_tag('tag')
        tags = list(Tag.objects.filter(name='tag'))
        self.factory.make_device(device_type=self.device_type, hostname="fakeqemu1", tags=tags)
        job1 = TestJob.from_yaml_and_user(
            self.factory.make_job_json(tags=['tag']),
            self.factory.make_user())
        job2 = TestJob.from_yaml_and_user(
            self.factory.make_job_json(tags=['tag']),
            self.factory.make_user())
        self.assertEqual(
            set(tag.pk for tag in job1.tags.all()),
            set(tag.pk for tag in job2.tags.all()))

    def test_from_yaml_and_user_matches_available_tags(self):
        """
        Test that with more than one device of the requested type supporting
        tags, that the tag list set for the TestJob matches the list requested,
        not a shorter list from a different device or a combined list of multiple
        devices.
        """
        tag_list = [
            self.factory.ensure_tag('common_tag1'),
            self.factory.ensure_tag('common_tag2')
        ]
        self.factory.make_device(device_type=self.device_type, hostname="fakeqemu1", tags=tag_list)
        tag_list.append(self.factory.ensure_tag('unique_tag'))
        self.factory.make_device(device_type=self.device_type, hostname="fakeqemu2", tags=tag_list)
        job = TestJob.from_yaml_and_user(
            self.factory.make_job_json(tags=['common_tag1', 'common_tag2', 'unique_tag']),
            self.factory.make_user())
        self.assertEqual(
            set(tag for tag in job.tags.all()),
            set(tag_list)
        )


class TestPipelineSubmit(TestCaseWithFactory):

    def setUp(self):
        super(TestPipelineSubmit, self).setUp()
        self.factory = YamlFactory()
        self.device_type = self.factory.make_device_type()
        self.factory.make_device(device_type=self.device_type, hostname="fakeqemu1")

    def test_from_yaml_and_user_sets_definition(self):
        definition = self.factory.make_job_json()
        job = TestJob.from_yaml_and_user(definition, self.factory.make_user())
        self.assertEqual(definition, job.definition)

    def test_from_yaml_and_user_sets_submitter(self):
        user = self.factory.make_user()
        job = TestJob.from_yaml_and_user(
            self.factory.make_job_json(), user)
        self.assertEqual(user, job.submitter)


class TestPipelineStore(TestCaseWithFactory):

    def setUp(self):
        super(TestPipelineStore, self).setUp()
        self.factory = YamlFactory()
        self.device_type = self.factory.make_device_type()
        self.factory.make_device(device_type=self.device_type, hostname="fakeqemu1")

    def test_new_pipeline_store(self):
        user = self.factory.make_user()
        job = TestJob.from_yaml_and_user(
            self.factory.make_job_json(), user)
        foo = JobPipeline.get('foo')
        self.assertIsNone(foo)
        foo = JobPipeline.get(job.id)
        self.assertIsNotNone(foo)
        self.assertIsInstance(foo, JobPipeline)
        # pipeline.describe() needs to reparse as YAML
        yaml.load(foo.pipeline)
