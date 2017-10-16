import os
import sys
import glob
import yaml
import jinja2
import unittest
import logging
import tempfile
# pylint: disable=superfluous-parens,ungrouped-imports
from lava_dispatcher.pipeline.parser import JobParser
from lava_dispatcher.pipeline.device import NewDevice
from lava_scheduler_app.schema import validate_device, SubmissionException
from lava_dispatcher.pipeline.action import Timeout
from lava_dispatcher.pipeline.utils.shell import infrastructure_error
from lava_dispatcher.pipeline.test.utils import DummyLogger
from lava_scheduler_app.schema import (
    validate_submission,
    validate_device,
)

# pylint: disable=too-many-branches,too-many-public-methods
# pylint: disable=too-many-nested-blocks


CONFIG_PATH = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__), "..", "..",
        "lava_scheduler_app", "tests", "devices"))


def prepare_jinja_template(hostname, jinja_data):
    string_loader = jinja2.DictLoader({'%s.jinja2' % hostname: jinja_data})
    path = os.path.dirname(CONFIG_PATH)
    type_loader = jinja2.FileSystemLoader([os.path.join(path, 'device-types')])
    env = jinja2.Environment(
        loader=jinja2.ChoiceLoader([string_loader, type_loader]),
        trim_blocks=True)
    return env.get_template("%s.jinja2" % hostname)


class TestTemplates(unittest.TestCase):
    """
    Test rendering of jinja2 templates

    When adding or modifying a jinja2 template, add or update the test here.
    Use realistic data - complete exports of the device dictionary preferably.
    Set debug to True to see the content of the rendered templates
    Set system to True to use the system templates - note that this requires
    that the templates in question are in sync with the branch upon which the
    test is run. Therefore, if the templates should be the same, this can be
    used to check that the templates are correct. If there are problems, check
    for a template with a .dpkg-dist extension. Check the diff between the
    checkout and the system file matches the difference between the system file
    and the dpkg-dist version. If the diffs match, copy the dpkg-dist onto the
    system file.
    """

    debug = False  # set to True to see the YAML device config output
    system = False  # set to True to debug the system templates

    def render_device_dictionary(self, hostname, data, job_ctx=None):
        if not job_ctx:
            job_ctx = {}
        test_template = prepare_jinja_template(hostname, data)
        rendered = test_template.render(**job_ctx)
        if self.debug:
            print('#######')
            print(rendered)
            print('#######')
        return rendered

    def validate_data(self, hostname, data, job_ctx=None):
        rendered = self.render_device_dictionary(hostname, data, job_ctx)
        try:
            ret = validate_device(yaml.load(rendered))
        except SubmissionException as exc:
            print('#######')
            print(rendered)
            print('#######')
            self.fail(exc)
        return ret

    def test_all_templates(self):
        path = os.path.dirname(CONFIG_PATH)
        templates = glob.glob(os.path.join(path, 'device-types', '*.jinja2'))
        self.assertNotEqual([], templates)
        for template in templates:
            data = "{%% extends '%s' %%}" % os.path.basename(template)
            try:
                self.validate_data('device', data)
            except AssertionError as exc:
                self.fail("Template %s failed: %s" % (os.path.basename(template), exc))

    def test_all_template_connections(self):
        path = os.path.dirname(CONFIG_PATH)
        templates = glob.glob(os.path.join(path, 'device-types', '*.jinja2'))
        self.assertNotEqual([], templates)
        for template in templates:
            name = os.path.basename(template)
            data = "{%% extends '%s' %%}" % os.path.basename(template)
            data += "{% set connection_command = 'telnet calvin 6080' %}"
            self.validate_data('device', data)
            test_template = prepare_jinja_template('testing-01', data)
            rendered = test_template.render()
            template_dict = yaml.load(rendered)
            self.assertIn('connect', template_dict['commands'])
            self.assertNotIn(
                'connections',
                template_dict['commands'], msg="%s - failed support for connection_list syntax" % name)
            data = "{%% extends '%s' %%}" % os.path.basename(template)
            data += "{% set connection_list = ['uart0'] %}"
            data += "{% set connection_commands = {'uart1': 'telnet calvin 6080'} %}"
            data += "{% set connection_tags = {'uart1': ['primary']} %}"
            self.validate_data('device', data)
            test_template = prepare_jinja_template('testing-01', data)
            rendered = test_template.render()
            template_dict = yaml.load(rendered)
            self.assertNotIn('connect', template_dict['commands'])
            self.assertIn(
                'connections',
                template_dict['commands'], msg="%s - missing connection_list syntax" % name)

    def test_rendering(self):
        self.assertFalse(CONFIG_PATH.startswith('/etc/'))
        with open(os.path.join(os.path.dirname(__file__), 'devices', 'db410c.jinja2')) as hikey:
            data = hikey.read()
        env = jinja2.Environment()
        ast = env.parse(data)
        device_dict = {}
        count = 0
        for node in ast.find_all(jinja2.nodes.Assign):
            count += 1
            if isinstance(node.node, jinja2.nodes.Const):
                device_dict[node.target.name] = node.node.value
        self.assertIsNotNone(device_dict)
        # FIXME: recurse through the jinja2 nodes without rendering
        # then change this to assertEqual
        self.assertNotEqual(count, len(device_dict.keys()))

    def test_inclusion(self):
        data = """{% extends 'nexus4.jinja2' %}
{% set adb_serial_number = 'R42D300FRYP' %}
{% set fastboot_serial_number = 'R42D300FRYP' %}
{% set connection_command = 'adb -s ' + adb_serial_number +' shell' %}
"""
        test_template = prepare_jinja_template('nexus4-01', data)
        rendered = test_template.render()
        template_dict = yaml.load(rendered)
        self.assertEqual(
            'adb -s R42D300FRYP shell',
            template_dict['commands']['connect']
        )
        self.assertIn('lxc', template_dict['actions']['boot']['methods'])
        self.assertIn('fastboot', template_dict['actions']['boot']['methods'])
        self.assertIn('lxc', template_dict['actions']['deploy']['methods'])
        self.assertIn('fastboot', template_dict['actions']['deploy']['methods'])
        self.assertEqual(
            ['reboot'],
            template_dict['actions']['boot']['methods']['fastboot']
        )

    def test_primary_connection_power_commands_fail(self):
        data = """{% extends 'x86.jinja2' %}
{% set power_off_command = '/usr/bin/pduclient --command off' %}
{% set power_on_command = '/usr/bin/pduclient --command on' %}
{% set hard_reset_command = '/usr/bin/pduclient --command reset' %}
{% set connection_command = 'telnet localhost 7302' %}
{% set ssh_host = 'localhost' %}"""
        device_dict = self.render_device_dictionary('staging-x86-01', data)
        self.assertRaises(
            SubmissionException,
            validate_device,
            yaml.load(device_dict)
        )

    def test_primary_connection_power_commands_empty_ssh_host(self):
        data = """{% extends 'x86.jinja2' %}
{% set power_off_command = '/usr/bin/pduclient --command off' %}
{% set power_on_command = '/usr/bin/pduclient --command on' %}
{% set hard_reset_command = '/usr/bin/pduclient --command reset' %}
{% set connection_command = 'telnet localhost 7302' %}
{% set ssh_host = '' %}"""
        device_dict = self.render_device_dictionary('staging-x86-01', data)
        self.assertTrue(validate_device(yaml.load(device_dict)))

    def test_primary_connection_power_commands(self):
        data = """{% extends 'x86.jinja2' %}
{% set power_off_command = '/usr/bin/pduclient --command off' %}
{% set hard_reset_command = '/usr/bin/pduclient --command reset' %}
{% set power_on_command = '/usr/bin/pduclient --command on' %}
{% set connection_command = 'telnet localhost 7302' %}"""
        device_dict = self.render_device_dictionary('staging-x86-01', data)
        self.assertTrue(validate_device(yaml.load(device_dict)))

    def test_nexus4_template(self):
        data = """{% extends 'nexus4.jinja2' %}
{% set adb_serial_number = 'R32D300FRYP' %}
{% set fastboot_serial_number = 'R32D300FRYP' %}
"""
        self.assertTrue(self.validate_data('nexus4-01', data))
        test_template = prepare_jinja_template('nexus4-01', data)
        rendered = test_template.render()
        template_dict = yaml.load(rendered)
        self.assertEqual('nexus4', template_dict['device_type'])
        self.assertEqual('R32D300FRYP', template_dict['adb_serial_number'])
        self.assertEqual('R32D300FRYP', template_dict['fastboot_serial_number'])
        self.assertEqual([], template_dict['fastboot_options'])

    def test_x15_template(self):
        data = """{% extends 'x15.jinja2' %}
{% set adb_serial_number = 'R32D300FRYP' %}
{% set fastboot_serial_number = 'R32D300FRYP' %}
"""
        self.assertTrue(self.validate_data('x15-01', data))
        test_template = prepare_jinja_template('x15-01', data)
        rendered = test_template.render()
        template_dict = yaml.load(rendered)
        self.assertEqual('x15', template_dict['device_type'])
        self.assertEqual('R32D300FRYP', template_dict['adb_serial_number'])
        self.assertEqual('R32D300FRYP', template_dict['fastboot_serial_number'])
        self.assertEqual([], template_dict['fastboot_options'])
        self.assertIn('u-boot', template_dict['actions']['boot']['methods'])
        self.assertIn('parameters', template_dict['actions']['boot']['methods']['u-boot'])
        self.assertIn('interrupt_prompt', template_dict['actions']['boot']['methods']['u-boot']['parameters'])
        # fastboot deploy to eMMC
        self.assertIn('mmc', template_dict['actions']['boot']['methods']['u-boot'])
        self.assertIn('commands', template_dict['actions']['boot']['methods']['u-boot']['mmc'])
        # NFS using standard U-Boot TFTP
        self.assertIn('nfs', template_dict['actions']['boot']['methods']['u-boot'])
        self.assertIn('commands', template_dict['actions']['boot']['methods']['u-boot']['nfs'])
        for command in template_dict['actions']['boot']['methods']['u-boot']['nfs']['commands']:
            if 'setenv bootargs' in command:
                # x15 needs both consoles enabled.
                self.assertIn('ttyS2', command)
                self.assertNotIn('console=ttyO2', command)

    def test_armada375_template(self):
        """
        Test the armada-375 template as if it was a device dictionary
        """
        data = """
{% extends 'base-uboot.jinja2' %}
{% set console_device = console_device|default('ttyS0') %}
{% set baud_rate = baud_rate|default(115200) %}
{% set device_type = "armada-375-db" %}
{% set bootloader_prompt = bootloader_prompt|default('Marvell>>') %}
{% set bootm_kernel_addr = '0x02080000' %}
{% set bootm_ramdisk_addr = '0x02880000' %}
{% set bootm_dtb_addr = '0x02000000' %}
{% set base_ip_args = 'ip=dhcp' %}
{% set uboot_mkimage_arch = 'arm' %}
{% set append_dtb = true %}
{% set use_xip = true %}
{% set uboot_bootx_cmd = "bootm {KERNEL_ADDR} {RAMDISK_ADDR}" %}
        """
        self.assertTrue(self.validate_data('armada-375-01', data))
        test_template = prepare_jinja_template('armada-375-01', data)
        rendered = test_template.render()
        template_dict = yaml.load(rendered)
        params = template_dict['actions']['deploy']['parameters']
        self.assertIsNotNone(params)
        self.assertIn('use_xip', params)
        self.assertIn('append_dtb', params)
        self.assertTrue(params['use_xip'])
        self.assertTrue(params['append_dtb'])
        params = template_dict['actions']['boot']['methods']['u-boot']['ramdisk']['commands']
        for line in params:
            if 'run loadkernel' in line:
                self.assertIn('bootm', line)

    def test_nexus10_template(self):
        self.assertTrue(self.validate_data('staging-nexus10-01', """{% extends 'nexus10.jinja2' %}
{% set adb_serial_number = 'R32D300FRYP' %}
{% set fastboot_serial_number = 'R32D300FRYP' %}
{% set soft_reboot_command = 'adb -s R32D300FRYP reboot bootloader' %}
{% set connection_command = 'adb -s R32D300FRYP shell' %}
{% set device_info = [{'board_id': 'R32D300FRYP'}] %}
"""))

    def test_x86_template(self):
        data = """{% extends 'x86.jinja2' %}
{% set power_off_command = '/usr/bin/pduclient --daemon localhost --port 02 --hostname lngpdu01 --command off' %}
{% set hard_reset_command = '/usr/bin/pduclient --daemon localhost --port 02 --hostname lngpdu01 --command reboot' %}
{% set power_on_command = '/usr/bin/pduclient --daemon localhost --port 02 --hostname lngpdu01 --command on' %}
{% set connection_command = 'telnet localhost 7302' %}"""
        self.assertTrue(self.validate_data('staging-x86-01', data))
        test_template = prepare_jinja_template('staging-qemu-01', data)
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
        test_template = prepare_jinja_template('staging-qemu-01', data)
        job_ctx = {}
        rendered = test_template.render(**job_ctx)
        template_dict = yaml.load(rendered)

        self.assertIsNotNone(template_dict['actions']['boot']['methods']['ipxe']['nfs']['commands'])

        self.assertIsNotNone(template_dict['timeouts']['connections']['bootloader-commands'])
        self.assertEqual(template_dict['timeouts']['connections']['bootloader-commands']['minutes'], 5)

        # uses default value from template
        self.assertEqual(500, template_dict['character_delays']['boot'])

        # override template in job context
        job_ctx = {'boot_character_delay': 150}
        rendered = test_template.render(**job_ctx)
        template_dict = yaml.load(rendered)
        self.assertEqual(150, template_dict['character_delays']['boot'])

        # add device dictionary override
        # overrides the template default
        data += """{% set boot_character_delay = 400 %}"""
        test_template = prepare_jinja_template('staging-qemu-01', data)
        job_ctx = {}
        rendered = test_template.render(**job_ctx)
        template_dict = yaml.load(rendered)
        self.assertEqual(400, template_dict['character_delays']['boot'])

        # job context does not override device dictionary
        job_ctx = {'boot_character_delay': 150}
        rendered = test_template.render(**job_ctx)
        template_dict = yaml.load(rendered)
        self.assertNotEqual(150, template_dict['character_delays']['boot'])
        self.assertEqual(400, template_dict['character_delays']['boot'])

    def test_x86_interface_template(self):
        # test boot interface override
        data = """{% extends 'x86.jinja2' %}
{% set power_off_command = '/usr/bin/pduclient --daemon localhost --port 02 --hostname lngpdu01 --command off' %}
{% set hard_reset_command = '/usr/bin/pduclient --daemon localhost --port 02 --hostname lngpdu01 --command reboot' %}
{% set power_on_command = '/usr/bin/pduclient --daemon localhost --port 02 --hostname lngpdu01 --command on' %}
{% set connection_command = 'telnet localhost 7302' %}"""
        self.assertTrue(self.validate_data('staging-x86-01', data))
        test_template = prepare_jinja_template('staging-qemu-01', data)
        rendered = test_template.render()
        template_dict = yaml.load(rendered)
        for _, value in template_dict['actions']['boot']['methods']['ipxe'].items():
            if 'commands' in value:
                self.assertIn('dhcp net0', value['commands'])
                self.assertNotIn('dhcp net1', value['commands'])
        # test boot interface override
        data = """{% extends 'x86.jinja2' %}
{% set boot_interface = 'net1' %}
{% set power_off_command = '/usr/bin/pduclient --daemon localhost --port 02 --hostname lngpdu01 --command off' %}
{% set hard_reset_command = '/usr/bin/pduclient --daemon localhost --port 02 --hostname lngpdu01 --command reboot' %}
{% set power_on_command = '/usr/bin/pduclient --daemon localhost --port 02 --hostname lngpdu01 --command on' %}
{% set connection_command = 'telnet localhost 7302' %}"""
        self.assertTrue(self.validate_data('staging-x86-01', data))
        test_template = prepare_jinja_template('staging-qemu-01', data)
        rendered = test_template.render()
        template_dict = yaml.load(rendered)
        for _, value in template_dict['actions']['boot']['methods']['ipxe'].items():
            if 'commands' in value:
                self.assertIn('dhcp net1', value['commands'])
                self.assertNotIn('dhcp net0', value['commands'])

    def test_thunderx_template(self):
        data = """{% extends 'thunderx.jinja2' %}
{% set map = {'iface0': {'lngswitch03': 13}, 'iface1': {'lngswitch03': 1}, 'iface2': {'lngswitch02': 9}, 'iface3': {'lngswitch02': 10}} %}
{% set tags = {'iface0': [], 'iface1': ['RJ45', '1G', '10G'], 'iface2': ['SFP+', '1G', '10G'], 'iface3': ['SFP+', '1G', '10G']} %}
{% set mac_addr = {'iface0': '00:00:1a:1b:8b:f6', 'iface1': '00:00:1a:1b:8b:f7', 'iface2': '00:11:0a:68:94:30', 'iface3': '00:11:0a:68:94:31'} %}
{% set interfaces = ['iface0', 'iface1', 'iface2', 'iface3'] %}
{% set sysfs = {'iface0': '/sys/devices/platform/AMDI8001:00/net/',
'iface1': '/sys/devices/platform/AMDI8001:01/net/',
'iface2': '/sys/devices/pci0000:00/0000:00:02.1/0000:01:00.0/net/',
'iface3': '/sys/devices/pci0000:00/0000:00:02.1/0000:01:00.1/net/'} %}
{% set hard_reset_command = '/usr/bin/pduclient --daemon localhost --hostname lngpdu01 --command reboot --port 19' %}
{% set power_off_command = '/usr/bin/pduclient --daemon localhost --hostname lngpdu01 --command off --port 19' %}
{% set power_on_command = '/usr/bin/pduclient --daemon localhost --hostname lngpdu01 --command on --port 19' %}
{% set connection_command = 'telnet localhost 7333' %}
{% set exclusive = 'True' %}"""
        self.assertTrue(self.validate_data('staging-thunderx-01', data))
        test_template = prepare_jinja_template('staging-thunderx-01', data)
        rendered = test_template.render()
        template_dict = yaml.load(rendered)
        self.assertIn('character_delays', template_dict)
        self.assertIn('boot', template_dict['character_delays'])
        self.assertEqual(150, template_dict['character_delays']['boot'])
        self.assertIn('interfaces', template_dict['parameters'])
        self.assertIn('iface2', template_dict['parameters']['interfaces'])
        self.assertIn('iface1', template_dict['parameters']['interfaces'])
        self.assertIn('iface0', template_dict['parameters']['interfaces'])
        self.assertIn('sysfs', template_dict['parameters']['interfaces']['iface2'])

    def test_beaglebone_black_template(self):
        data = """{% extends 'beaglebone-black.jinja2' %}
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
{% set exclusive = 'True' %}"""
        self.assertTrue(self.validate_data('staging-bbb-01', data))
        test_template = prepare_jinja_template('staging-bbb-01', data)
        rendered = test_template.render()
        template_dict = yaml.load(rendered)
        self.assertIsNotNone(template_dict['actions']['deploy']['methods']['ssh']['host'])
        self.assertEqual('', template_dict['actions']['deploy']['methods']['ssh']['host'])
        self.assertNotEqual('None', template_dict['actions']['deploy']['methods']['ssh']['host'])
        data += "{% set ssh_host = '192.168.0.10' %}"
        test_template = prepare_jinja_template('staging-bbb-01', data)
        rendered = test_template.render()
        template_dict = yaml.load(rendered)
        self.assertIsNotNone(template_dict['actions']['deploy']['methods']['ssh']['host'])
        self.assertEqual('192.168.0.10', template_dict['actions']['deploy']['methods']['ssh']['host'])

    def test_b2260_template(self):
        data = """{% extends 'b2260.jinja2' %}"""
        self.assertTrue(self.validate_data('staging-b2260-01', data))
        test_template = prepare_jinja_template('staging-qemu-01', data)
        rendered = test_template.render()
        template_dict = yaml.load(rendered)
        self.assertEqual({'seconds': 15}, template_dict['timeouts']['actions']['power-off'])

    def test_qemu_template(self):
        data = """{% extends 'qemu.jinja2' %}
{% set exclusive = 'True' %}
{% set mac_addr = 'DE:AD:BE:EF:28:01' %}
{% set memory = 512 %}"""
        job_ctx = {'arch': 'amd64', 'no_kvm': True}
        self.assertTrue(self.validate_data('staging-x86-01', data, job_ctx))
        test_template = prepare_jinja_template('staging-qemu-01', data)
        rendered = test_template.render(**job_ctx)
        template_dict = yaml.load(rendered)
        options = template_dict['actions']['boot']['methods']['qemu']['parameters']['options']
        self.assertNotIn('-enable-kvm', options)
        job_ctx = {'arch': 'amd64', 'no_kvm': False}
        rendered = test_template.render(**job_ctx)
        template_dict = yaml.load(rendered)
        options = template_dict['actions']['boot']['methods']['qemu']['parameters']['options']
        self.assertIn('-enable-kvm', options)

    def test_qemu_installer(self):
        data = """{% extends 'qemu.jinja2' %}
{% set exclusive = 'True' %}
{% set mac_addr = 'DE:AD:BE:EF:28:01' %}
{% set memory = 512 %}"""
        job_ctx = {'arch': 'amd64'}
        test_template = prepare_jinja_template('staging-qemu-01', data)
        rendered = test_template.render(**job_ctx)
        template_dict = yaml.load(rendered)
        self.assertEqual(
            'c',
            template_dict['actions']['boot']['methods']['qemu']['parameters']['boot_options']['boot_order']
        )

    def test_mustang_template(self):
        data = """{% extends 'mustang.jinja2' %}
{% set connection_command = 'telnet serial4 7012' %}
{% set hard_reset_command = '/usr/bin/pduclient --daemon staging-master --hostname pdu15 --command reboot --port 05' %}
{% set power_off_command = '/usr/bin/pduclient --daemon staging-master --hostname pdu15 --command off --port 05' %}
{% set power_on_command = '/usr/bin/pduclient --daemon staging-master --hostname pdu15 --command on --port 05' %}"""
        self.assertTrue(self.validate_data('staging-mustang-01', data))
        test_template = prepare_jinja_template('staging-mustang-01', data)
        rendered = test_template.render()
        template_dict = yaml.load(rendered)
        self.assertIsInstance(template_dict['parameters']['text_offset'], str)
        commands = template_dict['actions']['boot']['methods']['u-boot']['ramdisk']['commands']
        for line in commands:
            if 'setenv initrd_high' in line:
                self.fail('Mustang should not have initrd_high set')
            if 'setenv fdt_high' in line:
                self.fail('Mustang should not have fdt_high set')

    def test_mustang_pxe_grub_efi_template(self):
        data = """{% extends 'mustang-grub-efi.jinja2' %}
{% set exclusive = 'True' %}
{% set hard_reset_command = '/usr/bin/pduclient --daemon services --hostname pdu09 --command reboot --port 05' %}
{% set power_off_command = '/usr/bin/pduclient --daemon services --hostname pdu09 --command off --port 05' %}
{% set power_on_command = '/usr/bin/pduclient --daemon services --hostname pdu09 --command on --port 05' %}
{% set connection_command = 'telnet localhost 7012' %}"""
        self.assertTrue(self.validate_data('staging-mustang-01', data))
        test_template = prepare_jinja_template('staging-mustang-01', data)
        rendered = test_template.render()
        template_dict = yaml.load(rendered)
        self.assertIn('uefi-menu', template_dict['actions']['boot']['methods'])
        self.assertIn('pxe-grub', template_dict['actions']['boot']['methods']['uefi-menu'])
        self.assertNotIn('grub', template_dict['actions']['boot']['methods']['uefi-menu'])
        # label class regex is mangled by jinja/yaml processing
        self.assertNotIn('label_class', template_dict['actions']['boot']['methods']['uefi-menu']['parameters'])
        self.assertIn('grub-efi', template_dict['actions']['boot']['methods'])
        self.assertIn('menu_options', template_dict['actions']['boot']['methods']['grub-efi'])
        self.assertEqual(template_dict['actions']['boot']['methods']['grub-efi']['menu_options'], 'pxe-grub')
        self.assertIn('ramdisk', template_dict['actions']['boot']['methods']['grub-efi'])
        self.assertIn('commands', template_dict['actions']['boot']['methods']['grub-efi']['ramdisk'])
        self.assertIn('nfs', template_dict['actions']['boot']['methods']['grub-efi'])
        self.assertIn('commands', template_dict['actions']['boot']['methods']['grub-efi']['nfs'])
        nfs_commands = template_dict['actions']['boot']['methods']['grub-efi']['nfs']['commands']
        self.assertNotIn('insmod efinet', nfs_commands)
        self.assertNotIn('net_bootp', nfs_commands)

    def test_mustang_grub_efi_template(self):
        data = """{% extends 'mustang-grub-efi.jinja2' %}
{% set exclusive = 'True' %}
{% set grub_efi_method = 'grub' %}
{% set hard_reset_command = '/usr/bin/pduclient --daemon services --hostname pdu09 --command reboot --port 05' %}
{% set power_off_command = '/usr/bin/pduclient --daemon services --hostname pdu09 --command off --port 05' %}
{% set power_on_command = '/usr/bin/pduclient --daemon services --hostname pdu09 --command on --port 05' %}
{% set connection_command = 'telnet localhost 7012' %}"""
        self.assertTrue(self.validate_data('staging-mustang-01', data))
        test_template = prepare_jinja_template('staging-mustang-01', data)
        rendered = test_template.render()
        template_dict = yaml.load(rendered)
        self.assertIn('uefi-menu', template_dict['actions']['boot']['methods'])
        self.assertNotIn('pxe-grub', template_dict['actions']['boot']['methods']['uefi-menu'])
        self.assertIn('grub', template_dict['actions']['boot']['methods']['uefi-menu'])
        self.assertEqual(template_dict['actions']['boot']['methods']['grub-efi']['menu_options'], 'grub')
        self.assertIn('ramdisk', template_dict['actions']['boot']['methods']['grub-efi'])
        self.assertIn('commands', template_dict['actions']['boot']['methods']['grub-efi']['ramdisk'])
        self.assertIn('nfs', template_dict['actions']['boot']['methods']['grub-efi'])
        self.assertIn('commands', template_dict['actions']['boot']['methods']['grub-efi']['nfs'])
        nfs_commands = template_dict['actions']['boot']['methods']['grub-efi']['nfs']['commands']
        self.assertIn('insmod efinet', nfs_commands)
        self.assertIn('net_bootp', nfs_commands)

    def test_mustang_secondary_media(self):
        data = """{% extends 'mustang-grub-efi.jinja2' %}
{% set exclusive = 'True' %}
{% set sata_label = 'ST500DM002' %}
{% set sata_uuid = 'ata-ST500DM002-1BD142_S2AKYFSN' %}
{% set grub_efi_method = 'pxe-grub' %}
{% set hard_reset_command = '/usr/bin/pduclient --daemon services --hostname pdu09 --command reboot --port 05' %}
{% set power_off_command = '/usr/bin/pduclient --daemon services --hostname pdu09 --command off --port 05' %}
{% set power_on_command = '/usr/bin/pduclient --daemon services --hostname pdu09 --command on --port 05' %}
{% set connection_command = 'telnet localhost 7012' %}"""
        self.assertTrue(self.validate_data('staging-mustang-01', data))
        test_template = prepare_jinja_template('staging-mustang-01', data)
        rendered = test_template.render()
        template_dict = yaml.load(rendered)
        parameters = {
            'parameters': {
                'media': {
                    'sata': {
                        'ST500DM002': {
                            'boot_part': 1,
                            'device_id': 0,
                            'grub_interface': 'hd0',
                            'uboot_interface': 'scsi',
                            'uuid': 'ata-ST500DM002-1BD142_S2AKYFSN'
                        },
                        'UUID-required': True
                    }
                }
            }
        }
        self.assertTrue(template_dict['parameters'] == parameters['parameters'])
        self.assertIn('sata', template_dict['actions']['boot']['methods']['grub-efi'])
        commands = {
            'commands': [
                'insmod gzio',
                'linux (hd0,gpt1)/{KERNEL} console=ttyS0,115200n8 debug root=/dev/sda2 rw ip=:::::eth0:dhcp',
                'initrd (hd0,gpt1/{RAMDISK}',
                'boot']}
        self.assertEqual(
            commands,
            template_dict['actions']['boot']['methods']['grub-efi']['sata']
        )

    def test_hikey_template(self):
        with open(os.path.join(os.path.dirname(__file__), 'devices', 'hi6220-hikey-01.jinja2')) as hikey:
            data = hikey.read()
        self.assertIsNotNone(data)
        self.assertTrue(self.validate_data('hi6220-hikey-01', data))
        test_template = prepare_jinja_template('staging-hikey-01', data)
        rendered = test_template.render()
        template_dict = yaml.load(rendered)
        self.assertIsNotNone(template_dict)
        self.assertIsInstance(template_dict['device_info'], list)
        self.assertEqual(template_dict['device_info'][0]['board_id'],
                         '0123456789')
        self.assertIsInstance(template_dict['fastboot_options'], list)
        self.assertEqual(template_dict['fastboot_options'], ['-S', '256M'])
        order = template_dict['flash_cmds_order']
        self.assertEqual(0, order.index('ptable'))
        self.assertEqual(1, order.index('fastboot'))
        self.assertIn('cache', order)
        self.assertIn('system', order)
        self.assertIn('userdata', order)

        # test support for retreiving MAC from device.
        data += "{% set device_mac = '00:E0:4C:53:44:58' %}"
        self.assertTrue(self.validate_data('hi6220-hikey-01', data))
        test_template = prepare_jinja_template('staging-hikey-01', data)
        rendered = test_template.render()
        template_dict = yaml.load(rendered)
        self.assertIn('parameters', template_dict)
        self.assertIn('interfaces', template_dict['parameters'])
        self.assertIn('target', template_dict['parameters']['interfaces'])
        self.assertIn('mac', template_dict['parameters']['interfaces']['target'])
        self.assertIn('ip', template_dict['parameters']['interfaces']['target'])
        self.assertIsNotNone(template_dict['parameters']['interfaces']['target']['mac'])
        self.assertNotEqual('', template_dict['parameters']['interfaces']['target']['mac'])
        self.assertIsNone(template_dict['parameters']['interfaces']['target']['ip'])

    def test_hikey_grub_efi(self):
        with open(os.path.join(os.path.dirname(__file__), 'devices', 'hi6220-hikey-01.jinja2')) as hikey:
            data = hikey.read()
        self.assertIsNotNone(data)
        job_ctx = {
            'kernel': 'Image',
            'devicetree': 'hi6220-hikey.dtb'
        }
        self.assertTrue(self.validate_data('hi6220-hikey-01', data))
        test_template = prepare_jinja_template('staging-hikey-01', data)
        rendered = test_template.render(**job_ctx)
        template_dict = yaml.load(rendered)
        self.assertIsNotNone(template_dict)
        self.assertIsNotNone(template_dict['actions']['boot']['methods'])
        self.assertIn('grub-efi', template_dict['actions']['boot']['methods'])
        self.assertEqual('fastboot', template_dict['actions']['boot']['methods']['grub-efi']['menu_options'])
        params = template_dict['actions']['boot']['methods']['grub-efi']
        self.assertEqual(params['parameters']['bootloader_prompt'], 'grub>')
        for command in params['installed']['commands']:
            if command.startswith('search'):
                self.assertIn('rootfs', command)
            elif command.startswith('linux'):
                self.assertIn('/boot/Image', command)
            elif command.startswith('devicetree'):
                self.assertIn('hi6220-hikey.dtb', command)
            elif 'root=' in command:
                self.assertIn('/dev/mmcblk0p9', command)
                self.assertIn('ttyAMA3', command)
            else:
                self.assertEqual('boot', command)
        self.assertIn('ssh', template_dict['actions']['deploy']['methods'])
        params = template_dict['actions']['deploy']['methods']['ssh']
        self.assertIsNotNone(params)
        self.assertIn('port', params)
        self.assertIn('user', params)
        self.assertIn('options', params)
        self.assertIn('identity_file', params)

    def test_hikey620_uarts(self):
        with open(os.path.join(os.path.dirname(__file__), 'devices', 'hi6220-hikey-01.jinja2')) as hikey:
            data = hikey.read()
        self.assertIsNotNone(data)
        job_ctx = {}
        self.assertTrue(self.validate_data('hi6220-hikey-01', data))
        test_template = prepare_jinja_template('staging-hikey-01', data)
        rendered = test_template.render(**job_ctx)
        template_dict = yaml.load(rendered)
        validate_device(template_dict)
        self.assertIsNotNone(template_dict)
        self.assertIn('commands', template_dict)
        self.assertNotIn('connect', template_dict['commands'])
        self.assertIn('connections', template_dict['commands'])
        self.assertIn('uart0', template_dict['commands']['connections'])
        self.assertIn('uart1', template_dict['commands']['connections'])
        self.assertIn('tags', template_dict['commands']['connections']['uart1'])
        self.assertIn('primary', template_dict['commands']['connections']['uart1']['tags'])
        self.assertNotIn('tags', template_dict['commands']['connections']['uart0'])
        self.assertEqual(
            template_dict['commands']['connections']['uart0']['connect'],
            'telnet localhost 4002')
        self.assertEqual(
            template_dict['commands']['connections']['uart1']['connect'],
            'telnet 192.168.1.200 8001')

    def test_hikey960_grub(self):
        with open(os.path.join(os.path.dirname(__file__), 'devices', 'hi960-hikey-01.jinja2')) as hikey:
            data = hikey.read()
        self.assertIsNotNone(data)
        job_ctx = {
            'kernel': 'Image',
            'devicetree': 'hi960-hikey.dtb'
        }
        # self.assertTrue(self.validate_data('hi960-hikey-01', data))
        test_template = prepare_jinja_template('staging-hikey-01', data)
        rendered = test_template.render(**job_ctx)
        template_dict = yaml.load(rendered)
        self.assertIsNotNone(template_dict)
        self.assertIsNotNone(template_dict['actions']['boot']['methods'])
        self.assertNotIn('menu_options', template_dict['actions']['boot']['methods']['grub'])
        self.assertIn('grub', template_dict['actions']['boot']['methods'])
        params = template_dict['actions']['boot']['methods']['grub']
        for command in params['installed']['commands']:
            self.assertEqual('boot', command)
        self.assertIn('ssh', template_dict['actions']['deploy']['methods'])
        params = template_dict['actions']['deploy']['methods']['ssh']
        self.assertIsNotNone(params)
        self.assertIn('port', params)
        self.assertIn('user', params)
        self.assertIn('options', params)
        self.assertIn('identity_file', params)

    def test_panda_template(self):
        logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
        logger = logging.getLogger('unittests')
        logger.disabled = True
        logger.propagate = False
        data = """{% extends 'panda.jinja2' %}
{% set connection_command = 'telnet serial4 7012' %}
{% set hard_reset_command = '/usr/bin/pduclient --daemon staging-master --hostname pdu15 --command reboot --port 05' %}
{% set power_off_command = '/usr/bin/pduclient --daemon staging-master --hostname pdu15 --command off --port 05' %}
{% set power_on_command = '/usr/bin/pduclient --daemon staging-master --hostname pdu15 --command on --port 05' %}"""
        self.assertTrue(self.validate_data('staging-panda-01', data))
        context = {'extra_kernel_args': 'intel_mmio=on mmio=on'}
        test_template = prepare_jinja_template('staging-panda-01', data)
        rendered = test_template.render(**context)
        template_dict = yaml.load(rendered)
        self.assertEqual('panda', (template_dict['device_type']))
        self.assertIn('bootloader-commands', template_dict['timeouts']['actions'])
        self.assertEqual(180.0, Timeout.parse(template_dict['timeouts']['actions']['bootloader-commands']))
        commands = template_dict['actions']['boot']['methods']['u-boot']['ramdisk']['commands']
        checked = False
        self.assertIsNotNone(commands)
        self.assertIsInstance(commands, list)
        self.assertIn('usb start', commands)
        for line in commands:
            if 'setenv bootargs' in line:
                self.assertIn('console=ttyO2', line)
                self.assertIn(' ' + context['extra_kernel_args'] + ' ', line)
                checked = True
        self.assertTrue(checked)
        checked = False
        for line in commands:
            if 'setenv initrd_high' in line:
                checked = True
        self.assertTrue(checked)

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
        test_template = prepare_jinja_template('staging-juno-01', data)
        rendered = test_template.render()
        template_dict = yaml.load(rendered)
        self.assertIsNotNone(template_dict)

    def test_cubietruck_template(self):
        data = """{% extends 'cubietruck.jinja2' %}
{% set usb_label = 'SanDisk_Ultra' %}
{% set sata_label = 'ST160LM003' %}
{% set uuid_required = False %}
{% set usb_uuid = "usb-SanDisk_Ultra_20060775320F43006019-0:0" %}
{% set sata_uuid = "ata-ST160LM003_HN-M160MBB_S2SYJ9KC102184" %}
{% set connection_command = 'telnet localhost 6002' %}
{% set console_device = 'ttyfake1' %}"""
        self.assertTrue(self.validate_data('staging-cubietruck-01', data))
        test_template = prepare_jinja_template('staging-cubietruck-01', data)
        rendered = test_template.render()
        template_dict = yaml.load(rendered)
        self.assertIsNotNone(template_dict)
        self.assertIn('u-boot', template_dict['actions']['boot']['methods'])
        self.assertIn('SanDisk_Ultra', template_dict['parameters']['media']['usb'])
        self.assertEqual(template_dict['parameters']['media']['usb']['SanDisk_Ultra']['device_id'], 0)
        self.assertEqual(template_dict['parameters']['media']['usb']['SanDisk_Ultra']['uuid'],
                         'usb-SanDisk_Ultra_20060775320F43006019-0:0')
        self.assertIn('ST160LM003', template_dict['parameters']['media']['sata'])
        self.assertIn('uboot_interface', template_dict['parameters']['media']['sata']['ST160LM003'])
        self.assertEqual('scsi', template_dict['parameters']['media']['sata']['ST160LM003']['uboot_interface'])
        self.assertIn('uuid', template_dict['parameters']['media']['sata']['ST160LM003'])
        self.assertIn('ata-ST160LM003_HN-M160MBB_S2SYJ9KC102184',
                      template_dict['parameters']['media']['sata']['ST160LM003']['uuid'])
        self.assertIn('ssh', template_dict['actions']['boot']['methods'])

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
        test_template = prepare_jinja_template('staging-juno-01', data)
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

    def test_qemu_cortex_a57_nfs(self):
        data = """{% extends 'qemu.jinja2' %}
{% set memory = 2048 %}
{% set mac_addr = '52:54:00:12:34:59' %}
{% set arch = 'arm64' %}
{% set base_guest_fs_size = 2048 %}
        """
        job_ctx = {
            'arch': 'amd64',
            'qemu_method': 'qemu-nfs',
            'netdevice': 'tap',
            'extra_options': ['-smp', 1]
        }
        self.assertTrue(self.validate_data('staging-qemu-01', data))
        test_template = prepare_jinja_template('staging-juno-01', data)
        rendered = test_template.render(**job_ctx)
        self.assertIsNotNone(rendered)
        template_dict = yaml.load(rendered)
        self.assertIn('qemu-nfs', template_dict['actions']['boot']['methods'])
        params = template_dict['actions']['boot']['methods']['qemu-nfs']['parameters']
        self.assertIn('command', params)
        self.assertEqual(params['command'], 'qemu-system-aarch64')
        self.assertIn('options', params)
        self.assertIn('-cpu cortex-a57', params['options'])
        self.assertEqual('qemu-system-aarch64', params['command'])
        self.assertIn('-smp', params['extra'])
        self.assertIn('append', params)
        self.assertIn('nfsrootargs', params['append'])
        self.assertEqual(params['append']['root'], '/dev/nfs')
        self.assertEqual(params['append']['console'], 'ttyAMA0')

    def test_overdrive_template(self):
        data = """{% extends 'overdrive.jinja2' %}
{% set connection_command = 'telnet serial4 7001' %}
{% set hard_reset_command = '/usr/local/lab-scripts/snmp_pdu_control --hostname pdu18 --command reboot --port 10 --delay 10' %}
{% set power_off_command = '/usr/local/lab-scripts/snmp_pdu_control --hostname pdu18 --command off --port 10 --delay 10' %}
{% set power_on_command = '/usr/local/lab-scripts/snmp_pdu_control --hostname pdu18 --command on --port 10 --delay 10' %}
{% set map = {'iface0': {'lngswitch03': 13}, 'iface1': {'lngswitch03': 1}, 'iface2': {'lngswitch02': 9}, 'iface3': {'lngswitch02': 10}} %}
{% set tags = {'iface0': [], 'iface1': ['RJ45', '1G', '10G'], 'iface2': ['SFP+', '1G', '10G'], 'iface3': ['SFP+', '1G', '10G']} %}
{% set mac_addr = {'iface0': '00:00:1a:1b:8b:f6', 'iface1': '00:00:1a:1b:8b:f7', 'iface2': '00:11:0a:68:94:30', 'iface3': '00:11:0a:68:94:31'} %}
{% set interfaces = ['iface0', 'iface1', 'iface2', 'iface3'] %}
{% set sysfs = {'iface0': '/sys/devices/platform/AMDI8001:00/net/',
'iface1': '/sys/devices/platform/AMDI8001:01/net/',
'iface2': '/sys/devices/pci0000:00/0000:00:02.1/0000:01:00.0/net/',
'iface3': '/sys/devices/pci0000:00/0000:00:02.1/0000:01:00.1/net/'} %}
{% set boot_character_delay = 100 %}"""
        self.assertTrue(self.validate_data('staging-overdrive-01', data))
        test_template = prepare_jinja_template('staging-overdrive-01', data)
        rendered = test_template.render()
        template_dict = yaml.load(rendered)
        self.assertIsNotNone(template_dict)
        self.assertIn('parameters', template_dict)
        self.assertIn('interfaces', template_dict['parameters'])
        self.assertIn('actions', template_dict)
        self.assertIn('character_delays', template_dict)
        self.assertIn('boot', template_dict['character_delays'])
        self.assertEqual(100, template_dict['character_delays']['boot'])
        self.assertIn('iface2', template_dict['parameters']['interfaces'])
        self.assertIn('iface1', template_dict['parameters']['interfaces'])
        self.assertIn('iface0', template_dict['parameters']['interfaces'])
        self.assertIn('sysfs', template_dict['parameters']['interfaces']['iface2'])
        self.assertEqual(
            [check for check in template_dict['actions']['boot']['methods']['grub']['nfs']['commands'] if 'nfsroot' in check][0].count('nfsroot'),
            1
        )
        self.assertIn(
            ' rw',
            [check for check in template_dict['actions']['boot']['methods']['grub']['nfs']['commands'] if 'nfsroot' in check][0]
        )

    def test_highbank_template(self):
        data = """{% extends 'highbank.jinja2' %}
{% set connection_command = 'ipmitool -I lanplus -U admin -P admin -H calxeda02-07-02 sol activate' %}
{% set power_off_command = 'ipmitool -H calxeda02-07-02 -U admin -P admin chassis power off' %}
{% set power_on_command = 'ipmitool -H calxeda02-07-02 -U admin -P admin chassis power on' %}
{% set hard_reset_command = 'ipmitool -H calxeda02-07-02 -U admin -P admin chassis power off; sleep 20; ipmitool -H calxeda02-07-02 -U admin -P admin chassis power on' %}"""
        self.assertTrue(self.validate_data('highbank-07', data))
        test_template = prepare_jinja_template('highbank-07', data)
        rendered = test_template.render()
        template_dict = yaml.load(rendered)
        self.assertIsNotNone(template_dict)
        self.assertEqual(template_dict['character_delays']['boot'], 100)
        self.assertEqual(template_dict['actions']['boot']['methods']['u-boot']['parameters']['bootloader_prompt'], 'Highbank')
        self.assertEqual(template_dict['actions']['boot']['methods']['u-boot']['parameters']['interrupt_char'], 's')

    def test_extended_x86_template(self):
        data = """{% extends 'x86.jinja2' %}
{% set map = {'MAC 94 (SFP+)': {'lngswitch02': 3},
'MAC 95 (SFP+)': {'lngswitch02': 4},
'MAC d6': {'lngswitch01': 12},
'MAC d7': {'lngswitch01': 13},
'MAC e8': {'lngswitch01': 11},
'MAC e9': {'lngswitch01': 10},
'MAC ea': {'lngswitch01': 9},
'MAC eb': {'lngswitch01': 8}} %}
{% set hard_reset_command = '/usr/local/lab-scripts/snmp_pdu_control --port 1 --hostname lngpdu01 --command reboot' %}
{% set tags = {'MAC 94 (SFP+)': ['SFP+', '1G', '10G'],
'MAC 95 (SFP+)': ['SFP+', '1G', '10G'],
'MAC d6': ['RJ45', '10M', '100M', '1G'],
'MAC d7': ['RJ45', '10M', '100M', '1G'],
'MAC e8': [],
'MAC e9': ['RJ45', '10M', '100M', '1G'],
'MAC ea': ['RJ45', '10M', '100M', '1G'],
'MAC eb': ['RJ45', '10M', '100M', '1G']} %}
{% set interfaces = ['MAC eb',
'MAC ea',
'MAC e9',
'MAC e8',
'MAC d6',
'MAC d7',
'MAC 94 (SFP+)',
'MAC 95 (SFP+)'] %}
{% set sysfs = {'MAC 94 (SFP+)': '/sys/devices/pci0000:00/0000:00:01.0/0000:04:00.1/net/',
'MAC 95 (SFP+)': '/sys/devices/pci0000:00/0000:00:01.0/0000:04:00.0/net/',
'MAC d6': '/sys/devices/pci0000:00/0000:00:03.0/0000:07:00.0/net/',
'MAC d7': '/sys/devices/pci0000:00/0000:00:03.0/0000:07:00.1/net/',
'MAC e8': '/sys/devices/pci0000:00/0000:00:02.0/0000:03:00.0/net/',
'MAC e9': '/sys/devices/pci0000:00/0000:00:02.0/0000:03:00.1/net/',
'MAC ea': '/sys/devices/pci0000:00/0000:00:02.0/0000:03:00.2/net/',
'MAC eb': '/sys/devices/pci0000:00/0000:00:02.0/0000:03:00.3/net/'} %}
{% set power_off_command = '/usr/local/lab-scripts/snmp_pdu_control --port 1 --hostname lngpdu01 --command off' %}
{% set mac_addr = {'MAC 94 (SFP+)': '38:ea:a7:93:98:94',
'MAC 95 (SFP+)': '38:ea:a7:93:98:95',
'MAC d6': 'a0:36:9f:39:0b:d6',
'MAC d7': 'a0:36:9f:39:0b:d7',
'MAC e8': 'd8:9d:67:26:ae:e8',
'MAC e9': 'd8:9d:67:26:ae:e9',
'MAC ea': 'd8:9d:67:26:ae:ea',
'MAC eb': 'd8:9d:67:26:ae:eb'} %}
{% set power_on_command = '/usr/local/lab-scripts/snmp_pdu_control --port 1 --hostname lngpdu01 --command on' %}
{% set connection_command = 'telnet localhost 7301' %}
{% set lava_mac = 'd8:9d:67:26:ae:e8' %}"""
        self.assertTrue(self.validate_data('staging-x86-01', data))
        test_template = prepare_jinja_template('staging-qemu-01', data)
        rendered = test_template.render()
        template_dict = yaml.load(rendered)
        self.assertIn(
            'set console console=ttyS0,115200n8 lava_mac={LAVA_MAC}',
            template_dict['actions']['boot']['methods']['ipxe']['nfs']['commands'])
        context = {'extra_kernel_args': 'intel_mmio=on mmio=on'}
        rendered = test_template.render(**context)
        template_dict = yaml.load(rendered)
        self.assertIn(
            'set extraargs root=/dev/nfs rw nfsroot={NFS_SERVER_IP}:{NFSROOTFS},tcp,hard,intr intel_mmio=on mmio=on ip=dhcp',
            template_dict['actions']['boot']['methods']['ipxe']['nfs']['commands'])

    def test_extra_nfs_opts(self):
        data = """{% extends 'panda.jinja2' %}
{% set connection_command = 'telnet serial4 7012' %}
{% set hard_reset_command = '/usr/bin/pduclient --daemon staging-master --hostname pdu15 --command reboot --port 05' %}
{% set power_off_command = '/usr/bin/pduclient --daemon staging-master --hostname pdu15 --command off --port 05' %}
{% set power_on_command = '/usr/bin/pduclient --daemon staging-master --hostname pdu15 --command on --port 05' %}"""
        job_ctx = {}
        test_template = prepare_jinja_template('staging-panda-01', data)
        rendered = test_template.render(**job_ctx)
        template_dict = yaml.load(rendered)
        for line in template_dict['actions']['boot']['methods']['u-boot']['nfs']['commands']:
            if line.startswith("setenv nfsargs"):
                self.assertIn(',tcp,hard,intr ', line)
                self.assertNotIn('nfsvers', line)
        job_ctx = {'extra_nfsroot_args': ',nolock,nfsvers=3'}
        test_template = prepare_jinja_template('staging-panda-01', data)
        rendered = test_template.render(**job_ctx)
        template_dict = yaml.load(rendered)
        for line in template_dict['actions']['boot']['methods']['u-boot']['nfs']['commands']:
            if line.startswith("setenv nfsargs"):
                self.assertIn(',tcp,hard,intr,nolock,nfsvers=3 ', line)
        commands = template_dict['actions']['boot']['methods']['u-boot']['ramdisk']['commands']
        checked = False
        for line in commands:
            if 'setenv initrd_high' in line:
                checked = True
        self.assertTrue(checked)

    def test_juno_uboot_vland_template(self):
        data = """{% extends 'juno-uboot.jinja2' %}
{% set map = {'iface0': {'lngswitch03': 19}, 'iface1': {'lngswitch03': 8}} %}
{% set hard_reset_command = '/usr/local/lab-scripts/snmp_pdu_control --hostname lngpdu01 --command reboot --port 19' %}
{% set tags = {'iface0': [], 'iface1': ['RJ45', '10M', '100M']} %}
{% set interfaces = ['iface0', 'iface1'] %}
{% set device_mac = '90:59:af:5e:69:fd' %}
{% set sysfs = {'iface0': '/sys/devices/platform/ocp/4a100000.ethernet/net/',
'iface1': '/sys/devices/platform/ocp/47400000.usb/47401c00.usb/musb-hdrc.1.auto/usb1/1-1/1-1:1.0/net/'} %}
{% set power_off_command = '/usr/local/lab-scripts/snmp_pdu_control --hostname lngpdu01 --command off --port 19' %}
{% set mac_addr = {'iface0': '90:59:af:5e:69:fd', 'iface1': '00:e0:4c:53:44:58'} %}
{% set power_on_command = '/usr/local/lab-scripts/snmp_pdu_control --hostname lngpdu01 --command on --port 19' %}
{% set connection_command = 'telnet localhost 7333' %}
{% set exclusive = 'True' %}"""
        self.assertTrue(self.validate_data('staging-x86-01', data))
        test_template = prepare_jinja_template('staging-qemu-01', data)
        rendered = test_template.render()
        template_dict = yaml.load(rendered)
        self.assertIn('interfaces', template_dict['parameters'])
        self.assertIn('iface0', template_dict['parameters']['interfaces'])
        self.assertIn('port', template_dict['parameters']['interfaces']['iface0'])
        self.assertIn('target', template_dict['parameters']['interfaces'])
        self.assertIn('ip', template_dict['parameters']['interfaces']['target'])
        self.assertIsNone(template_dict['parameters']['interfaces']['target']['ip'])
        self.assertIsNotNone(template_dict['parameters']['interfaces']['target']['mac'])

    @unittest.skipIf(infrastructure_error('lxc-info'), "lxc-info not installed")
    def test_panda_lxc_template(self):
        logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
        logger = logging.getLogger('unittests')
        logger.disabled = True
        logger.propagate = False
        logger = logging.getLogger('dispatcher')
        logging.disable(logging.DEBUG)
        logger.disabled = True
        logger.propagate = False
        data = """{% extends 'panda.jinja2' %}
{% set power_off_command = '/usr/local/lab-scripts/snmp_pdu_control --hostname pdu15 --command off --port 07' %}
{% set hard_reset_command = '/usr/local/lab-scripts/snmp_pdu_control --hostname pdu15 --command reboot --port 07' %}
{% set connection_command = 'telnet serial4 7010' %}
{% set power_on_command = '/usr/local/lab-scripts/snmp_pdu_control --hostname pdu15 --command on --port 07' %}"""
        self.assertTrue(self.validate_data('staging-panda-01', data))
        test_template = prepare_jinja_template('staging-panda-01', data)
        rendered = test_template.render()
        template_dict = yaml.load(rendered)
        fdesc, device_yaml = tempfile.mkstemp()
        os.write(fdesc, yaml.dump(template_dict))
        panda = NewDevice(device_yaml)
        lxc_yaml = os.path.join(os.path.dirname(__file__), 'devices', 'panda-lxc-aep.yaml')
        with open(lxc_yaml) as sample_job_data:
            parser = JobParser()
            job = parser.parse(sample_job_data, panda, 4577, None, "",
                               output_dir='/tmp')
        os.close(fdesc)
        job.logger = DummyLogger()
        job.logger.disabled = True
        job.logger.propagate = False
        job.validate()

    def test_ethaddr(self):
        data = """{% extends 'b2260.jinja2' %}
{% set hard_reset_command = '/usr/local/lab-scripts/snmp_pdu_control --port 14 --hostname pdu18 --command reboot' %}
{% set power_off_command = '/usr/local/lab-scripts/snmp_pdu_control --port 14 --hostname pdu18 --command off' %}
{% set connection_command = 'telnet localhost 7114' %}
{% set power_on_command = '/usr/local/lab-scripts/snmp_pdu_control --port 14 --hostname pdu18 --command on' %}
{% set uboot_mac_addr = '00:80:e1:12:81:30' %}
{% set exclusive = 'True' %}"""
        self.assertTrue(self.validate_data('staging-b2260-01', data))
        test_template = prepare_jinja_template('staging-b2260-01', data)
        rendered = test_template.render()
        template_dict = yaml.load(rendered)
        ethaddr = False
        for command in template_dict['actions']['boot']['methods']['u-boot']['ramdisk']['commands']:
            if command.startswith('setenv ethaddr'):
                self.assertEqual(command, 'setenv ethaddr 00:80:e1:12:81:30')
                ethaddr = True
        self.assertTrue(ethaddr)
        ethaddr = False
        for command in template_dict['actions']['boot']['methods']['u-boot']['nfs']['commands']:
            if command.startswith('setenv ethaddr'):
                self.assertEqual(command, 'setenv ethaddr 00:80:e1:12:81:30')
                ethaddr = True
        self.assertTrue(ethaddr)

    def test_ip_args(self):
        data = """{% extends 'arndale.jinja2' %}
{% set power_off_command = '/usr/local/lab-scripts/snmp_pdu_control --hostname pdu15 --command off --port 07' %}
{% set hard_reset_command = '/usr/local/lab-scripts/snmp_pdu_control --hostname pdu15 --command reboot --port 07' %}
{% set connection_command = 'telnet serial4 7010' %}
{% set power_on_command = '/usr/local/lab-scripts/snmp_pdu_control --hostname pdu15 --command on --port 07' %}"""
        self.assertTrue(self.validate_data('staging-arndale-01', data))
        test_template = prepare_jinja_template('staging-panda-01', data)
        rendered = test_template.render()
        template_dict = yaml.load(rendered)
        for line in template_dict['actions']['boot']['methods']['u-boot']['ramdisk']['commands']:
            if line.startswith("setenv nfsargs"):
                self.assertIn('ip=:::::eth0:dhcp', line)
                self.assertNotIn('ip=dhcp', line)
            elif line.startswith("setenv bootargs"):
                self.assertIn("drm_kms_helper.edid_firmware=edid-1920x1080.fw", line)

    def test_arduino(self):
        data = """{% extends 'arduino101.jinja2' %}
{% set board_id = 'AE6642EK61804EZ' %}"""
        self.assertTrue(self.validate_data('staging-arduino101-01', data))
        test_template = prepare_jinja_template('staging-arduino101-01',
                                               data)
        rendered = test_template.render()
        template_dict = yaml.load(rendered)
        self.assertIsNotNone(template_dict)
        self.assertEqual(template_dict['board_id'],
                         'AE6642EK61804EZ')
        self.assertEqual(template_dict['usb_vendor_id'],
                         '8087')
        self.assertEqual(template_dict['usb_product_id'],
                         '0aba')

    def test_d03(self):
        data = """{% extends 'd03.jinja2' %}
{% set hard_reset_command = '/usr/bin/pduclient --daemon services --hostname pdu09 --command reboot --port 07' %}
{% set grub_installed_device = '(hd2,gpt1)' %}
{% set power_off_command = '/usr/bin/pduclient --daemon services --hostname pdu09 --command off --port 07' %}
{% set connection_command = 'telnet localhost 7001' %}
{% set power_on_command = '/usr/bin/pduclient --daemon services --hostname pdu09 --command on --port 07' %}
{% set boot_character_delay = 30 %}"""
        self.assertTrue(self.validate_data('staging-d03-01', data))
        test_template = prepare_jinja_template('staging-d03-01',
                                               data)
        rendered = test_template.render()
        template_dict = yaml.load(rendered)
        self.assertIn('character_delays', template_dict)
        self.assertIn('boot', template_dict['character_delays'])
        self.assertNotIn('test', template_dict['character_delays'])
        self.assertEqual(30, template_dict['character_delays']['boot'])

    def test_nexus5x_template(self):
        self.assertTrue(self.validate_data('staging-nexus5x-01', """{% extends 'nexus5x.jinja2' %}
{% set adb_serial_number = '10de1214adae123' %}
{% set fastboot_serial_number = '10de1214adae123' %}
{% set device_info = [{'board_id': '10de1214adae123'}] %}
"""))

    def test_pixel_template(self):
        self.assertTrue(self.validate_data('staging-pixel-01', """{% extends 'pixel.jinja2' %}
{% set adb_serial_number = 'FDAC1231DAD' %}
{% set fastboot_serial_number = 'FDAC1231DAD' %}
{% set device_info = [{'board_id': 'FDAC1231DAD'}] %}
"""))

    def test_nuc_template(self):
        self.assertTrue(self.validate_data('staging-nuc-01', """{% extends 'adb-nuc.jinja2' %}
{% set device_ip = '192.168.1.11' %}
{% set exclusive = 'True' %}
"""))

    def test_ifc6410(self):
        data = """{% extends 'ifc6410.jinja2' %}
{% set adb_serial_number = 'e080c212' %}
{% set fastboot_serial_number = 'e080c212' %}
        """
        self.assertTrue(self.validate_data('staging-ifc6410-01', data))
        test_template = prepare_jinja_template('staging-ifc6410-01',
                                               data)
        rendered = test_template.render()
        template_dict = yaml.load(rendered)
        self.assertEqual('ifc6410', template_dict['device_type'])
        self.assertEqual('e080c212', template_dict['adb_serial_number'])
        self.assertEqual('e080c212', template_dict['fastboot_serial_number'])
        self.assertEqual([], template_dict['fastboot_options'])
        methods = template_dict['actions']['boot']['methods']['fastboot']
        self.assertIn('reboot', methods)
        self.assertIn('boot', methods)
        self.assertIn('auto-login', methods)
        self.assertIn('overlay-unpack', methods)

    def test_juno_vexpress_template(self):
        data = """{% extends 'vexpress.jinja2' %}
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
        test_template = prepare_jinja_template('staging-juno-01', data)
        rendered = test_template.render()
        template_dict = yaml.load(rendered)
        self.assertIsNotNone(template_dict)
        self.assertEqual({'boot': 30}, template_dict['character_delays'])
        self.assertIn('cpu-reset-message', template_dict['constants'])

    def test_db820c_template(self):
        data = """{% extends 'dragonboard-820c.jinja2' %}
{% set adb_serial_number = '3083f595' %}
{% set fastboot_serial_number = '3083f595' %}
"""
        self.assertTrue(self.validate_data('db820c-01', data))
        test_template = prepare_jinja_template('db820c-01', data)
        rendered = test_template.render()
        template_dict = yaml.load(rendered)
        self.assertEqual('dragonboard-820c', template_dict['device_type'])
        self.assertEqual('3083f595', template_dict['adb_serial_number'])
        self.assertEqual('3083f595', template_dict['fastboot_serial_number'])
        self.assertEqual([], template_dict['fastboot_options'])

    def test_docker_template(self):
        data = "{% extends 'docker.jinja2' %}"
        self.assertTrue(self.validate_data('docker-01', data))
        test_template = prepare_jinja_template('docker-01', data)
        rendered = test_template.render()
        template_dict = yaml.load(rendered)
        self.assertEqual('docker', template_dict['device_type'])
        self.assertEqual({'docker': None}, template_dict['actions']['deploy']['methods'])
        self.assertEqual({'docker': {'options': {'cpus': 0.0, 'memory': 0, 'volumes': []}}},
                         template_dict['actions']['boot']['methods'])

        data = """{% extends 'docker.jinja2' %}
{% set docker_cpus=2.1 %}
{% set docker_memory="120M" %}
{% set docker_volumes=["/home", "/tmp"] %}"""
        self.assertTrue(self.validate_data('docker-01', data))
        test_template = prepare_jinja_template('docker-01', data)
        rendered = test_template.render()
        template_dict = yaml.load(rendered)
        self.assertEqual('docker', template_dict['device_type'])
        self.assertEqual({'docker': None}, template_dict['actions']['deploy']['methods'])
        self.assertEqual({'docker': {'options': {'cpus': 2.1, 'memory': "120M",
                                                 'volumes': ["/home", "/tmp"]}}},
                         template_dict['actions']['boot']['methods'])
