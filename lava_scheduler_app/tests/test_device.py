import os
import yaml
import jinja2
from django.contrib.contenttypes.models import ContentType
from django.contrib.admin.models import LogEntry
from lava_scheduler_app.models import (
    Device,
    DeviceType,
    DeviceDictionary,
    JobPipeline,
)
from lava_scheduler_app.utils import (
    devicedictionary_to_jinja2,
    jinja2_to_devicedictionary,
    prepare_jinja_template,
    jinja_template_path,
    load_devicetype_template,
)
from lava_scheduler_app.schema import validate_device, SubmissionException
from django_testscenarios.ubertest import TestCase
from django.contrib.auth.models import User
from lava_dispatcher.pipeline.device import PipelineDevice
from lava_dispatcher.pipeline.action import Timeout

# pylint: disable=blacklisted-name,too-many-ancestors,invalid-name
# python3 needs print to be a function, so disable pylint
# pylint: disable=superfluous-parens
# pylint: disable=too-many-branches,too-many-locals,too-many-nested-blocks


class ModelFactory(object):

    def __init__(self):
        self._int = 0

    def getUniqueInteger(self):
        self._int += 1
        return self._int

    def getUniqueString(self, prefix='generic'):
        return '%s-%d' % (prefix, self.getUniqueInteger())

    def get_unique_user(self, prefix='generic'):  # pylint: disable=no-self-use
        return "%s-%d" % (prefix, User.objects.count() + 1)

    def make_user(self):
        return User.objects.create_user(
            self.get_unique_user(),
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
        jinja2_path = jinja_template_path(system=False)
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
        data = devicedictionary_to_jinja2(device_dictionary, 'cubietruck.jinja2')
        template = prepare_jinja_template('cubie', data, system_path=False, path=jinja2_path)
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
            "setenv bootargs 'console=ttyfake1,56 debug rw root=/dev/ram0  ip=dhcp'",
            ramdisk_args['commands'])

        device_dictionary.update(
            {
                'hard_reset_command': "/usr/bin/pduclient --daemon localhost --hostname pdu --command reboot --port 08",
                'power_off_command': "/usr/bin/pduclient --daemon localhost --hostname pdu --command off --port 08",
                'power_on_command': "/usr/bin/pduclient --daemon localhost --hostname pdu --command on --port 08"
            }
        )

        data = devicedictionary_to_jinja2(device_dictionary, 'beaglebone-black.jinja2')
        template = prepare_jinja_template('bbb', data, system_path=False, path=jinja2_path)
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
        jinja2_path = jinja_template_path(system=False)
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
        jinja_data = devicedictionary_to_jinja2(cubie.parameters, '%s.jinja2' % device_type)
        dict_loader = jinja2.DictLoader({'cubie.jinja2': jinja_data})
        type_loader = jinja2.FileSystemLoader([os.path.join(jinja2_path, 'device-types')])
        env = jinja2.Environment(
            loader=jinja2.ChoiceLoader([dict_loader, type_loader]),
            trim_blocks=True)
        template = env.get_template("%s.jinja2" % 'cubie')
        # pylint gets this wrong from jinja
        device_configuration = template.render()  # pylint: disable=no-member

        chk_template = prepare_jinja_template('cubie', jinja_data, system_path=False, path=jinja2_path)
        self.assertEqual(template.render(), chk_template.render())  # pylint: disable=no-member
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

    def test_vland_jinja2(self):
        """
        Test complex device dictionary values

        The reference data can cross lines but cannot be indented as the pprint
        object in utils uses indent=0, width=80 for YAML compatibility.
        The strings read in from config files can have indenting spaces, these
        are removed in the pprint.
        """
        data = """{% extends 'vland.jinja2' %}
{% set interfaces = ['eth0', 'eth1'] %}
{% set sysfs = {'eth0': '/sys/devices/pci0000:00/0000:00:19.0/net/eth0',
'eth1': '/sys/devices/pci0000:00/0000:00:1c.1/0000:03:00.0/net/eth1'} %}
{% set mac_addr = {'eth0': 'f0:de:f1:46:8c:21', 'eth1': '00:24:d7:9b:c0:8c'} %}
{% set tags = {'eth0': ['1G', '10G'], 'eth1': ['1G']} %}
{% set map = {'eth0': {'192.168.0.2': 5}, 'eth1': {'192.168.0.2': 7}} %}
"""
        result = {
            'interfaces': ['eth0', 'eth1'],
            'sysfs': {
                'eth1': '/sys/devices/pci0000:00/0000:00:1c.1/0000:03:00.0/net/eth1',
                'eth0': '/sys/devices/pci0000:00/0000:00:19.0/net/eth0'
            },
            'extends': 'vland.jinja2',
            'mac_addr': {
                'eth1': '00:24:d7:9b:c0:8c',
                'eth0': 'f0:de:f1:46:8c:21'
            },
            'tags': {
                'eth1': ['1G'],
                'eth0': ['1G', '10G']
            },
            'map': {
                'eth0': {
                    '192.168.0.2': 5
                },
                'eth1': {
                    '192.168.0.2': 7
                }
            }
        }
        dictionary = jinja2_to_devicedictionary(data_dict=data)
        self.assertEqual(result, dictionary)
        jinja2_str = devicedictionary_to_jinja2(data_dict=dictionary, extends='vland.jinja2')
        # ordering within the dict can change but each line needs to still appear
        for line in str(data).split('\n'):
            self.assertIn(line, str(jinja2_str))

        # create a DeviceDictionary for this test
        vlan = DeviceDictionary(hostname='vlanned1')
        vlan.parameters = dictionary
        vlan.save()
        del vlan
        vlan = DeviceDictionary.get('vlanned1')
        cmp_str = str(devicedictionary_to_jinja2(vlan.parameters, 'vland.jinja2'))
        for line in str(data).split('\n'):
            self.assertIn(line, cmp_str)

    def test_network_map(self):
        """
        Convert a device dictionary into the output suitable for XMLRPC
        """
        map_yaml = """
switches:
  '192.168.0.2':
  - port: 5
    device:
      interface: eth0
      sysfs: "/sys/devices/pci0000:00/0000:00:19.0/net/eth0"
      mac: "f0:de:f1:46:8c:21"
      hostname: bbb1
  - port: 7
    device:
      interface: eth1
      sysfs: "/sys/devices/pci0000:00/0000:00:1c.1/0000:03:00.0/net/eth1"
      mac: "00:24:d7:9b:c0:8c"
      hostname: bbb1
        """
        device_dict = {
            'interfaces': ['eth0', 'eth1'],
            'sysfs': {
                'eth1': '/sys/devices/pci0000:00/0000:00:1c.1/0000:03:00.0/net/eth1',
                'eth0': '/sys/devices/pci0000:00/0000:00:19.0/net/eth0'
            },
            'extends': 'vland.jinja2',
            'mac_addr': {
                'eth1': '00:24:d7:9b:c0:8c',
                'eth0': 'f0:de:f1:46:8c:21'
            },
            'tags': {
                'eth1': ['1G'],
                'eth0': ['1G', '10G']
            },
            'map': {
                'eth0': {
                    '192.168.0.2': 5
                },
                'eth1': {
                    '192.168.0.2': 7
                }
            }
        }
        chk_map = yaml.load(map_yaml)
        if 'interfaces' not in device_dict:
            self.fail("Not a vland device dictionary")
        network_map = {}
        port_list = []
        for interface in device_dict['interfaces']:
            for switch, port in device_dict['map'][interface].iteritems():
                device = {
                    'interface': interface,
                    'mac': device_dict['mac_addr'][interface],
                    'sysfs': device_dict['sysfs'][interface],
                    'hostname': 'bbb1'
                }
                port_list.append({'port': port, 'device': device})
                network_map['switches'] = {switch: port_list}
        self.assertEqual(chk_map, network_map)


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


class DeviceTypeTest(TestCaseWithFactory):
    """
    Test loading of device-type information
    """
    def test_device_type_parser(self):
        jinja2_path = jinja_template_path(system=False)
        self.assertTrue(os.path.exists(jinja2_path))
        data = load_devicetype_template('beaglebone-black', system_path=False)
        self.assertIsNotNone(data)
        self.assertIn('actions', data)
        self.assertIn('deploy', data['actions'])
        self.assertIn('boot', data['actions'])

    def test_device_type_templates(self):
        """
        Ensure each template renders valid YAML
        """
        jinja2_path = jinja_template_path(system=False)
        for template_name in os.listdir(os.path.join(jinja2_path, 'device-types')):
            if not template_name.endswith('jinja2'):
                continue
            type_loader = jinja2.FileSystemLoader([os.path.join(jinja2_path, 'device-types')])
            env = jinja2.Environment(
                loader=jinja2.ChoiceLoader([type_loader]),
                trim_blocks=True)
            try:
                template = env.get_template(template_name)
            except jinja2.TemplateNotFound as exc:
                self.fail('%s: %s' % (template_name, exc))
            data = None
            try:
                data = template.render()
                yaml_data = yaml.load(data)
            except yaml.YAMLError as exc:
                print(data)  # for easier debugging - use the online yaml parser
                self.fail("%s: %s" % (template_name, exc))
            self.assertIsInstance(yaml_data, dict)


class TestLogEntry(TestCaseWithFactory):

    def test_create_logentry(self):
        foo = DeviceType(name='foo')
        device = Device(device_type=foo, hostname='foo01', status=Device.OFFLINE)
        device.save()

        # only unit tests should call these functions with None, None
        # if that is made a requirement of the device status functions, fix this test.
        device.put_into_looping_mode(None, None)
        self.assertEqual(device.status, Device.IDLE, "should be IDLE")
        self.assertEqual(device.health_status, Device.HEALTH_LOOPING, "should be LOOPING")
        device_ct = ContentType.objects.get_for_model(Device)
        self.assertEqual(0, len(LogEntry.objects.filter(content_type=device_ct, action_flag=2).order_by('-action_time')))

        user = self.factory.make_user()
        device.put_into_maintenance_mode(user, 'test_create_logentry')
        self.assertEqual(device.status, Device.OFFLINE, "should be OFFLINE")
        self.assertEqual(device.health_status, Device.HEALTH_UNKNOWN, "should be UNKNOWN")
        # the device state transition also creates a log entry
        self.assertEqual(2, len(LogEntry.objects.filter(content_type=device_ct, action_flag=2).order_by('-action_time')))


class TestTemplates(TestCaseWithFactory):

    # When adding or modifying a jinja2 template, add or update the test here.
    # Use realistic data.

    debug = False  # set to True to see the YAML device config output

    def validate_data(self, hostname, data, job_ctx=None):
        if not job_ctx:
            job_ctx = {}
        test_template = prepare_jinja_template(hostname, data, system_path=False)
        rendered = test_template.render(**job_ctx)
        if self.debug:
            print('#######')
            print(rendered)
            print('#######')
        try:
            ret = validate_device(yaml.load(rendered))
        except SubmissionException as exc:
            print('#######')
            print(rendered)
            print('#######')
            self.fail(exc)
        return ret

    def test_nexus10_template(self):
        self.assertTrue(self.validate_data('staging-nexus10-01', """{% extends 'nexus10.jinja2' %}
{% set adb_serial_number = 'R32D300FRYP' %}
{% set soft_reboot_command = 'adb -s R32D300FRYP reboot bootloader' %}
{% set connection_command = 'adb -s R32D300FRYP shell' %}"""))

    def test_x86_template(self):
        data = """{% extends 'x86.jinja2' %}
{% set power_off_command = '/usr/bin/pduclient --daemon localhost --port 02 --hostname lngpdu01 --command off' %}
{% set hard_reset_command = '/usr/bin/pduclient --daemon localhost --port 02 --hostname lngpdu01 --command reboot' %}
{% set power_on_command = '/usr/bin/pduclient --daemon localhost --port 02 --hostname lngpdu01 --command on' %}
{% set connection_command = 'telnet localhost 7302' %}"""
        self.assertTrue(self.validate_data('staging-x86-01', data))
        test_template = prepare_jinja_template('staging-qemu-01', data, system_path=False)
        rendered = test_template.render()
        template_dict = yaml.load(rendered)
        for _, value in template_dict['actions']['boot']['methods']['ipxe'].items():
            if 'commands' in value:
                for item in value['commands']:
                    self.assertFalse(item.endswith(','))
        depth = 0
        # check configured commands blocks for trailing commas inherited from JSON V1 configuration.
        # reduce does not help as the top level dictionary also contains lists, integers and strings
        for _, action_value in template_dict['actions'].items():
            if 'methods' in action_value:
                depth = 1 if depth < 1 else depth
                for _, method_value in action_value.items():
                    depth = 2 if depth < 2 else depth
                    for item_key, item_value in method_value.items():
                        depth = 3 if depth < 3 else depth
                        if isinstance(item_value, dict):
                            depth = 4 if depth < 4 else depth
                            for _, command_value in method_value[item_key].items():
                                depth = 5 if depth < 5 else depth
                                if isinstance(command_value, dict):
                                    depth = 6 if depth < 6 else depth
                                    if 'commands' in command_value:
                                        depth = 7 if depth < 7 else depth
                                        for item in command_value['commands']:
                                            depth = 8 if depth < 8 else depth
                                            if item.endswith(','):
                                                self.fail("%s ends with a comma" % item)
        self.assertEqual(depth, 8)

    def test_beaglebone_black_template(self):
        self.assertTrue(self.validate_data('staging-x86-01', """{% extends 'beaglebone-black.jinja2' %}
{% set map = {'eth0': {'lngswitch03': 19}, 'eth1': {'lngswitch03': 8}} %}
{% set hard_reset_command = '/usr/bin/pduclient --daemon localhost --hostname lngpdu01 --command reboot --port 19' %}
{% set tags = {'eth0': ['1G', '100M'], 'eth1': ['100M']} %}
{% set interfaces = ['eth0', 'eth1'] %}
{% set sysfs = {'eth0': '/sys/devices/platform/ocp/4a100000.ethernet/net/eth0',
'eth1': '/sys/devices/platform/ocp/47400000.usb/47401c00.usb/musb-hdrc.1.auto/usb1/1-1/1-1:1.0/net/eth1'} %}
{% set power_off_command = '/usr/bin/pduclient --daemon localhost --hostname lngpdu01 --command off --port 19' %}
{% set mac_addr = {'eth0': '90:59:af:5e:69:fd', 'eth1': '00:e0:4c:53:44:58'} %}
{% set power_on_command = '/usr/bin/pduclient --daemon localhost --hostname lngpdu01 --command on --port 19' %}
{% set connection_command = 'telnet localhost 7333' %}
{% set exclusive = 'True' %}"""))

    def test_qemu_template(self):
        self.assertTrue(self.validate_data('staging-x86-01', """{% extends 'qemu.jinja2' %}
{% set exclusive = 'True' %}
{% set mac_addr = 'DE:AD:BE:EF:28:01' %}
{% set memory = 512 %}""", job_ctx={'arch': 'amd64'}))

    def test_qemu_installer(self):
        data = """{% extends 'qemu.jinja2' %}
{% set exclusive = 'True' %}
{% set mac_addr = 'DE:AD:BE:EF:28:01' %}
{% set memory = 512 %}"""
        job_ctx = {'arch': 'amd64'}
        test_template = prepare_jinja_template('staging-qemu-01', data, system_path=False)
        rendered = test_template.render(**job_ctx)
        template_dict = yaml.load(rendered)
        self.assertEqual(
            'c',
            template_dict['actions']['boot']['methods']['qemu']['parameters']['boot_options']['boot_order']
        )

    def test_mustang_template(self):
        self.assertTrue(self.validate_data('staging-x86-01', """{% extends 'mustang.jinja2' %}
{% set connection_command = 'telnet serial4 7012' %}
{% set hard_reset_command = '/usr/bin/pduclient --daemon staging-master --hostname pdu15 --command reboot --port 05' %}
{% set power_off_command = '/usr/bin/pduclient --daemon staging-master --hostname pdu15 --command off --port 05' %}
{% set power_on_command = '/usr/bin/pduclient --daemon staging-master --hostname pdu15 --command on --port 05' %}"""))

    def test_hikey_template(self):
        with open(os.path.join(os.path.dirname(__file__), 'devices', 'hi6220-hikey-01.jinja2')) as hikey:
            data = hikey.read()
        self.assertIsNotNone(data)
        self.assertTrue(self.validate_data('hi6220-hikey-01', data))
        test_template = prepare_jinja_template('staging-hikey-01', data, system_path=False)
        rendered = test_template.render()
        template_dict = yaml.load(rendered)
        self.assertIsNotNone(template_dict)

    def test_panda_template(self):
        data = """{% extends 'panda.jinja2' %}
{% set connection_command = 'telnet serial4 7012' %}
{% set hard_reset_command = '/usr/bin/pduclient --daemon staging-master --hostname pdu15 --command reboot --port 05' %}
{% set power_off_command = '/usr/bin/pduclient --daemon staging-master --hostname pdu15 --command off --port 05' %}
{% set power_on_command = '/usr/bin/pduclient --daemon staging-master --hostname pdu15 --command on --port 05' %}"""
        self.assertTrue(self.validate_data('staging-panda-01', data))
        test_template = prepare_jinja_template('staging-panda-01', data, system_path=False)
        rendered = test_template.render()
        template_dict = yaml.load(rendered)
        self.assertIn('u-boot-commands', template_dict['timeouts']['actions'])
        self.assertEqual(120.0, Timeout.parse(template_dict['timeouts']['actions']['u-boot-commands']))

    def test_juno_uboot_template(self):
        data = """{% extends 'juno-uboot.jinja2' %}
{% set connection_command = 'telnet serial4 7001' %}
{% set hard_reset_command = '/usr/local/lab-scripts/snmp_pdu_control --hostname pdu18 --command reboot --port 10 --delay 10' %}
{% set power_off_command = '/usr/local/lab-scripts/snmp_pdu_control --hostname pdu18 --command off --port 10 --delay 10' %}
{% set power_on_command = '/usr/local/lab-scripts/snmp_pdu_control --hostname pdu18 --command on --port 10 --delay 10' %}
{% set usb_label = 'SanDiskCruzerBlade' %}
{% set usb_uuid = 'usb-SanDisk_Cruzer_Blade_20060266531DA442AD42-0:0' %}
{% set usb_device_id = 0 %}
{% set nfs_uboot_bootcmd = (
"          - setenv bootcmd 'dhcp; setenv serverip {SERVER_IP}; run loadkernel; run loadinitrd; run loadfdt; {BOOTX}'
          - boot") %}"""
        self.assertTrue(self.validate_data('staging-juno-01', data))
        test_template = prepare_jinja_template('staging-juno-01', data, system_path=False)
        rendered = test_template.render()
        template_dict = yaml.load(rendered)
        self.assertIsNotNone(template_dict)

    def test_qemu_cortex_a57(self):
        data = """{% extends 'qemu.jinja2' %}
{% set memory = 2048 %}
{% set mac_addr = '52:54:00:12:34:59' %}
{% set arch = 'arm64' %}
{% set base_guest_fs_size = 2048 %}
        """
        job_ctx = {
            'arch': 'amd64',
            'boot_root': '/dev/vda',
            'extra_options': ['-global', 'virtio-blk-device.scsi=off', '-smp', 1, '-device', 'virtio-scsi-device,id=scsi']
        }
        self.assertTrue(self.validate_data('staging-qemu-01', data))
        test_template = prepare_jinja_template('staging-juno-01', data, system_path=False)
        rendered = test_template.render(**job_ctx)
        self.assertIsNotNone(rendered)
        template_dict = yaml.load(rendered)
        options = template_dict['actions']['boot']['methods']['qemu']['parameters']['options']
        self.assertIn('-cpu cortex-a57', options)
        self.assertNotIn('-global', options)
        extra = template_dict['actions']['boot']['methods']['qemu']['parameters']['extra']
        self.assertIn('-global', extra)
        self.assertNotIn('-cpu cortex-a57', extra)
        options.extend(extra)
        self.assertIn('-global', options)
        self.assertIn('-cpu cortex-a57', options)

    def test_overdrive_template(self):
        data = """{% extends 'overdrive.jinja2' %}
{% set connection_command = 'telnet serial4 7001' %}
{% set hard_reset_command = '/usr/local/lab-scripts/snmp_pdu_control --hostname pdu18 --command reboot --port 10 --delay 10' %}
{% set power_off_command = '/usr/local/lab-scripts/snmp_pdu_control --hostname pdu18 --command off --port 10 --delay 10' %}
{% set power_on_command = '/usr/local/lab-scripts/snmp_pdu_control --hostname pdu18 --command on --port 10 --delay 10' %}"""
        self.assertTrue(self.validate_data('staging-overdrive-01', data))
        test_template = prepare_jinja_template('staging-overdrive-01', data, system_path=False)
        rendered = test_template.render()
        template_dict = yaml.load(rendered)
        self.assertEqual(
            [check for check in template_dict['actions']['boot']['methods']['grub']['nfs']['commands'] if 'nfsroot' in check][0].count('nfsroot'),
            1
        )
        self.assertIn(
            ' rw',
            [check for check in template_dict['actions']['boot']['methods']['grub']['nfs']['commands'] if 'nfsroot' in check][0]
        )
        self.assertIsNotNone(template_dict)
