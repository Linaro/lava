import os
import yaml
import jinja2
from lava_scheduler_app.models import (
    Device,
    DeviceType,
    DeviceDictionary,
    JobPipeline,
)
from lava_scheduler_app.utils import devicedictionary_to_jinja2
from lava_scheduler_app.schema import validate_device
from django_testscenarios.ubertest import TestCase
from django.contrib.auth.models import Group, Permission, User
from lava_dispatcher.pipeline.device import PipelineDevice


class ModelFactory(object):

    def __init__(self):
        self._int = 0

    def getUniqueInteger(self):
        self._int += 1
        return self._int

    def getUniqueString(self, prefix='generic'):
        return '%s-%d' % (prefix, self.getUniqueInteger())

    def make_user(self):
        return User.objects.create_user(
            self.getUniqueString(),
            '%s@mail.invalid' % (self.getUniqueString(),),
            self.getUniqueString())


class TestCaseWithFactory(TestCase):

    def setUp(self):
        TestCase.setUp(self)
        self.factory = ModelFactory()


class DeviceTest(TestCaseWithFactory):

    def test_put_into_looping_mode(self):
        foo = DeviceType(name='foo')
        device = Device(device_type=foo, hostname='foo01', status=Device.OFFLINE)
        device.save()

        device.put_into_looping_mode(None, None)

        self.assertEqual(device.status, Device.IDLE, "should be IDLE")
        self.assertEqual(device.health_status, Device.HEALTH_LOOPING, "should be LOOPING")

    def test_access_while_hidden(self):
        hidden = DeviceType(name="hidden", owners_only=True, health_check_job='')
        device = Device(device_type=hidden, hostname='hidden1', status=Device.OFFLINE)
        user = self.factory.make_user()
        device.user = user
        device.save()
        self.assertEqual(device.is_public, False)
        self.assertEqual(device.user, user)
        user2 = self.factory.make_user()
        self.assertEqual(device.can_submit(user2), False)
        self.assertEqual(device.can_submit(user), True)

    def test_access_retired_hidden(self):
        hidden = DeviceType(name="hidden", owners_only=True, health_check_job='')
        device = Device(device_type=hidden, hostname='hidden2', status=Device.RETIRED)
        user = self.factory.make_user()
        device.user = user
        device.save()
        self.assertEqual(device.is_public, False)
        self.assertEqual(device.user, user)
        user2 = self.factory.make_user()
        self.assertEqual(device.can_submit(user2), False)
        # user cannot submit as the device is retired
        self.assertEqual(device.can_submit(user), False)

    def test_maintenance_mode(self):
        foo = DeviceType(name='foo')
        device = Device(device_type=foo, hostname='foo01', status=Device.IDLE)
        device.save()

        device.put_into_maintenance_mode(None, None)

        self.assertEqual(device.status, Device.OFFLINE, "should be offline")

        device.status = Device.RUNNING
        device.put_into_maintenance_mode(None, None)

        self.assertEqual(device.status, Device.OFFLINING, "should be offlining")


class DeviceDictionaryTest(TestCaseWithFactory):
    """
    Test the Device Dictionary KVStore
    """

    def test_new_dictionary(self):
        foo = DeviceDictionary(hostname='foo')
        foo.save()
        self.assertEqual(foo.hostname, 'foo')

    def test_dictionary_parameters(self):
        foo = DeviceDictionary(hostname='foo')
        foo.parameters = {
            'bootz': {
                'kernel': '0x4700000',
                'ramdisk': '0x4800000',
                'dtb': '0x4300000'
            },
            'media': {
                'usb': {
                    'UUID-required': True,
                    'SanDisk_Ultra': {
                        'uuid': 'usb-SanDisk_Ultra_20060775320F43006019-0:0',
                        'device_id': 0
                    },
                    'sata': {
                        'UUID-required': False
                    }
                }
            }
        }
        foo.save()
        bar = DeviceDictionary.get('foo')
        self.assertEqual(bar.parameters, foo.parameters)

    def test_pipeline_device(self):
        foo = DeviceDictionary(hostname='foo')
        foo.parameters = {
            'bootz': {
                'kernel': '0x4700000',
                'ramdisk': '0x4800000',
                'dtb': '0x4300000'
            },
            'media': {
                'usb': {
                    'UUID-required': True,
                    'SanDisk_Ultra': {
                        'uuid': 'usb-SanDisk_Ultra_20060775320F43006019-0:0',
                        'device_id': 0
                    },
                    'sata': {
                        'UUID-required': False
                    }
                }
            }
        }
        device = PipelineDevice(foo.parameters, 'foo')
        self.assertEqual(device.target, 'foo')
        self.assertIn('power_state', device)
        self.assertEqual(device.power_state, '')  # there is no power_on_command for this device, so the property is ''
        self.assertTrue(hasattr(device, 'power_state'))
        self.assertFalse(hasattr(device, 'hostname'))
        self.assertIn('hostname', device)

    def test_dictionary_remove(self):
        foo = DeviceDictionary(hostname='foo')
        foo.parameters = {
            'bootz': {
                'kernel': '0x4700000',
                'ramdisk': '0x4800000',
                'dtb': '0x4300000'
            },
        }
        foo.save()
        baz = DeviceDictionary.get('foo')
        self.assertEqual(baz.parameters, foo.parameters)
        baz.delete()
        self.assertIsInstance(baz, DeviceDictionary)
        baz = DeviceDictionary.get('foo')
        self.assertIsNone(baz)

    def test_jinja_string_templates(self):
        jinja2_path = os.path.realpath(os.path.join(
            __file__, '..', '..', '..', 'etc', 'dispatcher-config'))
        self.assertTrue(os.path.exists(jinja2_path))
        device_dictionary = {
            'usb_label': 'SanDisk_Ultra',
            'sata_label': 'ST160LM003',
            'usb_uuid': "usb-SanDisk_Ultra_20060775320F43006019-0:0",
            'sata_uuid': "ata-ST160LM003_HN-M160MBB_S2SYJ9KC102184",
            'connection_command': 'telnet localhost 6002',
            'console_device': 'ttyfake1',
            'baud_rate': 56
        }
        data = devicedictionary_to_jinja2(device_dictionary, 'cubietruck.yaml')
        string_loader = jinja2.DictLoader({'cubie.yaml': data})
        type_loader = jinja2.FileSystemLoader([os.path.join(jinja2_path, 'device-types')])
        env = jinja2.Environment(
            loader=jinja2.ChoiceLoader([string_loader, type_loader]),
            trim_blocks=True)
        template = env.get_template("%s.yaml" % 'cubie')
        device_configuration = template.render()
        yaml_data = yaml.load(device_configuration)
        self.assertTrue(validate_device(yaml_data))
        self.assertIn('timeouts', yaml_data)
        self.assertIn('parameters', yaml_data)
        self.assertIn('bootz', yaml_data['parameters'])
        self.assertIn('media', yaml_data['parameters'])
        self.assertIn('usb', yaml_data['parameters']['media'])
        self.assertIn(device_dictionary['usb_label'], yaml_data['parameters']['media']['usb'])
        self.assertIn('uuid', yaml_data['parameters']['media']['usb'][device_dictionary['usb_label']])
        self.assertEqual(
            yaml_data['parameters']['media']['usb'][device_dictionary['usb_label']]['uuid'],
            device_dictionary['usb_uuid']
        )
        self.assertIn('commands', yaml_data)
        self.assertIn('connect', yaml_data['commands'])
        self.assertEqual(
            device_dictionary['connection_command'],
            yaml_data['commands']['connect'])
        ramdisk_args = yaml_data['actions']['boot']['methods']['u-boot']['ramdisk']
        self.assertIn('commands', ramdisk_args)
        self.assertIn('boot', ramdisk_args['commands'])
        self.assertIn(
            "setenv bootargs 'console=ttyfake1,56 debug rw root=/dev/ram0 ip=dhcp'",
            ramdisk_args['commands'])

        device_dictionary.update(
            {
                'hard_reset_command': "/usr/bin/pduclient --daemon localhost --hostname pdu --command reboot --port 08",
                'power_off_command': "/usr/bin/pduclient --daemon localhost --hostname pdu --command off --port 08",
                'power_on_command': "/usr/bin/pduclient --daemon localhost --hostname pdu --command on --port 08"
            }
        )

        data = devicedictionary_to_jinja2(device_dictionary, 'beaglebone-black.yaml')
        string_loader = jinja2.DictLoader({'bbb.yaml': data})
        type_loader = jinja2.FileSystemLoader([os.path.join(jinja2_path, 'device-types')])
        env = jinja2.Environment(
            loader=jinja2.ChoiceLoader([string_loader, type_loader]),
            trim_blocks=True)
        template = env.get_template("%s.yaml" % 'bbb')
        device_configuration = template.render()
        yaml_data = yaml.load(device_configuration)
        self.assertTrue(validate_device(yaml_data))
        device = PipelineDevice(yaml_data, 'bbb')
        self.assertIn('power_state', device)
        # bbb has power_on_command defined above
        self.assertEqual(device.power_state, 'off')
        self.assertTrue(hasattr(device, 'power_state'))
        self.assertFalse(hasattr(device, 'hostname'))
        self.assertIn('hostname', device)

    def test_jinja_postgres_loader(self):
        # path used for the device_type template
        jinja2_path = os.path.realpath(os.path.join(__file__, '..', '..', '..', 'etc', 'dispatcher-config'))
        self.assertTrue(os.path.exists(jinja2_path))
        device_type = 'cubietruck'
        # pretend this was already imported into the database and use for comparison later.
        device_dictionary = {
            'usb_label': 'SanDisk_Ultra',
            'sata_label': 'ST160LM003',
            'usb_uuid': "usb-SanDisk_Ultra_20060775320F43006019-0:0",
            'sata_uuid': "ata-ST160LM003_HN-M160MBB_S2SYJ9KC102184",
            'connection_command': 'telnet localhost 6002'
        }

        # create a DeviceDictionary for this test
        cubie = DeviceDictionary(hostname='cubie')
        cubie.parameters = device_dictionary
        cubie.save()

        dict_loader = jinja2.DictLoader(
            {
                'cubie.yaml':
                devicedictionary_to_jinja2(cubie.parameters, '%s.yaml' % device_type)
            }
        )

        type_loader = jinja2.FileSystemLoader([os.path.join(jinja2_path, 'device-types')])
        env = jinja2.Environment(
            loader=jinja2.ChoiceLoader([dict_loader, type_loader]),
            trim_blocks=True)
        template = env.get_template("%s.yaml" % 'cubie')
        device_configuration = template.render()
        yaml_data = yaml.load(device_configuration)
        self.assertTrue(validate_device(yaml_data))
        self.assertIn('timeouts', yaml_data)
        self.assertIn('parameters', yaml_data)
        self.assertIn('bootz', yaml_data['parameters'])
        self.assertIn('media', yaml_data['parameters'])
        self.assertIn('usb', yaml_data['parameters']['media'])
        self.assertIn(device_dictionary['usb_label'], yaml_data['parameters']['media']['usb'])
        self.assertIn('uuid', yaml_data['parameters']['media']['usb'][device_dictionary['usb_label']])
        self.assertEqual(
            yaml_data['parameters']['media']['usb'][device_dictionary['usb_label']]['uuid'],
            device_dictionary['usb_uuid']
        )
        self.assertIn('commands', yaml_data)
        self.assertIn('connect', yaml_data['commands'])
        self.assertEqual(
            device_dictionary['connection_command'],
            yaml_data['commands']['connect'])
        device = PipelineDevice(yaml_data, 'cubie')
        self.assertIn('power_state', device)
        # cubie1 has no power_on_command defined
        self.assertEqual(device.power_state, '')
        self.assertTrue(hasattr(device, 'power_state'))
        self.assertFalse(hasattr(device, 'hostname'))
        self.assertIn('hostname', device)


class JobPipelineTest(TestCaseWithFactory):
    """
    Test that the JobPipeline KVStore is separate from the Device Dictionary KVStore.
    """
    def test_new_dictionary(self):
        foo = JobPipeline.get('foo')
        self.assertIsNone(foo)
        foo = DeviceDictionary(hostname='foo')
        foo.save()
        self.assertEqual(foo.hostname, 'foo')
        self.assertIsInstance(foo, DeviceDictionary)
        foo = DeviceDictionary.get('foo')
        self.assertIsNotNone(foo)
