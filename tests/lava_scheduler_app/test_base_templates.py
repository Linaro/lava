import os
import unittest

from jinja2 import ChoiceLoader, DictLoader
from jinja2.nodes import Assign as JinjaNodesAssign
from jinja2.nodes import Const as JinjaNodesConst
from jinja2.sandbox import SandboxedEnvironment as JinjaSandboxEnv

from lava_common.yaml import yaml_safe_load
from lava_scheduler_app.schema import SubmissionException, validate_device
from lava_server.files import File


def prepare_jinja_template(hostname, jinja_data, job_ctx=None, raw=True):
    if not job_ctx:
        job_ctx = {}
    string_loader = DictLoader({"%s.jinja2" % hostname: jinja_data})
    type_loader = File("device-type").loader()
    env = JinjaSandboxEnv(
        loader=ChoiceLoader([string_loader, type_loader]),
        trim_blocks=True,
        autoescape=False,
    )
    test_template = env.get_template("%s.jinja2" % hostname)
    if raw:
        return test_template
    rendered = test_template.render(**job_ctx)
    if not rendered:
        return None
    return yaml_safe_load(rendered)


class BaseTemplate:
    class BaseTemplateCases(unittest.TestCase):
        debug = False  # set to True to see the YAML device config output

        def render_device_dictionary_file(self, filename, job_ctx=None, raw=True):
            device = filename.replace(".jinja2", "")
            with open(
                os.path.join(os.path.dirname(__file__), "devices", filename)
            ) as input:
                data = input.read()
            if not job_ctx:
                job_ctx = {}
            self.assertTrue(self.validate_data(device, data))
            test_template = prepare_jinja_template(device, data)
            if not job_ctx:
                job_ctx = {}
            rendered = test_template.render(**job_ctx)
            if raw:
                return rendered
            return yaml_safe_load(rendered)

        def render_device_dictionary(self, hostname, data, job_ctx=None, raw=True):
            if not job_ctx:
                job_ctx = {}
            test_template = prepare_jinja_template(hostname, data)
            rendered = test_template.render(**job_ctx)
            if self.debug:
                print("#######")
                print(rendered)
                print("#######")
            if raw:
                return rendered
            return yaml_safe_load(rendered)

        def validate_data(self, hostname, data, job_ctx=None):
            rendered = self.render_device_dictionary(hostname, data, job_ctx, raw=True)
            try:
                ret = validate_device(yaml_safe_load(rendered))
            except SubmissionException as exc:
                print("#######")
                print(rendered)
                print("#######")
                self.fail(exc)
            return ret


class TestBaseTemplates(BaseTemplate.BaseTemplateCases):
    def test_all_templates(self):
        templates = File("device-type").list("*.jinja2")
        self.assertNotEqual([], templates)

        # keep this out of the loop, as creating the environment is slow.
        env = JinjaSandboxEnv(
            loader=File("device-type").loader(), trim_blocks=True, autoescape=False
        )

        for template in templates:
            data = "{%% extends '%s' %%}" % os.path.basename(template)
            try:
                test_template = env.from_string(data)
                rendered = test_template.render()
                template_dict = yaml_safe_load(rendered)
                validate_device(template_dict)
            except AssertionError as exc:
                self.fail("Template %s failed: %s" % (os.path.basename(template), exc))

    def test_all_template_connections(self):
        templates = File("device-type").list("*.jinja2")
        self.assertNotEqual([], templates)

        # keep this out of the loop, as creating the environment is slow.
        env = JinjaSandboxEnv(
            loader=File("device-type").loader(), trim_blocks=True, autoescape=False
        )

        for template in templates:
            name = os.path.basename(template)
            data = "{%% extends '%s' %%}" % os.path.basename(template)
            data += "{% set connection_command = 'telnet calvin 6080' %}"
            test_template = env.from_string(data)
            rendered = test_template.render()
            template_dict = yaml_safe_load(rendered)
            validate_device(template_dict)
            self.assertIn("connect", template_dict["commands"])
            self.assertNotIn(
                "connections",
                template_dict["commands"],
                msg="%s - failed support for connection_list syntax" % name,
            )
            data = "{%% extends '%s' %%}" % os.path.basename(template)
            data += "{% set connection_list = ['uart0'] %}"
            data += "{% set connection_commands = {'uart1': 'telnet calvin 6080'} %}"
            data += "{% set connection_tags = {'uart1': ['primary']} %}"
            test_template = env.from_string(data)
            rendered = test_template.render()
            template_dict = yaml_safe_load(rendered)
            validate_device(template_dict)
            self.assertNotIn("connect", template_dict["commands"])
            self.assertIn(
                "connections",
                template_dict["commands"],
                msg="%s - missing connection_list syntax" % name,
            )

    def test_rendering(self):
        with open(
            os.path.join(os.path.dirname(__file__), "devices", "db410c.jinja2")
        ) as hikey:
            data = hikey.read()
        env = JinjaSandboxEnv(autoescape=False)
        ast = env.parse(data)
        device_dict = {}
        count = 0
        for node in ast.find_all(JinjaNodesAssign):
            count += 1
            if isinstance(node.node, JinjaNodesConst):
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
        template_dict = prepare_jinja_template("nexus4-01", data, raw=False)
        self.assertEqual(
            "adb -s R42D300FRYP shell", template_dict["commands"]["connect"]
        )
        self.assertIn("lxc", template_dict["actions"]["boot"]["methods"])
        self.assertIn("fastboot", template_dict["actions"]["boot"]["methods"])
        self.assertIn("lxc", template_dict["actions"]["deploy"]["methods"])
        self.assertIn("fastboot", template_dict["actions"]["deploy"]["methods"])
        self.assertEqual(
            ["reboot"], template_dict["actions"]["boot"]["methods"]["fastboot"]
        )

    def test_console_baud(self):
        data = """{% extends 'beaglebone-black.jinja2' %}"""
        template_dict = prepare_jinja_template("bbb-01", data, raw=False)
        self.assertIn("u-boot", template_dict["actions"]["boot"]["methods"])
        self.assertIn("nfs", template_dict["actions"]["boot"]["methods"]["u-boot"])
        commands = template_dict["actions"]["boot"]["methods"]["u-boot"]["nfs"][
            "commands"
        ]
        for command in commands:
            if not command.startswith("setenv nfsargs"):
                continue
            self.assertIn("console=ttyO0,115200n8", command)
        data = """{% extends 'base-uboot.jinja2' %}"""
        template_dict = prepare_jinja_template("base-01", data, raw=False)
        self.assertIn("u-boot", template_dict["actions"]["boot"]["methods"])
        self.assertIn("nfs", template_dict["actions"]["boot"]["methods"]["u-boot"])
        commands = template_dict["actions"]["boot"]["methods"]["u-boot"]["nfs"][
            "commands"
        ]
        for command in commands:
            if not command.startswith("setenv nfsargs"):
                continue
            self.assertNotIn("console=ttyO0,115200n8", command)
            self.assertNotIn("console=", command)
            self.assertNotIn("console=ttyO0", command)
            self.assertNotIn("115200n8", command)
            self.assertNotIn("n8", command)

    def test_primary_connection_power_commands_fail(self):
        data = """{% extends 'x86.jinja2' %}
{% set power_off_command = '/usr/bin/pduclient --command off' %}
{% set power_on_command = '/usr/bin/pduclient --command on' %}
{% set hard_reset_command = '/usr/bin/pduclient --command reset' %}
{% set connection_command = 'telnet localhost 7302' %}
{% set ssh_host = 'localhost' %}"""
        device_dict = self.render_device_dictionary("staging-x86-01", data)
        self.assertRaises(
            SubmissionException, validate_device, yaml_safe_load(device_dict)
        )

    def test_primary_connection_power_commands_empty_ssh_host(self):
        data = """{% extends 'x86.jinja2' %}
{% set power_off_command = '/usr/bin/pduclient --command off' %}
{% set power_on_command = '/usr/bin/pduclient --command on' %}
{% set hard_reset_command = '/usr/bin/pduclient --command reset' %}
{% set connection_command = 'telnet localhost 7302' %}
{% set ssh_host = '' %}"""
        device_dict = self.render_device_dictionary("staging-x86-01", data)
        self.assertTrue(validate_device(yaml_safe_load(device_dict)))

    def test_primary_connection_power_commands(self):
        data = """{% extends 'x86.jinja2' %}
{% set power_off_command = '/usr/bin/pduclient --command off' %}
{% set hard_reset_command = '/usr/bin/pduclient --command reset' %}
{% set power_on_command = '/usr/bin/pduclient --command on' %}
{% set connection_command = 'telnet localhost 7302' %}"""
        device_dict = self.render_device_dictionary("staging-x86-01", data)
        self.assertTrue(validate_device(yaml_safe_load(device_dict)))

    def test_pexpect_spawn_window(self):
        template_dict = self.render_device_dictionary_file(
            "hi6220-hikey-01.jinja2", raw=False
        )
        self.assertIsNotNone(template_dict["constants"])
        self.assertIn("spawn_maxread", template_dict["constants"])
        self.assertIsInstance(template_dict["constants"]["spawn_maxread"], str)
        self.assertEqual(int(template_dict["constants"]["spawn_maxread"]), 4092)

    def test_test_shell_constants(self):
        job_ctx = {}
        template_dict = self.render_device_dictionary_file(
            "hi6220-hikey-01.jinja2", job_ctx=job_ctx, raw=False
        )
        self.assertIsNotNone(template_dict["constants"])
        self.assertIn("posix", template_dict["constants"])
        self.assertEqual(
            "/lava-%s", template_dict["constants"]["posix"]["lava_test_results_dir"]
        )
        job_ctx = {"lava_test_results_dir": "/sysroot/lava-%s"}
        template_dict = self.render_device_dictionary_file(
            "hi6220-hikey-01.jinja2", job_ctx=job_ctx, raw=False
        )
        self.assertIsNotNone(template_dict["constants"])
        self.assertIn("posix", template_dict["constants"])
        self.assertEqual(
            "/sysroot/lava-%s",
            template_dict["constants"]["posix"]["lava_test_results_dir"],
        )
