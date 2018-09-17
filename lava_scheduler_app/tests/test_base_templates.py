import os
import glob
import yaml
import jinja2
import unittest
# pylint: disable=superfluous-parens,ungrouped-imports
from lava_scheduler_app.schema import (
    validate_device,
    SubmissionException,
)

# pylint: disable=too-many-branches,too-many-public-methods,too-few-public-methods
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


class BaseTemplate(object):

    class BaseTemplateCases(unittest.TestCase):

        debug = False  # set to True to see the YAML device config output
        system = False  # set to True to debug the system templates

        def render_device_dictionary_file(self, filename, job_ctx=None):
            device = filename.replace('.jinja2', '')
            with open(os.path.join(os.path.dirname(__file__), 'devices', filename)) as input:
                data = input.read()
            if not job_ctx:
                job_ctx = {}
            self.assertTrue(self.validate_data(device, data))
            test_template = prepare_jinja_template(device, data)
            if not job_ctx:
                job_ctx = {}
            return test_template.render(**job_ctx)

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
                ret = validate_device(yaml.load(rendered, Loader=yaml.CLoader))
            except SubmissionException as exc:
                print('#######')
                print(rendered)
                print('#######')
                self.fail(exc)
            return ret


class TestBaseTemplates(BaseTemplate.BaseTemplateCases):

    def test_all_templates(self):
        path = os.path.dirname(CONFIG_PATH)
        templates = glob.glob(os.path.join(path, 'device-types', '*.jinja2'))
        self.assertNotEqual([], templates)

        # keep this out of the loop, as creating the environment is slow.
        path = os.path.dirname(CONFIG_PATH)
        fs_loader = jinja2.FileSystemLoader([os.path.join(path, 'device-types')])
        env = jinja2.Environment(loader=fs_loader, trim_blocks=True)

        for template in templates:
            data = "{%% extends '%s' %%}" % os.path.basename(template)
            try:
                test_template = env.from_string(data)
                rendered = test_template.render()
                template_dict = yaml.load(rendered, Loader=yaml.CLoader)
                validate_device(template_dict)
            except AssertionError as exc:
                self.fail("Template %s failed: %s" % (os.path.basename(template), exc))

    def test_all_template_connections(self):
        path = os.path.dirname(CONFIG_PATH)
        templates = glob.glob(os.path.join(path, 'device-types', '*.jinja2'))
        self.assertNotEqual([], templates)

        # keep this out of the loop, as creating the environment is slow.
        path = os.path.dirname(CONFIG_PATH)
        fs_loader = jinja2.FileSystemLoader([os.path.join(path, 'device-types')])
        env = jinja2.Environment(loader=fs_loader, trim_blocks=True)

        for template in templates:
            name = os.path.basename(template)
            data = "{%% extends '%s' %%}" % os.path.basename(template)
            data += "{% set connection_command = 'telnet calvin 6080' %}"
            test_template = env.from_string(data)
            rendered = test_template.render()
            template_dict = yaml.load(rendered, Loader=yaml.CLoader)
            validate_device(template_dict)
            self.assertIn('connect', template_dict['commands'])
            self.assertNotIn(
                'connections',
                template_dict['commands'], msg="%s - failed support for connection_list syntax" % name)
            data = "{%% extends '%s' %%}" % os.path.basename(template)
            data += "{% set connection_list = ['uart0'] %}"
            data += "{% set connection_commands = {'uart1': 'telnet calvin 6080'} %}"
            data += "{% set connection_tags = {'uart1': ['primary']} %}"
            test_template = env.from_string(data)
            rendered = test_template.render()
            template_dict = yaml.load(rendered, Loader=yaml.CLoader)
            validate_device(template_dict)
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

    def test_console_baud(self):
        data = """{% extends 'beaglebone-black.jinja2' %}"""
        test_template = prepare_jinja_template('bbb-01', data)
        rendered = test_template.render()
        template_dict = yaml.load(rendered)
        self.assertIn('u-boot', template_dict['actions']['boot']['methods'])
        self.assertIn('nfs', template_dict['actions']['boot']['methods']['u-boot'])
        commands = template_dict['actions']['boot']['methods']['u-boot']['nfs']['commands']
        for command in commands:
            if not command.startswith('setenv nfsargs'):
                continue
            self.assertIn('console=ttyO0,115200n8', command)
        data = """{% extends 'base-uboot.jinja2' %}"""
        test_template = prepare_jinja_template('base-01', data)
        rendered = test_template.render()
        template_dict = yaml.load(rendered)
        self.assertIn('u-boot', template_dict['actions']['boot']['methods'])
        self.assertIn('nfs', template_dict['actions']['boot']['methods']['u-boot'])
        commands = template_dict['actions']['boot']['methods']['u-boot']['nfs']['commands']
        for command in commands:
            if not command.startswith('setenv nfsargs'):
                continue
            self.assertNotIn('console=ttyO0,115200n8', command)
            self.assertNotIn('console=', command)
            self.assertNotIn('console=ttyO0', command)
            self.assertNotIn('115200n8', command)
            self.assertNotIn('n8', command)

    def test_primary_connection_power_commands_fail(self):  # pylint: disable=invalid-name
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

    def test_primary_connection_power_commands_empty_ssh_host(self):  # pylint: disable=invalid-name
        data = """{% extends 'x86.jinja2' %}
{% set power_off_command = '/usr/bin/pduclient --command off' %}
{% set power_on_command = '/usr/bin/pduclient --command on' %}
{% set hard_reset_command = '/usr/bin/pduclient --command reset' %}
{% set connection_command = 'telnet localhost 7302' %}
{% set ssh_host = '' %}"""
        device_dict = self.render_device_dictionary('staging-x86-01', data)
        self.assertTrue(validate_device(yaml.load(device_dict)))

    def test_primary_connection_power_commands(self):  # pylint: disable=invalid-name
        data = """{% extends 'x86.jinja2' %}
{% set power_off_command = '/usr/bin/pduclient --command off' %}
{% set hard_reset_command = '/usr/bin/pduclient --command reset' %}
{% set power_on_command = '/usr/bin/pduclient --command on' %}
{% set connection_command = 'telnet localhost 7302' %}"""
        device_dict = self.render_device_dictionary('staging-x86-01', data)
        self.assertTrue(validate_device(yaml.load(device_dict)))

    def test_pexpect_spawn_window(self):
        rendered = self.render_device_dictionary_file('hi6220-hikey-01.jinja2')
        template_dict = yaml.load(rendered)
        self.assertIsNotNone(template_dict['constants'])
        self.assertIn('spawn_maxread', template_dict['constants'])
        self.assertIsInstance(template_dict['constants']['spawn_maxread'], str)
        self.assertEqual(int(template_dict['constants']['spawn_maxread']), 4092)

    def test_test_shell_constants(self):
        job_ctx = {}
        rendered = self.render_device_dictionary_file('hi6220-hikey-01.jinja2', job_ctx=job_ctx)
        template_dict = yaml.load(rendered)
        self.assertIsNotNone(template_dict['constants'])
        self.assertIn('posix', template_dict['constants'])
        self.assertEqual(
            '/lava-%s',
            template_dict['constants']['posix']['lava_test_results_dir']
        )
        job_ctx = {
            'lava_test_results_dir': '/sysroot/lava-%s',
        }
        rendered = self.render_device_dictionary_file('hi6220-hikey-01.jinja2', job_ctx=job_ctx)
        template_dict = yaml.load(rendered)
        self.assertIsNotNone(template_dict['constants'])
        self.assertIn('posix', template_dict['constants'])
        self.assertEqual(
            '/sysroot/lava-%s',
            template_dict['constants']['posix']['lava_test_results_dir']
        )
