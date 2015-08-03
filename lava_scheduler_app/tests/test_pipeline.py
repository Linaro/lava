import os
import yaml
import jinja2
import logging
from lava_scheduler_app.models import (
    Device,
    DeviceType,
    DeviceDictionary,
    JobPipeline,
    TestJob,
    Tag,
    DevicesUnavailableException,
    _pipeline_protocols,
)
from django.db import models
from django_testscenarios.ubertest import TestCase
from django.contrib.auth.models import Group, Permission, User
from collections import OrderedDict
from lava_scheduler_app.utils import jinja_template_path, split_multinode_yaml
from lava_scheduler_app.tests.test_submission import ModelFactory, TestCaseWithFactory
from lava_dispatcher.pipeline.device import PipelineDevice
from lava_dispatcher.pipeline.parser import JobParser
from lava_dispatcher.pipeline.action import JobError


# pylint: disable=too-many-ancestors,too-many-public-methods,invalid-name,no-member


class YamlFactory(ModelFactory):
    """
    Override some factory functions to supply YAML instead of JSON
    The YAML **must** be valid for the current pipeline to be able to
    save a TestJob into the database. Hence qemu.yaml.
    """

    def make_fake_qemu_device(self, hostname='fakeqemu1'):  # pylint: disable=no-self-use
        qemu = DeviceDictionary(hostname=hostname)
        qemu.parameters = {'extends': 'qemu.yaml', 'arch': 'amd64'}
        qemu.save()

    def make_device_type(self, name='qemu', health_check_job=None):
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

    def make_job_data(self, actions=None, **kw):
        sample_job_file = os.path.join(os.path.dirname(__file__), 'qemu.yaml')
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
        jinja_template_path(system=False)
        self.device_type = self.factory.make_device_type()
        self.conf = {
            'arch': 'amd64',
            'extends': 'qemu.yaml',
            'mac_addr': '52:54:00:12:34:59',
            'memory': '256',
        }

    def test_make_job_yaml(self):
        data = yaml.load(self.factory.make_job_yaml())
        self.assertIn('device_type', data)
        self.assertNotIn('timeout', data)
        self.assertIn('timeouts', data)
        self.assertIn('job', data['timeouts'])

    def test_make_device(self):
        hostname = 'fakeqemu3'
        device_dict = DeviceDictionary(hostname=hostname)
        device_dict.parameters = self.conf
        device_dict.save()
        device = self.factory.make_device(self.device_type, hostname)
        self.assertEqual(device.device_type.name, 'qemu')
        job = self.factory.make_job_yaml()
        self.assertIsNotNone(job)

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

    def test_invalid_device(self):
        user = self.factory.make_user()
        job = TestJob.from_yaml_and_user(
            self.factory.make_job_json(), user)
        job_def = yaml.load(job.definition)
        job_ctx = job_def.get('context', {})
        device = Device.objects.get(hostname='fakeqemu1')
        device_config = device.load_device_configuration(job_ctx)  # raw dict
        del device_config['device_type']
        parser = JobParser()
        obj = PipelineDevice(device_config, device.hostname)  # equivalent of the NewDevice in lava-dispatcher, without .yaml file.
        self.assertRaises(KeyError, parser.parse, job.definition, obj, job.id, None, output_dir='/tmp')

    def test_exclusivity(self):
        device = Device.objects.get(hostname="fakeqemu1")
        self.assertTrue(device.is_pipeline)
        self.assertFalse(device.is_exclusive)
        self.assertIsNotNone(DeviceDictionary.get(device.hostname))
        device_dict = DeviceDictionary(hostname=device.hostname)
        device_dict.save()
        device_dict = DeviceDictionary.get(device.hostname)
        self.assertTrue(device.is_pipeline)
        self.assertFalse(device.is_exclusive)
        update = device_dict.to_dict()
        update.update({'exclusive': 'True'})
        device_dict.parameters = update
        device_dict.save()
        self.assertTrue(device.is_pipeline)
        self.assertTrue(device.is_exclusive)


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
        store = JobPipeline.get('foo')
        self.assertIsNone(store)
        store = JobPipeline.get(job.id)
        self.assertIsNotNone(store)
        self.assertIsInstance(store, JobPipeline)
        self.assertIs(type(store.pipeline), dict)

    def test_pipeline_results(self):
        result_sample = """
- results: !!python/object/apply:collections.OrderedDict
  - - [linux-linaro-ubuntu-pwd, pass]
    - [linux-linaro-ubuntu-uname, pass]
    - [linux-linaro-ubuntu-vmstat, pass]
    - [linux-linaro-ubuntu-ifconfig, pass]
    - [linux-linaro-ubuntu-lscpu, pass]
    - [linux-linaro-ubuntu-lsb_release, pass]
    - [linux-linaro-ubuntu-netstat, pass]
    - [linux-linaro-ubuntu-ifconfig-dump, pass]
    - [linux-linaro-ubuntu-route-dump-a, pass]
    - [linux-linaro-ubuntu-route-ifconfig-up-lo, pass]
    - [linux-linaro-ubuntu-route-dump-b, pass]
    - [linux-linaro-ubuntu-route-ifconfig-up, pass]
    - [ping-test, fail]
    - [realpath-check, fail]
    - [ntpdate-check, pass]
    - [curl-ftp, pass]
    - [tar-tgz, pass]
    - [remove-tgz, pass]
        """
        result_store = {
            'result_sample': OrderedDict([
                ('linux-linaro-ubuntu-pwd', 'pass'),
                ('linux-linaro-ubuntu-uname', 'pass'),
                ('linux-linaro-ubuntu-vmstat', 'pass'),
                ('linux-linaro-ubuntu-ifconfig', 'pass'),
                ('linux-linaro-ubuntu-lscpu', 'pass'),
                ('linux-linaro-ubuntu-lsb_release', 'pass'),
                ('linux-linaro-ubuntu-netstat', 'pass'),
                ('linux-linaro-ubuntu-ifconfig-dump', 'pass'),
                ('linux-linaro-ubuntu-route-dump-a', 'pass'),
                ('linux-linaro-ubuntu-route-ifconfig-up-lo', 'pass'),
                ('linux-linaro-ubuntu-route-dump-b', 'pass'),
                ('linux-linaro-ubuntu-route-ifconfig-up', 'pass'),
                ('ping-test', 'fail'),
                ('realpath-check', 'fail'),
                ('ntpdate-check', 'pass'),
                ('curl-ftp', 'pass'),
                ('tar-tgz', 'pass'),
                ('remove-tgz', 'pass')])}
        name = "result_sample"
        user = self.factory.make_user()
        job = TestJob.from_yaml_and_user(
            self.factory.make_job_json(), user)
        store = JobPipeline.get(job.id)
        scanned = yaml.load(result_sample)
        if type(scanned) is list and len(scanned) == 1:
            if 'results' in scanned[0] and type(scanned[0]) is dict:
                store.pipeline.update({name: scanned[0]['results']})
                # too often to save the results?
                store.save()
        self.assertIsNotNone(store.pipeline)
        self.assertIsNot({}, store.pipeline)
        self.assertIs(type(store.pipeline), dict)
        self.assertIn('result_sample', store.pipeline)
        self.assertIs(type(store.pipeline['result_sample']), OrderedDict)
        self.assertEqual(store.pipeline, result_store)


class TestYamlMultinode(TestCaseWithFactory):

    def setUp(self):
        super(TestYamlMultinode, self).setUp()
        self.factory = YamlFactory()

    def test_multinode_split(self):
        """
        Test just the split of pipeline YAML

        This function does not test the content of 'roles' as this needs information
        which is only available after the devices have been reserved.
        """
        server_check = os.path.join(os.path.dirname(__file__), 'kvm-multinode-server.yaml')
        client_check = os.path.join(os.path.dirname(__file__), 'kvm-multinode-client.yaml')
        submission = yaml.load(open(
            os.path.join(os.path.dirname(__file__), 'kvm-multinode.yaml'), 'r'))
        target_group = 'arbitrary-group-id'  # for unit tests only

        jobs = split_multinode_yaml(submission, target_group)
        self.assertEqual(len(jobs), 2)
        for role, job_list in jobs.items():
            for job in job_list:
                yaml.dump(job)  # ensure the jobs can be serialised as YAML
                role = job['protocols']['lava-multinode']['role']
                if role == 'client':
                    self.assertEqual(job, yaml.load(open(client_check, 'r')))
                if role == 'server':
                    self.assertEqual(job, yaml.load(open(server_check, 'r')))

    def test_multinode_protocols(self):
        user = self.factory.make_user()
        self.device_type = self.factory.make_device_type()
        submission = yaml.load(open(
            os.path.join(os.path.dirname(__file__), 'kvm-multinode.yaml'), 'r'))
        # no devices defined for the specified type
        self.assertRaises(DevicesUnavailableException, _pipeline_protocols, submission, user, yaml_data=None)

        self.factory.make_device(self.device_type, 'fakeqemu1')
        # specified tags do not exist
        self.assertRaises(yaml.YAMLError, _pipeline_protocols, submission, user)

        tag_list = [
            self.factory.ensure_tag('usb-flash'),
            self.factory.ensure_tag('usb-eth')
        ]
        self.factory.make_device(self.device_type, 'fakeqemu2')
        # no devices which have the required tags applied
        self.assertRaises(DevicesUnavailableException, _pipeline_protocols, submission, user, yaml_data=None)

        self.factory.make_device(self.device_type, 'fakeqemu3', tags=tag_list)
        job_object_list = _pipeline_protocols(submission, user)
        self.assertEqual(len(job_object_list), 2)
        for job in job_object_list:
            self.assertEqual(list(job.sub_jobs_list), job_object_list)
            check = yaml.load(job.definition)
            if check['protocols']['lava-multinode']['role'] == 'client':
                self.assertEqual(
                    check['protocols']['lava-multinode']['tags'],
                    ['usb-flash', 'usb-eth'])
                self.assertEqual(
                    check['protocols']['lava-multinode']['interfaces'],
                    [{'vlan': 'name_two', 'tags': ['10G']}, {'vlan': 'name_two', 'tags': ['1G']}]
                )
                self.assertEqual(set(tag_list), set(job.tags.all()))
            if check['protocols']['lava-multinode']['role'] == 'server':
                self.assertNotIn('tags', check['protocols']['lava-multinode'])
                self.assertNotIn('interfaces', check['protocols']['lava-multinode'])
                self.assertEqual(set([]), set(job.tags.all()))

    def test_multinode_group(self):
        user = self.factory.make_user()
        self.device_type = self.factory.make_device_type()
        submission = yaml.load(open(
            os.path.join(os.path.dirname(__file__), 'kvm-multinode.yaml'), 'r'))
        self.factory.make_device(self.device_type, 'fakeqemu1')
        tag_list = [
            self.factory.ensure_tag('usb-flash'),
            self.factory.ensure_tag('usb-eth')
        ]
        self.factory.make_device(self.device_type, 'fakeqemu2', tags=tag_list)
        job_object_list = _pipeline_protocols(submission, user, yaml.dump(submission))
        for job in job_object_list:
            self.assertEqual(list(job.sub_jobs_list), job_object_list)
        check_one = yaml.load(job_object_list[0].definition)
        check_two = yaml.load(job_object_list[1].definition)
        self.assertEqual(
            job_object_list[0].target_group,
            job_object_list[1].target_group
        )
        # job 0 needs to have a sub_id of <id>.0
        # job 1 needs to have a sub_id of <id>.1 despite job 1 id being <id>+1
        self.assertEqual(int(job_object_list[0].id), int(float(job_object_list[0].sub_id)))
        self.assertEqual(int(job_object_list[0].id) + 1, int(job_object_list[1].id))
        self.assertEqual(
            job_object_list[0].sub_id,
            "%d.%d" % (int(job_object_list[0].id), 0))
        self.assertEqual(
            job_object_list[1].sub_id,
            "%d.%d" % (int(job_object_list[0].id), 1))
        self.assertNotEqual(
            job_object_list[1].sub_id,
            "%d.%d" % (int(job_object_list[1].id), 0))
        self.assertNotEqual(
            job_object_list[1].sub_id,
            "%d.%d" % (int(job_object_list[1].id), 1))
        self.assertNotEqual(
            check_one['protocols']['lava-multinode']['role'],
            check_two['protocols']['lava-multinode']['role']
        )

    def test_multinode_definition(self):
        user = self.factory.make_user()
        self.device_type = self.factory.make_device_type()
        submission = yaml.load(open(
            os.path.join(os.path.dirname(__file__), 'kvm-multinode.yaml'), 'r'))
        self.factory.make_device(self.device_type, 'fakeqemu1')
        self.factory.make_device(self.device_type, 'fakeqemu2')
        tag_list = [
            self.factory.ensure_tag('usb-flash'),
            self.factory.ensure_tag('usb-eth')
        ]
        self.factory.make_device(self.device_type, 'fakeqemu3', tags=tag_list)
        job_object_list = _pipeline_protocols(submission, user, None)
        for job in job_object_list:
            self.assertIsNotNone(job.multinode_definition)
            self.assertNotIn('#', job.multinode_definition)
        with open(os.path.join(os.path.dirname(__file__), 'kvm-multinode.yaml'), 'r') as source:
            yaml_str = source.read()
        self.assertIn('# unit test support comment', yaml_str)
        job_object_list = _pipeline_protocols(submission, user, yaml_str)
        for job in job_object_list:
            self.assertIsNotNone(job.multinode_definition)
            self.assertIn('# unit test support comment', job.multinode_definition)

    def test_invalid_multinode(self):
        user = self.factory.make_user()
        self.device_type = self.factory.make_device_type()
        submission = yaml.load(open(
            os.path.join(os.path.dirname(__file__), 'kvm-multinode.yaml'), 'r'))

        tag_list = [
            self.factory.ensure_tag('usb-flash'),
            self.factory.ensure_tag('usb-eth')
        ]
        self.factory.make_device(self.device_type, 'fakeqemu1')
        self.factory.make_device(self.device_type, 'fakeqemu2')
        self.factory.make_device(self.device_type, 'fakeqemu3', tags=tag_list)
        deploy = [action['deploy'] for action in submission['actions'] if 'deploy' in action]
        # replace working image with a broken URL
        for block in deploy:
            block['image'] = 'http://localhost/unknown/invalid.gz'
        job_object_list = _pipeline_protocols(submission, user, yaml.dump(submission))
        self.assertEqual(len(job_object_list), 2)
        self.assertEqual(
            job_object_list[0].sub_id,
            "%d.%d" % (int(job_object_list[0].id), 0))
        # FIXME: dispatcher master needs to make this kind of test more accessible.
        for job in job_object_list:
            definition = yaml.load(job.definition)
            self.assertNotEqual(definition['protocols']['lava-multinode']['sub_id'], '')
            job.actual_device = Device.objects.get(hostname='fakeqemu1')
            job_def = yaml.load(job.definition)
            job_ctx = job_def.get('context', {})
            parser = JobParser()
            device = None
            device_object = None
            if not job.dynamic_connection:
                device = job.actual_device

                try:
                    device_config = device.load_device_configuration(job_ctx)  # raw dict
                except (jinja2.TemplateError, yaml.YAMLError, IOError) as exc:
                    # FIXME: report the exceptions as useful user messages
                    self.fail("[%d] jinja2 error: %s" % (job.id, exc))
                if not device_config or type(device_config) is not dict:
                    # it is an error to have a pipeline device without a device dictionary as it will never get any jobs.
                    msg = "Administrative error. Device '%s' has no device dictionary." % device.hostname
                    self.fail('[%d] device-dictionary error: %s' % (job.id, msg))

                device_object = PipelineDevice(device_config, device.hostname)  # equivalent of the NewDevice in lava-dispatcher, without .yaml file.
                # FIXME: drop this nasty hack once 'target' is dropped as a parameter
                if 'target' not in device_object:
                    device_object.target = device.hostname
                device_object['hostname'] = device.hostname

            validate_list = job.sub_jobs_list if job.is_multinode else [job]
            for check_job in validate_list:
                parser_device = None if job.dynamic_connection else device_object
                try:
                    # pass (unused) output_dir just for validation as there is no zmq socket either.
                    pipeline_job = parser.parse(
                        check_job.definition, parser_device,
                        check_job.id, None, output_dir=check_job.output_dir)
                except (AttributeError, JobError, NotImplementedError, KeyError, TypeError) as exc:
                    self.fail('[%s] parser error: %s' % (check_job.sub_id, exc))
                if os.path.exists('/dev/loop0'):  # rather than skipping the entire test, just the validation.
                    self.assertRaises(JobError, pipeline_job.pipeline.validate_actions)
        for job in job_object_list:
            job = TestJob.objects.get(id=job.id)
            self.assertNotEqual(job.sub_id, '')
