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
    _check_submit_to_device,
)
from lava_scheduler_app.dbutils import match_vlan_interface
from django.db.models import Q
from django.contrib.auth.models import Group, Permission, User
from collections import OrderedDict
from lava_scheduler_app.utils import (
    jinja_template_path,
    map_context_overrides,
    allowed_overrides,
    split_multinode_yaml,
)
from lava_scheduler_app.tests.test_submission import ModelFactory, TestCaseWithFactory
from lava_scheduler_app.dbutils import testjob_submission, find_device_for_job
from lava_dispatcher.pipeline.device import PipelineDevice
from lava_dispatcher.pipeline.parser import JobParser
from lava_dispatcher.pipeline.action import JobError
from lava_dispatcher.pipeline.actions.boot.qemu import BootQEMU
from lava_dispatcher.pipeline.protocols.multinode import MultinodeProtocol
from django_restricted_resource.managers import RestrictedResourceQuerySet


# pylint: disable=too-many-ancestors,too-many-public-methods,invalid-name,no-member


class YamlFactory(ModelFactory):
    """
    Override some factory functions to supply YAML instead of JSON
    The YAML **must** be valid for the current pipeline to be able to
    save a TestJob into the database. Hence qemu.yaml.
    """

    def make_fake_qemu_device(self, hostname='fakeqemu1'):  # pylint: disable=no-self-use
        qemu = DeviceDictionary(hostname=hostname)
        qemu.parameters = {'extends': 'qemu.jinja2', 'arch': 'amd64'}
        qemu.save()

    def make_device_type(self, name='qemu', health_check_job=None):

        device_type = DeviceType.objects.get_or_create(
            name=name, health_check_job=health_check_job)[0]
        device_type.save()
        return device_type

    def make_device(self, device_type=None, hostname=None, tags=None, is_public=True, **kw):
        if device_type is None:
            device_type = self.ensure_device_type()
        if hostname is None:
            hostname = self.getUniqueString()
        if tags and not isinstance(tags, list):
            tags = []
        # a hidden device type will override is_public
        device = Device(device_type=device_type, is_public=is_public, hostname=hostname, is_pipeline=True, **kw)
        self.make_fake_qemu_device(hostname)
        if tags:
            device.tags = tags
        logging.debug("making a device of type %s %s %s with tags '%s'",
                      device_type, device.is_public, device.hostname, ", ".join([x.name for x in device.tags.all()]))
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
            'extends': 'qemu.jinja2',
            'mac_addr': '52:54:00:12:34:59',
            'memory': '256',
        }

    def test_make_job_yaml(self):
        data = yaml.load(self.factory.make_job_yaml())
        self.assertIn('device_type', data)
        self.assertNotIn('timeout', data)
        self.assertIn('timeouts', data)
        self.assertIn('job', data['timeouts'])
        self.assertIn('context', data)
        self.assertEqual(data['context']['arch'], self.conf['arch'])

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
        Tag.objects.all().delete()
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
        self.assertFalse(job.health_check)

    def test_pipeline_health_check(self):
        user = self.factory.make_user()
        device = Device.objects.get(hostname='fakeqemu1')
        job = testjob_submission(self.factory.make_job_yaml(), user, check_device=None)
        self.assertEqual(user, job.submitter)
        self.assertFalse(job.health_check)
        self.assertIsNone(job.requested_device)
        job = testjob_submission(self.factory.make_job_yaml(), user, check_device=device)
        self.assertEqual(user, job.submitter)
        self.assertTrue(job.health_check)
        self.assertEqual(job.requested_device, device)
        self.assertIsNone(job.actual_device)

    def test_pipeline_health_assignment(self):
        user = self.factory.make_user()
        device1 = Device.objects.get(hostname='fakeqemu1')
        self.factory.make_fake_qemu_device(hostname="fakeqemu1")
        self.assertTrue(device1.is_pipeline)
        device2 = self.factory.make_device(device_type=device1.device_type, hostname='fakeqemu2')
        self.factory.make_fake_qemu_device(hostname="fakeqemu2")
        self.assertTrue(device2.is_pipeline)
        device3 = self.factory.make_device(device_type=device1.device_type, hostname='fakeqemu3')
        self.factory.make_fake_qemu_device(hostname="fakeqemu3")
        self.assertTrue(device3.is_pipeline)
        job1 = testjob_submission(self.factory.make_job_yaml(), user, check_device=device1)
        job2 = testjob_submission(self.factory.make_job_yaml(), user, check_device=device2)
        self.assertEqual(user, job1.submitter)
        self.assertTrue(job1.health_check)
        self.assertEqual(job1.requested_device, device1)
        self.assertEqual(job2.requested_device, device2)
        self.assertIsNone(job1.actual_device)
        self.assertIsNone(job2.actual_device)
        device_list = Device.objects.filter(device_type=device1.device_type)
        count = 0
        while True:
            device_list.reverse()
            assigned = find_device_for_job(job2, device_list)
            if assigned != device2:
                self.fail("[%d] invalid device assigment in health check." % count)
            count += 1
            if count > 100:
                break
        self.assertGreater(count, 100)

    def test_invalid_device(self):
        user = self.factory.make_user()
        job = TestJob.from_yaml_and_user(
            self.factory.make_job_json(), user)
        job_def = yaml.load(job.definition)
        job_ctx = job_def.get('context', {})
        device = Device.objects.get(hostname='fakeqemu1')
        device_config = device.load_device_configuration(job_ctx, system=False)  # raw dict
        del device_config['device_type']
        parser = JobParser()
        obj = PipelineDevice(device_config, device.hostname)  # equivalent of the NewDevice in lava-dispatcher, without .yaml file.
        self.assertRaises(KeyError, parser.parse, job.definition, obj, job.id, None, None, None, output_dir='/tmp')

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

    def test_context(self):
        """
        Test overrides using the job context

        Defaults in the device-type can be overridden by the device dictionary.
        If not overridden by the device dictionary, can be overridden by the job context.
        If the
        """
        device = Device.objects.get(hostname="fakeqemu1")
        user = self.factory.make_user()
        job = TestJob.from_yaml_and_user(
            self.factory.make_job_json(), user)
        job_def = yaml.load(job.definition)
        job_ctx = job_def.get('context', {})
        device_config = device.load_device_configuration(job_ctx, system=False)  # raw dict
        self.assertEqual(
            device_config['actions']['boot']['methods']['qemu']['parameters']['command'],
            'qemu-system-x86_64'
        )

        job_data = yaml.load(self.factory.make_job_yaml())
        job_data['context'].update({'netdevice': 'tap'})
        job_ctx = job_data.get('context', {})
        device_config = device.load_device_configuration(job_ctx, system=False)  # raw dict
        opts = ' '.join(device_config['actions']['boot']['methods']['qemu']['parameters']['options'])
        self.assertIn('-net tap', opts)

        hostname = "fakemustang"
        mustang_type = self.factory.make_device_type('mustang-uefi')
        # this sets a qemu device dictionary, so replace it
        self.factory.make_device(device_type=mustang_type, hostname=hostname)
        mustang = DeviceDictionary(hostname=hostname)
        mustang.parameters = {
            'extends': 'mustang-uefi.jinja2',
            'base_nfsroot_args': '10.16.56.2:/home/lava/debian/nfs/,tcp,hard,intr',
            'console_device': 'ttyO0',  # takes precedence over the job context as the same var name is used.
        }
        mustang.save()

        device = Device.objects.get(hostname="fakemustang")
        self.assertEqual('mustang-uefi', device.device_type.name)
        self.assertTrue(device.is_pipeline)
        job_ctx = {
            'tftp_mac': 'FF:01:00:69:AA:CC',
            'nfsroot_args': '172.164.56.2:/home/user/nfs/,tcp,hard,intr',
            'console_device': 'ttyAMX0',
        }
        device_config = device.load_device_configuration(job_ctx, system=False)  # raw dict
        self.assertIn('uefi-menu', device_config['actions']['boot']['methods'])
        self.assertIn('nfs', device_config['actions']['boot']['methods']['uefi-menu'])
        menu_data = device_config['actions']['boot']['methods']['uefi-menu']['nfs']
        self.assertIn(
            job_ctx['nfsroot_args'],
            [
                item['select']['enter'] for item in menu_data if 'enter' in item['select'] and
                'new Entry' in item['select']['wait']][0]
        )
        self.assertEqual(
            [
                item['select']['items'][0] for item in menu_data if 'select' in item and
                'items' in item['select'] and 'TFTP' in item['select']['items'][0]][0],
            'TFTP on MAC Address: FF:01:00:69:AA:CC'  # matches the job_ctx
        )
        # note: the console_device and tftp_mac in the job_ctx has been *ignored* because the device type template
        # has not allowed the job_ctx to use a different name for the variable and the variable is
        # already defined in the device dictionary using the specified name. If the device dictionary lacked
        # the variable, the job could set it to override the device type template default, as shown by the
        # override of the base_nfsroot_args by allowing nfsroot_args in the device type template..
        self.assertEqual(
            [
                item['select']['enter'] for item in menu_data if 'select' in item and
                'wait' in item['select'] and 'Description' in item['select']['wait']][0],
            'console=ttyO0,115200 earlyprintk=uart8250-32bit,0x1c020000 debug '
            'root=/dev/nfs rw 172.164.56.2:/home/user/nfs/,tcp,hard,intr ip=dhcp'
        )

    def test_visibility(self):
        user = self.factory.make_user()
        user2 = self.factory.make_user()
        user3 = self.factory.make_user()

        # public set in the YAML
        yaml_str = self.factory.make_job_json()
        yaml_data = yaml.load(yaml_str)
        job = TestJob.from_yaml_and_user(
            yaml_str, user)
        self.assertTrue(job.is_public)
        self.assertTrue(job.can_view(user))
        self.assertTrue(job.can_view(user2))
        self.assertTrue(job.can_view(user3))

        yaml_data['visibility'] = 'personal'
        self.assertEqual(yaml_data['visibility'], 'personal')
        job2 = TestJob.from_yaml_and_user(
            yaml.dump(yaml_data), user3)
        self.assertFalse(job2.is_public)
        self.assertFalse(job2.can_view(user))
        self.assertFalse(job2.can_view(user2))
        self.assertTrue(job2.can_view(user3))

        group1, _ = Group.objects.get_or_create(name='group1')
        group1.user_set.add(user2)
        job2.viewing_groups.add(group1)
        job2.visibility = TestJob.VISIBLE_GROUP
        job2.save()
        self.assertFalse(job2.is_public)
        self.assertEqual(job2.visibility, TestJob.VISIBLE_GROUP)
        self.assertEqual(len(job2.viewing_groups.all()), 1)
        self.assertIn(group1, job2.viewing_groups.all())
        self.assertTrue(job.can_view(user2))
        self.assertFalse(job2.can_view(user))
        self.assertTrue(job2.can_view(user3))

    # FIXME: extend once the master validation code is exposed for unit tests
    def test_compatibility(self):  # pylint: disable=too-many-locals
        user = self.factory.make_user()
        # public set in the YAML
        yaml_str = self.factory.make_job_json()
        yaml_data = yaml.load(yaml_str)
        job = TestJob.from_yaml_and_user(
            yaml_str, user)
        self.assertTrue(job.is_public)
        self.assertTrue(job.can_view(user))
        # initial state prior to validation
        self.assertEqual(job.pipeline_compatibility, 0)
        self.assertNotIn('compatibility', yaml_data)
        # FIXME: dispatcher master needs to make this kind of test more accessible.
        definition = yaml.load(job.definition)
        self.assertNotIn('protocols', definition)
        job.actual_device = Device.objects.get(hostname='fakeqemu1')
        job_def = yaml.load(job.definition)
        job_ctx = job_def.get('context', {})
        parser = JobParser()
        device = job.actual_device

        try:
            device_config = device.load_device_configuration(job_ctx, system=False)  # raw dict
        except (jinja2.TemplateError, yaml.YAMLError, IOError) as exc:
            # FIXME: report the exceptions as useful user messages
            self.fail("[%d] jinja2 error: %s" % (job.id, exc))
        if not device_config or not isinstance(device_config, dict):
            # it is an error to have a pipeline device without a device dictionary as it will never get any jobs.
            msg = "Administrative error. Device '%s' has no device dictionary." % device.hostname
            self.fail('[%d] device-dictionary error: %s' % (job.id, msg))

        device_object = PipelineDevice(device_config, device.hostname)  # equivalent of the NewDevice in lava-dispatcher, without .yaml file.
        # FIXME: drop this nasty hack once 'target' is dropped as a parameter
        if 'target' not in device_object:
            device_object.target = device.hostname
        device_object['hostname'] = device.hostname

        parser_device = device_object
        try:
            # pass (unused) output_dir just for validation as there is no zmq socket either.
            pipeline_job = parser.parse(
                job.definition, parser_device,
                job.id, None, None, None, output_dir=job.output_dir)
        except (AttributeError, JobError, NotImplementedError, KeyError, TypeError) as exc:
            self.fail('[%s] parser error: %s' % (job.sub_id, exc))
        description = pipeline_job.describe()
        self.assertIn('compatibility', description)
        self.assertGreaterEqual(description['compatibility'], BootQEMU.compatibility)

    def test_identify_context(self):
        hostname = "fakebbb"
        mustang_type = self.factory.make_device_type('beaglebone-black')
        # this sets a qemu device dictionary, so replace it
        self.factory.make_device(device_type=mustang_type, hostname=hostname)
        mustang = DeviceDictionary(hostname=hostname)
        mustang.parameters = {
            'extends': 'beaglebone-black.jinja2',
            'base_nfsroot_args': '10.16.56.2:/home/lava/debian/nfs/,tcp,hard,intr',
            'console_device': 'ttyO0',  # takes precedence over the job context as the same var name is used.
        }
        mustang.save()
        mustang_dict = mustang.to_dict()
        device = Device.objects.get(hostname="fakebbb")
        self.assertEqual('beaglebone-black', device.device_type.name)
        self.assertTrue(device.is_pipeline)
        context_overrides = map_context_overrides('base.jinja2', 'beaglebone-black.jinja2', system=False)
        job_ctx = {
            'base_uboot_commands': 'dummy commands',
            'usb_uuid': 'dummy usb uuid',
            'console_device': 'ttyAMA0',
            'usb_device_id': 1111111111111111
        }
        device_config = device.load_device_configuration(job_ctx, system=False)  # raw dict
        self.assertIsNotNone(device_config)
        devicetype_blocks = []
        devicedict_blocks = []
        allowed = []
        for key, _ in job_ctx.items():
            if key in context_overrides:
                if key is not 'extends' and key not in mustang_dict['parameters'].keys():
                    allowed.append(key)
                else:
                    devicedict_blocks.append(key)
            else:
                devicetype_blocks.append(key)
        # only values set in job_ctx are checked
        self.assertEqual(set(allowed), {'usb_device_id', 'usb_uuid'})
        self.assertEqual(set(devicedict_blocks), {'console_device'})
        self.assertEqual(set(devicetype_blocks), {'base_uboot_commands'})
        full_list = allowed_overrides(mustang_dict, system=False)
        for key in allowed:
            self.assertIn(key, full_list)


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
        if isinstance(scanned, list) and len(scanned) == 1:
            if 'results' in scanned[0] and isinstance(scanned[0], dict):
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
        device_type = self.factory.make_device_type()
        Device.objects.filter(device_type=device_type).delete()
        Tag.objects.all().delete()
        submission = yaml.load(open(
            os.path.join(os.path.dirname(__file__), 'kvm-multinode.yaml'), 'r'))
        # no devices defined for the specified type
        self.assertRaises(DevicesUnavailableException, _pipeline_protocols, submission, user, yaml_data=None)

        self.factory.make_device(device_type, 'fakeqemu1')
        # specified tags do not exist
        self.assertRaises(yaml.YAMLError, _pipeline_protocols, submission, user)

        tag_list = [
            self.factory.ensure_tag('usb-flash'),
            self.factory.ensure_tag('usb-eth')
        ]
        self.factory.make_device(device_type, 'fakeqemu2')
        # no devices which have the required tags applied
        self.assertRaises(DevicesUnavailableException, _pipeline_protocols, submission, user, yaml_data=None)

        self.factory.make_device(device_type, 'fakeqemu3', tags=tag_list)
        job_object_list = _pipeline_protocols(submission, user)
        self.assertEqual(len(job_object_list), 2)
        for job in job_object_list:
            self.assertEqual(list(job.sub_jobs_list), job_object_list)
            check = yaml.load(job.definition)
            if check['protocols']['lava-multinode']['role'] == 'client':
                self.assertEqual(
                    check['protocols']['lava-multinode']['tags'],
                    ['usb-flash', 'usb-eth'])
                self.assertNotIn('interfaces', check['protocols']['lava-multinode'])
                self.assertEqual(set(tag_list), set(job.tags.all()))
            if check['protocols']['lava-multinode']['role'] == 'server':
                self.assertNotIn('tags', check['protocols']['lava-multinode'])
                self.assertNotIn('interfaces', check['protocols']['lava-multinode'])
                self.assertEqual(set([]), set(job.tags.all()))

    def test_multinode_group(self):
        user = self.factory.make_user()
        device_type = self.factory.make_device_type()
        submission = yaml.load(open(
            os.path.join(os.path.dirname(__file__), 'kvm-multinode.yaml'), 'r'))
        self.factory.make_device(device_type, 'fakeqemu1')
        tag_list = [
            self.factory.ensure_tag('usb-flash'),
            self.factory.ensure_tag('usb-eth')
        ]
        self.factory.make_device(device_type, 'fakeqemu2', tags=tag_list)
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
        device_type = self.factory.make_device_type()
        submission = yaml.load(open(
            os.path.join(os.path.dirname(__file__), 'kvm-multinode.yaml'), 'r'))
        self.factory.make_device(device_type, 'fakeqemu1')
        self.factory.make_device(device_type, 'fakeqemu2')
        tag_list = [
            self.factory.ensure_tag('usb-flash'),
            self.factory.ensure_tag('usb-eth')
        ]
        self.factory.make_device(device_type, 'fakeqemu3', tags=tag_list)
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

    def test_invalid_multinode(self):  # pylint: disable=too-many-locals
        user = self.factory.make_user()
        device_type = self.factory.make_device_type()
        submission = yaml.load(open(
            os.path.join(os.path.dirname(__file__), 'kvm-multinode.yaml'), 'r'))

        tag_list = [
            self.factory.ensure_tag('usb-flash'),
            self.factory.ensure_tag('usb-eth')
        ]
        self.factory.make_device(device_type, 'fakeqemu1')
        self.factory.make_device(device_type, 'fakeqemu2')
        self.factory.make_device(device_type, 'fakeqemu3', tags=tag_list)
        deploy = [action['deploy'] for action in submission['actions'] if 'deploy' in action]
        # replace working image with a broken URL
        for block in deploy:
            block['images'] = {
                'rootfs': {
                    'url': 'http://localhost/unknown/invalid.gz',
                    'image_arg': '{rootfs}'
                }
            }
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
                    device_config = device.load_device_configuration(job_ctx, system=False)  # raw dict
                except (jinja2.TemplateError, yaml.YAMLError, IOError) as exc:
                    # FIXME: report the exceptions as useful user messages
                    self.fail("[%d] jinja2 error: %s" % (job.id, exc))
                if not device_config or not isinstance(device_config, dict):
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
                        check_job.id, None, None, None,
                        output_dir=check_job.output_dir)
                except (AttributeError, JobError, NotImplementedError, KeyError, TypeError) as exc:
                    self.fail('[%s] parser error: %s' % (check_job.sub_id, exc))
                if os.path.exists('/dev/loop0'):  # rather than skipping the entire test, just the validation.
                    self.assertRaises(JobError, pipeline_job.pipeline.validate_actions)
        for job in job_object_list:
            job = TestJob.objects.get(id=job.id)
            self.assertNotEqual(job.sub_id, '')

    def test_mixed_multinode(self):
        user = self.factory.make_user()
        device_type = self.factory.make_device_type()
        self.factory.make_device(device_type, 'fakeqemu1')
        self.factory.make_device(device_type, 'fakeqemu2')
        self.factory.make_device(device_type, 'fakeqemu3')
        self.factory.make_device(device_type, 'fakeqemu4')
        submission = yaml.load(open(
            os.path.join(os.path.dirname(__file__), 'kvm-multinode.yaml'), 'r'))
        role_list = submission['protocols'][MultinodeProtocol.name]['roles']
        for role in role_list:
            if 'tags' in role_list[role]:
                del role_list[role]['tags']
        job_list = TestJob.from_yaml_and_user(yaml.dump(submission), user)
        self.assertEqual(len(job_list), 2)
        # make the list mixed
        fakeqemu1 = Device.objects.get(hostname='fakeqemu1')
        fakeqemu1.is_pipeline = False
        fakeqemu1.save(update_fields=['is_pipeline'])
        fakeqemu3 = Device.objects.get(hostname='fakeqemu3')
        fakeqemu3.is_pipeline = False
        fakeqemu3.save(update_fields=['is_pipeline'])
        device_list = Device.objects.filter(device_type=device_type, is_pipeline=True)
        self.assertEqual(len(device_list), 2)
        self.assertIsInstance(device_list, RestrictedResourceQuerySet)
        self.assertIsInstance(list(device_list), list)
        job_list = TestJob.from_yaml_and_user(yaml.dump(submission), user)
        self.assertEqual(len(job_list), 2)
        for job in job_list:
            self.assertEqual(job.requested_device_type, device_type)

    def test_multinode_with_retired(self):  # pylint: disable=too-many-statements
        """
        check handling with retired devices in device_list
        """
        user = self.factory.make_user()
        device_type = self.factory.make_device_type()
        self.factory.make_device(device_type, 'fakeqemu1')
        self.factory.make_device(device_type, 'fakeqemu2')
        self.factory.make_device(device_type, 'fakeqemu3')
        self.factory.make_device(device_type, 'fakeqemu4')
        submission = yaml.load(open(
            os.path.join(os.path.dirname(__file__), 'kvm-multinode.yaml'), 'r'))
        role_list = submission['protocols'][MultinodeProtocol.name]['roles']
        for role in role_list:
            if 'tags' in role_list[role]:
                del role_list[role]['tags']
        job_list = TestJob.from_yaml_and_user(yaml.dump(submission), user)
        self.assertEqual(len(job_list), 2)
        # make the list mixed
        fakeqemu1 = Device.objects.get(hostname='fakeqemu1')
        fakeqemu1.is_pipeline = False
        fakeqemu1.save(update_fields=['is_pipeline'])
        fakeqemu2 = Device.objects.get(hostname='fakeqemu2')
        fakeqemu3 = Device.objects.get(hostname='fakeqemu3')
        fakeqemu4 = Device.objects.get(hostname='fakeqemu4')
        device_list = Device.objects.filter(device_type=device_type, is_pipeline=True)
        self.assertEqual(len(device_list), 3)
        self.assertIsInstance(device_list, RestrictedResourceQuerySet)
        self.assertIsInstance(list(device_list), list)
        allowed_devices = []
        for device in list(device_list):
            if _check_submit_to_device([device], user):
                allowed_devices.append(device)
        self.assertEqual(len(allowed_devices), 3)
        self.assertIn(fakeqemu3, allowed_devices)
        self.assertIn(fakeqemu4, allowed_devices)
        self.assertIn(fakeqemu2, allowed_devices)
        self.assertNotIn(fakeqemu1, allowed_devices)

        # set one candidate device to RETIRED to force the bug
        fakeqemu2.status = Device.RETIRED
        fakeqemu2.save(update_fields=['status'])
        # refresh the device_list
        device_list = Device.objects.filter(device_type=device_type, is_pipeline=True)
        allowed_devices = []
        # test the old code to force the exception
        try:
            # by looping through in the test *and* in _check_submit_to_device
            # the retired device in device_list triggers the exception.
            for device in list(device_list):
                if _check_submit_to_device([device], user):
                    allowed_devices.append(device)
        except DevicesUnavailableException:
            self.assertEqual(len(allowed_devices), 2)
            self.assertIn(fakeqemu2, device_list)
            self.assertIn(fakeqemu2.status, [Device.RETIRED])
        else:
            self.fail("Missed DevicesUnavailableException")
        allowed_devices = []
        allowed_devices.extend(_check_submit_to_device(list(device_list), user))
        self.assertEqual(len(allowed_devices), 2)
        self.assertIn(fakeqemu3, allowed_devices)
        self.assertIn(fakeqemu4, allowed_devices)
        self.assertNotIn(fakeqemu2, allowed_devices)
        self.assertNotIn(fakeqemu1, allowed_devices)
        allowed_devices = []

        # test improvement as there is no point wasting memory with a Query containing Retired.
        device_list = Device.objects.filter(
            Q(device_type=device_type), Q(is_pipeline=True), ~Q(status=Device.RETIRED))
        allowed_devices.extend(_check_submit_to_device(list(device_list), user))
        self.assertEqual(len(allowed_devices), 2)
        self.assertIn(fakeqemu3, allowed_devices)
        self.assertIn(fakeqemu4, allowed_devices)
        self.assertNotIn(fakeqemu2, allowed_devices)
        self.assertNotIn(fakeqemu1, allowed_devices)

    def test_multinode_v2_metadata(self):
        device_type = self.factory.make_device_type()
        self.factory.make_device(device_type, 'fakeqemu1')
        self.factory.make_device(device_type, 'fakeqemu2')
        client_submission = yaml.load(open(
            os.path.join(os.path.dirname(__file__), 'kvm-multinode-client.yaml'), 'r'))
        job_ctx = client_submission.get('context', {})
        device = Device.objects.get(hostname='fakeqemu1')
        device_config = device.load_device_configuration(job_ctx)  # raw dict
        parser_device = PipelineDevice(device_config, device.hostname)
        parser = JobParser()
        pipeline_job = parser.parse(
            yaml.dump(client_submission), parser_device,
            4212, None, None, None, output_dir='/tmp/test')
        pipeline = pipeline_job.describe()
        from lava_results_app.dbutils import _get_job_metadata
        self.assertEqual(
            {
                'test.0.definition.name': 'multinode-basic',
                'test.0.definition.path': 'lava-test-shell/multi-node/multinode01.yaml',
                'test.0.definition.from': 'git',
                'boot.0.method': 'qemu',
                'test.0.definition.repository': 'http://git.linaro.org/lava-team/lava-functional-tests.git'
            },
            _get_job_metadata(pipeline['job']['actions'])
        )
        # simulate dynamic connection
        dynamic = yaml.load(open(
            os.path.join(os.path.dirname(__file__), 'pipeline_refs', 'connection-description.yaml'), 'r'))
        self.assertEqual(
            _get_job_metadata(dynamic['job']['actions']),
            {
                'omitted.1.inline.name': 'ssh-client',
                'test.0.definition.repository': 'git://git.linaro.org/qa/test-definitions.git',
                'test.0.definition.name': 'smoke-tests',
                'boot.0.method': 'ssh',
                'omitted.1.inline.path': 'inline/ssh-client.yaml',
                'test.0.definition.from': 'git',
                'test.0.definition.path': 'ubuntu/smoke-tests-basic.yaml'
            }
        )


class VlanInterfaces(TestCaseWithFactory):

    def setUp(self):
        super(VlanInterfaces, self).setUp()
        # YAML, pipeline only
        user = User.objects.create_user('test', 'e@mail.invalid', 'test')
        user.user_permissions.add(
            Permission.objects.get(codename='add_testjob'))
        user.save()
        bbb_type = self.factory.make_device_type('beaglebone-black')
        bbb_1 = self.factory.make_device(hostname='bbb-01', device_type=bbb_type)
        device_dict = DeviceDictionary.get(bbb_1.hostname)
        self.assertIsNone(device_dict)
        device_dict = DeviceDictionary(hostname=bbb_1.hostname)
        device_dict.parameters = {
            'interfaces': ['eth0', 'eth1'],
            'sysfs': {
                'eth0': "/sys/devices/pci0000:00/0000:00:19.0/net/eth0",
                'eth1': "/sys/devices/pci0000:00/0000:00:1c.1/0000:03:00.0/net/eth1"},
            'mac_addr': {'eth0': "f0:de:f1:46:8c:21", 'eth1': "00:24:d7:9b:c0:8c"},
            'tags': {'eth0': ['1G', '10G'], 'eth1': ['1G']},
            'map': {'eth0': {'192.168.0.2': 5}, 'eth1': {'192.168.0.2': 7}}
        }
        device_dict.save()
        ct_type = self.factory.make_device_type('cubietruck')
        cubie = self.factory.make_device(hostname='ct-01', device_type=ct_type)
        device_dict = DeviceDictionary.get(cubie.hostname)
        self.assertIsNone(device_dict)
        device_dict = DeviceDictionary(hostname=cubie.hostname)
        device_dict.parameters = {
            'interfaces': ['eth0', 'eth1'],
            'sysfs': {
                'eth0': "/sys/devices/pci0000:00/0000:00:19.0/net/eth0",
                'eth1': "/sys/devices/pci0000:00/0000:00:1c.1/0000:03:00.0/net/eth1"},
            'mac_addr': {'eth0': "f0:de:f1:46:8c:21", 'eth1': "00:24:d7:9b:c0:8c"},
            'tags': {'eth0': ['1G', '10G'], 'eth1': ['1G']},
            'map': {'eth0': {'192.168.0.2': 4}, 'eth1': {'192.168.0.2': 6}}
        }
        device_dict.save()
        self.filename = os.path.join(os.path.dirname(__file__), 'bbb-cubie-vlan-group.yaml')

    def test_vlan_interface(self):  # pylint: disable=too-many-locals
        device_dict = DeviceDictionary.get('bbb-01')
        chk = {
            'hostname': 'bbb-01',
            'parameters': {
                'map': {'eth1': {'192.168.0.2': 7}, 'eth0': {'192.168.0.2': 5}},
                'interfaces': ['eth0', 'eth1'],
                'sysfs': {
                    'eth1': '/sys/devices/pci0000:00/0000:00:1c.1/0000:03:00.0/net/eth1',
                    'eth0': '/sys/devices/pci0000:00/0000:00:19.0/net/eth0'
                },
                'mac_addr': {'eth1': '00:24:d7:9b:c0:8c', 'eth0': 'f0:de:f1:46:8c:21'},
                'tags': {'eth1': ['1G'], 'eth0': ['1G', '10G']}}
        }
        self.assertEqual(chk, device_dict.to_dict())
        submission = yaml.load(open(self.filename, 'r'))
        self.assertIn('protocols', submission)
        self.assertIn('lava-vland', submission['protocols'])
        roles = [role for role, _ in submission['protocols']['lava-vland'].iteritems()]
        params = submission['protocols']['lava-vland']
        vlans = {}
        for role in roles:
            for name, tags in params[role].iteritems():
                vlans[name] = tags
        self.assertIn('vlan_one', vlans)
        self.assertIn('vlan_two', vlans)
        jobs = split_multinode_yaml(submission, 'abcdefghijkl')
        job_roles = {}
        for role in roles:
            self.assertEqual(len(jobs[role]), 1)
            job_roles[role] = jobs[role][0]
        for role in roles:
            self.assertIn('device_type', job_roles[role])
            self.assertIn('protocols', job_roles[role])
            self.assertIn('lava-vland', job_roles[role]['protocols'])
        client_job = job_roles['client']
        server_job = job_roles['server']
        self.assertIn('vlan_one', client_job['protocols']['lava-vland'])
        self.assertIn('10G', client_job['protocols']['lava-vland']['vlan_one']['tags'])
        self.assertIn('vlan_two', server_job['protocols']['lava-vland'])
        self.assertIn('1G', server_job['protocols']['lava-vland']['vlan_two']['tags'])
        client_tags = client_job['protocols']['lava-vland']['vlan_one']
        client_dict = DeviceDictionary.get('bbb-01').to_dict()
        for interface, tags in client_dict['parameters']['tags'].iteritems():
            if any(set(tags).intersection(client_tags)):
                self.assertEqual(interface, 'eth0')
                self.assertEqual(
                    client_dict['parameters']['map'][interface],
                    {'192.168.0.2': 5}
                )
        # find_device_for_job would have a call to match_vlan_interface(device, job.definition) added
        bbb1 = Device.objects.get(hostname='bbb-01')
        self.assertTrue(match_vlan_interface(bbb1, client_job))
        cubie1 = Device.objects.get(hostname='ct-01')
        self.assertTrue(match_vlan_interface(cubie1, server_job))
