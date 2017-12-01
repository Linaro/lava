import os
import yaml
import logging
import tempfile
from lava_scheduler_app.utils import split_multinode_yaml
from lava_scheduler_app.dbutils import match_vlan_interface
from lava_scheduler_app.models import (
    Device,
    TestJob,
    Tag,
)
from lava_scheduler_app.tests.test_submission import TestCaseWithFactory
from lava_scheduler_app.tests.test_pipeline import YamlFactory
from lava_scheduler_app.dbutils import find_device_for_job, assign_jobs
from lava_dispatcher.device import NewDevice
from lava_dispatcher.parser import JobParser
from lava_dispatcher.protocols.vland import VlandProtocol
from lava_dispatcher.protocols.multinode import MultinodeProtocol

# pylint does not like TestCaseWithFactory
# pylint: disable=too-many-ancestors,no-self-use,too-many-statements
# pylint: disable=superfluous-parens,too-many-locals


class VlandFactory(YamlFactory):

    def __init__(self):
        super(VlandFactory, self).__init__()
        self.bbb1 = None
        self.cubie1 = None
        self.bbb_type = None

    def setUp(self):  # pylint: disable=invalid-name
        self.bbb_type = self.make_device_type(name='bbb')
        self.cubie_type = self.make_device_type(name='cubietruck')
        self.bbb1 = self.make_device(self.bbb_type, hostname='bbb-01')
        self.cubie1 = self.make_device(self.cubie_type, hostname='cubie1')

    def make_vland_job(self, **kw):
        sample_job_file = os.path.join(os.path.dirname(__file__), 'sample_jobs', 'bbb-cubie-vlan-group.yaml')
        with open(sample_job_file, 'r') as test_support:
            data = yaml.load(test_support)
        data.update(kw)
        return data


class TestVlandSplit(TestCaseWithFactory):
    """
    Test the splitting of lava-vland data from submission YAML
    Same tests as test_submission but converted to use and look for YAML.
    """
    def setUp(self):
        super(TestVlandSplit, self).setUp()
        self.factory = VlandFactory()

    def test_split_vland(self):
        target_group = "unit-test-only"
        job_dict = split_multinode_yaml(self.factory.make_vland_job(), target_group)
        self.assertEqual(len(job_dict), 2)
        roles = job_dict.keys()
        self.assertEqual({'server', 'client'}, set(roles))
        for role in roles:
            self.assertEqual(len(job_dict[role]), 1)  # count = 1
        client_job = job_dict['client'][0]
        server_job = job_dict['server'][0]
        self.assertIn('lava-multinode', client_job['protocols'])
        self.assertIn('lava-multinode', server_job['protocols'])
        self.assertIn('lava-vland', client_job['protocols'])
        self.assertIn('lava-vland', server_job['protocols'])
        client_vlan = client_job['protocols']['lava-vland']
        server_vlan = server_job['protocols']['lava-vland']
        self.assertIn('vlan_one', client_vlan)
        self.assertIn('vlan_two', server_vlan)
        self.assertEqual(['RJ45', '10M'], client_vlan.values()[0]['tags'])
        self.assertEqual(['RJ45', '100M'], server_vlan.values()[0]['tags'])


class TestVlandDevices(TestCaseWithFactory):
    """
    Test the matching of vland device requirements with submission YAML
    """
    def setUp(self):
        super(TestVlandDevices, self).setUp()
        self.factory = VlandFactory()
        self.factory.setUp()
        logger = logging.getLogger('lava-master')
        logger.disabled = True

    def test_match_devices_without_map(self):
        """
        Without a map, there is no support for knowing which interfaces to
        put onto a VLAN, so these devices cannot be assigned to a VLAN testjob
        See http://localhost/static/docs/v2/vland.html#vland-and-interface-tags-in-lava
        """
        self.bbb3 = self.factory.make_device(self.factory.bbb_type, hostname='bbb-03')
        self.cubie2 = self.factory.make_device(self.factory.cubie_type, hostname='cubie2')
        devices = [self.bbb3, self.cubie2]
        self.factory.ensure_tag('usb-eth')
        self.factory.ensure_tag('sata')
        self.factory.bbb1.tags = Tag.objects.filter(name='usb-eth')
        self.factory.bbb1.save()
        self.factory.cubie1.tags = Tag.objects.filter(name='sata')
        self.factory.cubie1.save()
        user = self.factory.make_user()
        sample_job_file = os.path.join(os.path.dirname(__file__), 'sample_jobs', 'bbb-cubie-vlan-group.yaml')
        with open(sample_job_file, 'r') as test_support:
            data = yaml.load(test_support)
        vlan_job = TestJob.from_yaml_and_user(yaml.dump(data), user)
        assignments = {}
        for job in vlan_job:
            device = find_device_for_job(job, devices)
            self.assertIsNone(device)
            # no map defined
            self.assertFalse(match_vlan_interface(device, yaml.load(job.definition)))
            assignments[job.device_role] = device
        self.assertIsNone(assignments['client'])
        self.assertIsNone(assignments['server'])

    def test_jinja_template(self):
        yaml_data = self.factory.bbb1.load_configuration()
        self.assertIn('parameters', yaml_data)
        self.assertIn('interfaces', yaml_data['parameters'])
        self.assertIn('bootm', yaml_data['parameters'])
        self.assertIn('bootz', yaml_data['parameters'])
        self.assertIn('actions', yaml_data)
        self.assertIn('eth0', yaml_data['parameters']['interfaces'])
        self.assertIn('eth1', yaml_data['parameters']['interfaces'])
        self.assertIn('sysfs', yaml_data['parameters']['interfaces']['eth0'])
        self.assertEqual(
            '/sys/devices/pci0000:00/0000:00:1c.1/0000:03:00.0/net/eth1',
            yaml_data['parameters']['interfaces']['eth1']['sysfs']
        )

    def test_match_devices_with_map(self):
        devices = Device.objects.filter(status=Device.IDLE).order_by('is_public')
        user = self.factory.make_user()
        sample_job_file = os.path.join(os.path.dirname(__file__), 'sample_jobs', 'bbb-cubie-vlan-group.yaml')
        with open(sample_job_file, 'r') as test_support:
            data = yaml.load(test_support)
        del(data['protocols']['lava-multinode']['roles']['client']['tags'])
        del(data['protocols']['lava-multinode']['roles']['server']['tags'])

        interfaces = []
        job_dict = split_multinode_yaml(data, 'abcdefg123456789')
        client_job = job_dict['client'][0]
        device_dict = self.factory.bbb1.load_configuration()
        self.assertIsNotNone(device_dict)
        tag_list = client_job['protocols']['lava-vland']['vlan_one']['tags']

        for interface in device_dict['parameters']['interfaces']:
            tags = device_dict['parameters']['interfaces'][interface]['tags']
            if set(tags) & set(tag_list) == set(tag_list) and interface not in interfaces:
                interfaces.append(interface)
                break
        self.assertEqual(['eth1'], interfaces)
        self.assertEqual(len(interfaces), len(client_job['protocols']['lava-vland'].keys()))

        interfaces = []
        server_job = job_dict['server'][0]
        device_dict = self.factory.cubie1.load_configuration()
        self.assertIsNotNone(device_dict)
        tag_list = server_job['protocols']['lava-vland']['vlan_two']['tags']
        for interface in device_dict['parameters']['interfaces']:
            tags = device_dict['parameters']['interfaces'][interface]['tags']
            if set(tags) & set(tag_list) == set(tag_list) and interface not in interfaces:
                interfaces.append(interface)
                break
        self.assertEqual(['eth1'], interfaces)
        self.assertEqual(len(interfaces), len(client_job['protocols']['lava-vland'].keys()))

        vlan_job = TestJob.from_yaml_and_user(yaml.dump(data), user)

        # vlan_one: client role. RJ45 10M. bbb device type
        # vlan_two: server role. RJ45 100M. cubie device type.

        assignments = {}
        for job in vlan_job:
            device = find_device_for_job(job, devices)
            self.assertEqual(device.device_type, job.requested_device_type)
            # map has been defined
            self.assertTrue(match_vlan_interface(device, yaml.load(job.definition)))
            assignments[job.device_role] = device
        self.assertEqual(assignments['client'].hostname, self.factory.bbb1.hostname)
        self.assertEqual(assignments['server'].hostname, self.factory.cubie1.hostname)

    def test_same_type_devices_with_map(self):
        bbb2 = self.factory.make_device(self.factory.bbb_type, hostname='bbb-02')
        devices = list(Device.objects.filter(status=Device.IDLE).order_by('is_public'))
        user = self.factory.make_user()
        sample_job_file = os.path.join(os.path.dirname(__file__), 'sample_jobs', 'bbb-bbb-vland-group.yaml')
        with open(sample_job_file, 'r') as test_support:
            data = yaml.load(test_support)
        vlan_job = TestJob.from_yaml_and_user(yaml.dump(data), user)
        assignments = {}
        for job in vlan_job:
            device = find_device_for_job(job, devices)
            self.assertIsNotNone(device)
            self.assertEqual(device.device_type, job.requested_device_type)
            # map has been defined
            self.assertTrue(match_vlan_interface(device, yaml.load(job.definition)))
            assignments[job.device_role] = device
            if device in devices:
                devices.remove(device)
        assign_jobs()
        self.factory.bbb1.refresh_from_db()
        bbb2.refresh_from_db()
        self.assertIsNotNone(self.factory.bbb1.current_job)
        self.assertIsNotNone(bbb2.current_job)
        self.assertIsNotNone(self.factory.bbb1.current_job.actual_device)
        self.assertIsNotNone(bbb2.current_job.actual_device)  # pylint: disable=no-member
        self.assertNotEqual(self.factory.bbb1.current_job, bbb2.current_job)
        self.assertNotEqual(
            self.factory.bbb1.current_job.actual_device, bbb2.current_job.actual_device)  # pylint: disable=no-member

    def test_differing_vlan_tags(self):
        """
        More devices of the requested type than needed by the test
        with some devices having unsuitable vland interface tags.
        """
        x86 = self.factory.make_device_type('x86')
        x86_1 = self.factory.make_device(device_type=x86, hostname='x86-01')
        x86_2 = self.factory.make_device(device_type=x86, hostname='x86-02')
        x86_3 = self.factory.make_device(device_type=x86, hostname='x86-03')
        x86_4 = self.factory.make_device(device_type=x86, hostname='x86-04')

        devices = list(Device.objects.filter(status=Device.IDLE).order_by('is_public'))
        user = self.factory.make_user()
        sample_job_file = os.path.join(os.path.dirname(__file__), 'sample_jobs', 'x86-vlan.yaml')
        with open(sample_job_file, 'r') as test_support:
            data = yaml.load(test_support)
        vlan_job = TestJob.from_yaml_and_user(yaml.dump(data), user)
        assignments = {}
        for job in vlan_job:
            device = find_device_for_job(job, devices)
            self.assertIsNotNone(device)
            self.assertEqual(device.device_type, job.requested_device_type)
            # map has been defined
            self.assertTrue(match_vlan_interface(device, yaml.load(job.definition)))
            assignments[job.device_role] = device
            if device in devices:
                devices.remove(device)
        assign_jobs()

        # reset state, pretend the assigned jobs have completed.
        for job in TestJob.objects.all():
            job.status = TestJob.COMPLETE
            job.actual_device.status = Device.IDLE
            job.actual_device.current_job = None
            job.actual_device.save(update_fields=['status', 'current_job'])
            job.save(update_fields=['status'])

        # take x86_1 offline, forcing the idle list to include x86_3 for evaluation

        x86_1.status = Device.OFFLINE
        x86_1.save(update_fields=['status'])
        x86_1.refresh_from_db()

        devices = list(Device.objects.filter(status=Device.IDLE).order_by('is_public'))
        self.assertNotIn(x86_1, devices)
        self.assertIn(x86_2, devices)
        self.assertIn(x86_3, devices)
        self.assertIn(x86_4, devices)
        user = self.factory.make_user()
        sample_job_file = os.path.join(os.path.dirname(__file__), 'sample_jobs', 'x86-vlan.yaml')
        with open(sample_job_file, 'r') as test_support:
            data = yaml.load(test_support)
        vlan_job = TestJob.from_yaml_and_user(yaml.dump(data), user)
        assignments = {}
        for job in vlan_job:
            device = find_device_for_job(job, devices)
            self.assertIsNotNone(device)
            self.assertEqual(device.device_type, job.requested_device_type)
            # map has been defined
            self.assertTrue(match_vlan_interface(device, yaml.load(job.definition)))
            assignments[job.device_role] = device
            if device in devices:
                devices.remove(device)
        assign_jobs()
        x86_1.refresh_from_db()
        x86_2.refresh_from_db()
        x86_3.refresh_from_db()
        x86_4.refresh_from_db()
        self.assertEqual(Device.STATUS_CHOICES[Device.OFFLINE], Device.STATUS_CHOICES[x86_1.status])
        self.assertEqual(Device.STATUS_CHOICES[Device.RESERVED], Device.STATUS_CHOICES[x86_2.status])
        self.assertEqual(Device.STATUS_CHOICES[Device.IDLE], Device.STATUS_CHOICES[x86_3.status])
        self.assertEqual(Device.STATUS_CHOICES[Device.RESERVED], Device.STATUS_CHOICES[x86_4.status])

    def test_match_devices_with_map_and_tags(self):  # pylint: disable=invalid-name
        devices = Device.objects.filter(status=Device.IDLE).order_by('is_public')
        self.factory.ensure_tag('usb-eth')
        self.factory.ensure_tag('sata')
        self.factory.bbb1.tags = Tag.objects.filter(name='usb-eth')
        self.factory.bbb1.save()
        self.factory.cubie1.tags = Tag.objects.filter(name='sata')
        self.factory.cubie1.save()
        user = self.factory.make_user()
        sample_job_file = os.path.join(os.path.dirname(__file__), 'sample_jobs', 'bbb-cubie-vlan-group.yaml')
        with open(sample_job_file, 'r') as test_support:
            data = yaml.load(test_support)
        vlan_job = TestJob.from_yaml_and_user(yaml.dump(data), user)
        assignments = {}
        for job in vlan_job:
            device = find_device_for_job(job, devices)
            self.assertEqual(device.device_type, job.requested_device_type)
            # map has been defined
            self.assertTrue(match_vlan_interface(device, yaml.load(job.definition)))
            assignments[job.device_role] = device
        self.assertEqual(assignments['client'].hostname, self.factory.bbb1.hostname)
        self.assertEqual(assignments['server'].hostname, self.factory.cubie1.hostname)


class TestVlandProtocolSplit(TestCaseWithFactory):
    """
    Test the handling of protocols in dispatcher after splitting the YAML
    """
    def setUp(self):
        super(TestVlandProtocolSplit, self).setUp()
        self.factory = VlandFactory()
        self.factory.setUp()

    def test_job_protocols(self):
        self.factory.ensure_tag('usb-eth')
        self.factory.ensure_tag('sata')
        self.factory.bbb1.tags = Tag.objects.filter(name='usb-eth')
        self.factory.bbb1.save()
        self.factory.cubie1.tags = Tag.objects.filter(name='sata')
        self.factory.cubie1.save()
        target_group = "unit-test-only"
        job_dict = split_multinode_yaml(self.factory.make_vland_job(), target_group)
        client_job = job_dict['client'][0]
        client_handle, client_file_name = tempfile.mkstemp()
        yaml.dump(client_job, open(client_file_name, 'w'))
        # YAML device file, as required by lava-dispatch --target
        device_yaml_file = os.path.realpath(os.path.join(os.path.dirname(__file__), 'devices', 'bbb-01.yaml'))
        self.assertTrue(os.path.exists(device_yaml_file))
        parser = JobParser()
        bbb_device = NewDevice(device_yaml_file)
        with open(client_file_name) as sample_job_data:
            bbb_job = parser.parse(sample_job_data, bbb_device, 4212, None, "", output_dir='/tmp/')
        os.close(client_handle)
        os.unlink(client_file_name)
        self.assertIn('protocols', bbb_job.parameters)
        self.assertIn(VlandProtocol.name, bbb_job.parameters['protocols'])
        self.assertIn(MultinodeProtocol.name, bbb_job.parameters['protocols'])
