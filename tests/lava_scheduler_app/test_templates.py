from tests.lava_scheduler_app.test_base_templates import (
    BaseTemplate,
    prepare_jinja_template,
)


class TestTemplates(BaseTemplate.BaseTemplateCases):
    """
    Test rendering of jinja2 templates

    When adding or modifying a jinja2 template, add or update the test here.
    Use realistic data - complete exports of the device dictionary preferably.
    Set debug to True to see the content of the rendered templates
    """

    def test_x86_template(self):
        data = """{% extends 'x86.jinja2' %}
{% set power_off_command = '/usr/bin/pduclient --daemon localhost --port 02 --hostname lngpdu01 --command off' %}
{% set hard_reset_command = '/usr/bin/pduclient --daemon localhost --port 02 --hostname lngpdu01 --command reboot' %}
{% set power_on_command = '/usr/bin/pduclient --daemon localhost --port 02 --hostname lngpdu01 --command on' %}
{% set connection_command = 'telnet localhost 7302' %}"""
        self.assertTrue(self.validate_data("staging-x86-01", data))
        template_dict = prepare_jinja_template("staging-x86-01", data, raw=False)
        for _, value in template_dict["actions"]["boot"]["methods"]["ipxe"].items():
            if "commands" in value:
                for item in value["commands"]:
                    self.assertFalse(item.endswith(","))
        depth = 0
        # check configured commands blocks for trailing commas inherited from JSON V1 configuration.
        # reduce does not help as the top level dictionary also contains lists, integers and strings
        for _, action_value in template_dict["actions"].items():
            if "methods" in action_value:
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
                                    if "commands" in command_value:
                                        depth = 7 if depth < 7 else depth
                                        for item in command_value["commands"]:
                                            depth = 8 if depth < 8 else depth
                                            if item.endswith(","):
                                                self.fail("%s ends with a comma" % item)
        self.assertEqual(depth, 8)
        job_ctx = {}
        template_dict = prepare_jinja_template(
            "staging-x86-01", data, job_ctx=job_ctx, raw=False
        )

        self.assertIsNotNone(
            template_dict["actions"]["boot"]["methods"]["ipxe"]["nfs"]["commands"]
        )

        self.assertIsNotNone(
            template_dict["timeouts"]["connections"]["bootloader-commands"]
        )
        self.assertEqual(
            template_dict["timeouts"]["connections"]["bootloader-commands"]["minutes"],
            5,
        )

        # uses default value from template
        self.assertEqual(500, template_dict["character_delays"]["boot"])

        # override template in job context
        job_ctx = {"boot_character_delay": 150}
        template_dict = prepare_jinja_template(
            "staging-x86-01", data, job_ctx=job_ctx, raw=False
        )
        self.assertEqual(150, template_dict["character_delays"]["boot"])

        # add device dictionary override
        # overrides the template default
        data += """{% set boot_character_delay = 400 %}"""
        job_ctx = {}
        template_dict = prepare_jinja_template(
            "staging-x86-01", data, job_ctx=job_ctx, raw=False
        )
        self.assertEqual(400, template_dict["character_delays"]["boot"])

        # job context does not override device dictionary
        job_ctx = {"boot_character_delay": 150}
        template_dict = prepare_jinja_template(
            "staging-x86-01", data, job_ctx=job_ctx, raw=False
        )
        self.assertNotEqual(150, template_dict["character_delays"]["boot"])
        self.assertEqual(400, template_dict["character_delays"]["boot"])

    def test_x86_interface_template(self):
        # test boot interface override
        data = """{% extends 'x86.jinja2' %}
{% set power_off_command = '/usr/bin/pduclient --daemon localhost --port 02 --hostname lngpdu01 --command off' %}
{% set hard_reset_command = '/usr/bin/pduclient --daemon localhost --port 02 --hostname lngpdu01 --command reboot' %}
{% set power_on_command = '/usr/bin/pduclient --daemon localhost --port 02 --hostname lngpdu01 --command on' %}
{% set connection_command = 'telnet localhost 7302' %}"""
        self.assertTrue(self.validate_data("staging-x86-01", data))
        template_dict = prepare_jinja_template("staging-x86-01", data, raw=False)
        for _, value in template_dict["actions"]["boot"]["methods"]["ipxe"].items():
            if "commands" in value:
                self.assertIn("dhcp net0", value["commands"])
                self.assertNotIn("dhcp net1", value["commands"])
        # test boot interface override
        data = """{% extends 'x86.jinja2' %}
{% set boot_interface = 'net1' %}
{% set power_off_command = '/usr/bin/pduclient --daemon localhost --port 02 --hostname lngpdu01 --command off' %}
{% set hard_reset_command = '/usr/bin/pduclient --daemon localhost --port 02 --hostname lngpdu01 --command reboot' %}
{% set power_on_command = '/usr/bin/pduclient --daemon localhost --port 02 --hostname lngpdu01 --command on' %}
{% set connection_command = 'telnet localhost 7302' %}"""
        self.assertTrue(self.validate_data("staging-x86-01", data))
        template_dict = prepare_jinja_template("staging-x86-01", data, raw=False)
        for _, value in template_dict["actions"]["boot"]["methods"]["ipxe"].items():
            if "commands" in value:
                self.assertIn("dhcp net1", value["commands"])
                self.assertNotIn("dhcp net0", value["commands"])

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
{% set connection_command = 'telnet localhost 7333' %}"""
        self.assertTrue(self.validate_data("staging-thunderx-01", data))
        template_dict = prepare_jinja_template("staging-thunderx-01", data, raw=False)
        self.assertIn("character_delays", template_dict)
        self.assertIn("boot", template_dict["character_delays"])
        self.assertEqual(150, template_dict["character_delays"]["boot"])
        self.assertIn("interfaces", template_dict["parameters"])
        self.assertIn("iface2", template_dict["parameters"]["interfaces"])
        self.assertIn("iface1", template_dict["parameters"]["interfaces"])
        self.assertIn("iface0", template_dict["parameters"]["interfaces"])
        self.assertIn("sysfs", template_dict["parameters"]["interfaces"]["iface2"])

    def test_highbank_template(self):
        data = """{% extends 'highbank.jinja2' %}
{% set connection_command = 'ipmitool -I lanplus -U admin -P admin -H calxeda02-07-02 sol activate' %}
{% set power_off_command = 'ipmitool -H calxeda02-07-02 -U admin -P admin chassis power off' %}
{% set power_on_command = 'ipmitool -H calxeda02-07-02 -U admin -P admin chassis power on' %}
{% set hard_reset_command = 'ipmitool -H calxeda02-07-02 -U admin -P admin chassis power off; sleep 20; ipmitool -H calxeda02-07-02 -U admin -P admin chassis power on' %}"""
        self.assertTrue(self.validate_data("highbank-07", data))
        template_dict = prepare_jinja_template("highbank-07", data, raw=False)
        self.assertIsNotNone(template_dict)
        self.assertEqual(template_dict["character_delays"]["boot"], 100)
        self.assertEqual(
            template_dict["actions"]["boot"]["methods"]["u-boot"]["parameters"][
                "bootloader_prompt"
            ],
            "Highbank",
        )
        self.assertEqual(
            template_dict["actions"]["boot"]["methods"]["u-boot"]["parameters"][
                "interrupt_char"
            ],
            "s",
        )

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
        self.assertTrue(self.validate_data("staging-x86-01", data))
        template_dict = prepare_jinja_template("staging-qemu-01", data, raw=False)
        self.assertIn(
            "set console console=ttyS0,115200n8 lava_mac={LAVA_MAC}",
            template_dict["actions"]["boot"]["methods"]["ipxe"]["nfs"]["commands"],
        )
        context = {"extra_kernel_args": "intel_mmio=on mmio=on"}
        template_dict = prepare_jinja_template(
            "staging-qemu-01", data, job_ctx=context, raw=False
        )
        self.assertIn(
            "set extraargs root=/dev/nfs rw nfsroot={NFS_SERVER_IP}:{NFSROOTFS},tcp,hard intel_mmio=on mmio=on ip=dhcp",
            template_dict["actions"]["boot"]["methods"]["ipxe"]["nfs"]["commands"],
        )

    def test_arduino(self):
        data = """{% extends 'arduino101.jinja2' %}
{% set board_id = 'AE6642EK61804EZ' %}"""
        self.assertTrue(self.validate_data("staging-arduino101-01", data))
        template_dict = prepare_jinja_template("staging-arduino101-01", data, raw=False)
        self.assertIsNotNone(template_dict)
        self.assertEqual(template_dict["board_id"], "AE6642EK61804EZ")
        self.assertEqual(template_dict["usb_vendor_id"], "8087")
        self.assertEqual(template_dict["usb_product_id"], "0aba")

    def test_depthcharge_template(self):
        data = """\
{% extends 'base-depthcharge.jinja2' %}
{% set mkimage_fit_arch = 'arm' %}
{% set fit_kernel_load_address = '0x5678' %}
{% set start_message = 'Starting netboot on veyron_jaq...' %}
{% set console_device = console_device | default('ttyS2') %}
{% set extra_kernel_args = 'earlyprintk=ttyS2,115200n8 console=tty1' %}"""
        self.assertTrue(self.validate_data("jaq-01", data))
        template_dict = prepare_jinja_template("jaq-01", data, raw=False)
        load_addr = template_dict["parameters"]["load_address"]
        self.assertEqual(load_addr, "0x5678")
        depthcharge = template_dict["actions"]["boot"]["methods"]["depthcharge"]
        self.assertEqual(
            "Starting netboot on veyron_jaq...",
            depthcharge["parameters"]["start_message"],
        )
        self.assertEqual(
            "earlyprintk=ttyS2,115200n8 console=tty1 console=ttyS2,115200n8 root=/dev/ram0 ip=dhcp",
            depthcharge["ramdisk"]["cmdline"],
        )

    def test_x86_atom330_template(self):
        template_dict = self.render_device_dictionary_file(
            "x86-atom330-01.jinja2", raw=False
        )
        self.assertIsNotNone(template_dict["actions"]["boot"]["methods"]["ipxe"])
        self.assertIn("ramdisk", template_dict["actions"]["boot"]["methods"]["ipxe"])
        self.assertIn(
            "commands", template_dict["actions"]["boot"]["methods"]["ipxe"]["nfs"]
        )
