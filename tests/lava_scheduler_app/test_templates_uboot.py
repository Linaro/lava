# Copyright (C) 2019 Linaro Limited
#
# Author: Antonio Terceiro <antonio.terceiro@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import os
import tempfile
import unittest

from lava_common.yaml import yaml_safe_dump
from lava_dispatcher.action import Timeout
from lava_dispatcher.device import NewDevice
from lava_dispatcher.parser import JobParser
from tests.utils import DummyLogger, infrastructure_error

from .test_templates import BaseTemplateTest


class TestUbootTemplates(BaseTemplateTest):
    """
    Test rendering of jinja2 templates

    When adding or modifying a jinja2 template, add or update the test here.
    Use realistic data - complete exports of the device dictionary preferably.
    Set debug to True to see the content of the rendered templates
    """

    def test_armada375_template(self):
        """
        Test the armada-375 template as if it was a device dictionary
        """
        data = """
{% extends 'base-uboot.jinja2' %}
{% set console_device = console_device|default('ttyS0') %}
{% set baud_rate = baud_rate|default(115200) %}
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
        template_dict = self.render_device_dictionary_from_text(data)
        params = template_dict["actions"]["deploy"]["parameters"]
        self.assertIsNotNone(params)
        self.assertIn("use_xip", params)
        self.assertIn("append_dtb", params)
        self.assertTrue(params["use_xip"])
        self.assertTrue(params["append_dtb"])
        params = template_dict["actions"]["boot"]["methods"]["u-boot"]["ramdisk"][
            "commands"
        ]
        for line in params:
            if "run loadkernel" in line:
                self.assertIn("bootm", line)

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
{% set connection_command = 'telnet localhost 7333' %}"""
        template_dict = self.render_device_dictionary_from_text(data)
        self.assertIsNotNone(
            template_dict["actions"]["deploy"]["methods"]["ssh"]["host"]
        )
        self.assertEqual(
            "", template_dict["actions"]["deploy"]["methods"]["ssh"]["host"]
        )
        self.assertNotEqual(
            "None", template_dict["actions"]["deploy"]["methods"]["ssh"]["host"]
        )
        data += "{% set ssh_host = '192.168.0.10' %}"
        template_dict = self.render_device_dictionary_from_text(data, validate=False)
        self.assertIsNotNone(
            template_dict["actions"]["deploy"]["methods"]["ssh"]["host"]
        )
        self.assertEqual(
            "192.168.0.10", template_dict["actions"]["deploy"]["methods"]["ssh"]["host"]
        )

    def test_b2260_template(self):
        data = """{% extends 'b2260.jinja2' %}"""
        template_dict = self.render_device_dictionary_from_text(data)
        self.assertEqual(
            {"seconds": 15}, template_dict["timeouts"]["actions"]["power-off"]
        )

    def test_mustang_template(self):
        data = """{% extends 'mustang.jinja2' %}
{% set connection_command = 'telnet serial4 7012' %}
{% set hard_reset_command = '/usr/bin/pduclient --daemon staging-master --hostname pdu15 --command reboot --port 05' %}
{% set power_off_command = '/usr/bin/pduclient --daemon staging-master --hostname pdu15 --command off --port 05' %}
{% set power_on_command = '/usr/bin/pduclient --daemon staging-master --hostname pdu15 --command on --port 05' %}"""
        template_dict = self.render_device_dictionary_from_text(data)
        self.assertIsInstance(template_dict["parameters"]["text_offset"], str)
        commands = template_dict["actions"]["boot"]["methods"]["u-boot"]["ramdisk"][
            "commands"
        ]
        for line in commands:
            if "setenv initrd_high" in line:
                self.fail("Mustang should not have initrd_high set")
            if "setenv fdt_high" in line:
                self.fail("Mustang should not have fdt_high set")

    def test_avenger96_template(self):
        data = """{% extends 'avenger96.jinja2' %}
{% set connection_command = 'telnet serial4 7012' %}
{% set hard_reset_command = '/usr/bin/pduclient --daemon staging-master --hostname pdu15 --command reboot --port 05' %}
{% set power_off_command = '/usr/bin/pduclient --daemon staging-master --hostname pdu15 --command off --port 05' %}
{% set power_on_command = '/usr/bin/pduclient --daemon staging-master --hostname pdu15 --command on --port 05' %}"""
        template_dict = self.render_device_dictionary_from_text(data)
        commands = template_dict["actions"]["boot"]["methods"]["u-boot"]["ramdisk"][
            "commands"
        ]
        for line in commands:
            if "setenv ethaddr" in line:
                self.fail(
                    "Avenger96 should not have 'setenv ethaddr' as MAC address is pre-configured already."
                )

    def test_rpi3_32_template(self):
        checked = False
        data = """{% extends 'bcm2837-rpi-3-b-32.jinja2' %}"""

        # test appending to kernel args
        context = {"extra_kernel_args": "extra_arg=extra_val"}
        template_dict = self.render_device_dictionary_from_text(data, context)
        commands = template_dict["actions"]["boot"]["methods"]["u-boot"]["ramdisk"][
            "commands"
        ]
        self.assertIsNotNone(commands)
        self.assertIsInstance(commands, list)
        for line in commands:
            if "setenv bootargs" in line:
                self.assertIn("earlycon=", line)
                self.assertIn("extra_arg=extra_val", line)
                checked = True
        self.assertTrue(checked)

        # test overwriting kernel args
        checked = False
        context = {"custom_kernel_args": "custom_arg=custom_val"}
        template_dict = self.render_device_dictionary_from_text(data, context)
        commands = template_dict["actions"]["boot"]["methods"]["u-boot"]["ramdisk"][
            "commands"
        ]
        self.assertIsNotNone(commands)
        self.assertIsInstance(commands, list)
        for line in commands:
            if "setenv bootargs" in line:
                self.assertNotIn("earlycon=", line)
                self.assertIn("custom_arg=custom_val", line)
                checked = True
        self.assertTrue(checked)

    def test_panda_template(self):
        data = """{% extends 'panda.jinja2' %}
{% set connection_command = 'telnet serial4 7012' %}
{% set hard_reset_command = '/usr/bin/pduclient --daemon staging-master --hostname pdu15 --command reboot --port 05' %}
{% set power_off_command = '/usr/bin/pduclient --daemon staging-master --hostname pdu15 --command off --port 05' %}
{% set power_on_command = '/usr/bin/pduclient --daemon staging-master --hostname pdu15 --command on --port 05' %}"""
        context = {"extra_kernel_args": "intel_mmio=on mmio=on"}
        template_dict = self.render_device_dictionary_from_text(data, context)
        self.assertIn("bootloader-commands", template_dict["timeouts"]["actions"])
        self.assertEqual(
            180.0,
            Timeout.parse(template_dict["timeouts"]["actions"]["bootloader-commands"]),
        )
        commands = template_dict["actions"]["boot"]["methods"]["u-boot"]["ramdisk"][
            "commands"
        ]
        checked = False
        self.assertIsNotNone(commands)
        self.assertIsInstance(commands, list)
        self.assertIn("usb start", commands)
        for line in commands:
            if "setenv bootargs" in line:
                self.assertIn("console=ttyO2", line)
                self.assertIn(" " + context["extra_kernel_args"] + " ", line)
                checked = True
        self.assertTrue(checked)
        checked = False
        for line in commands:
            if "setenv initrd_high" in line:
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
{% set usb_device_id = 0 %}"""
        template_dict = self.render_device_dictionary_from_text(data)
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
        template_dict = self.render_device_dictionary_from_text(data)
        self.assertIsNotNone(template_dict)
        self.assertIn("u-boot", template_dict["actions"]["boot"]["methods"])
        self.assertIn("SanDisk_Ultra", template_dict["parameters"]["media"]["usb"])
        self.assertEqual(
            template_dict["parameters"]["media"]["usb"]["SanDisk_Ultra"]["device_id"],
            "0",
        )
        self.assertEqual(
            template_dict["parameters"]["media"]["usb"]["SanDisk_Ultra"]["uuid"],
            "usb-SanDisk_Ultra_20060775320F43006019-0:0",
        )
        self.assertIn("ST160LM003", template_dict["parameters"]["media"]["sata"])
        self.assertIn(
            "uboot_interface",
            template_dict["parameters"]["media"]["sata"]["ST160LM003"],
        )
        self.assertEqual(
            "scsi",
            template_dict["parameters"]["media"]["sata"]["ST160LM003"][
                "uboot_interface"
            ],
        )
        self.assertIn(
            "uuid", template_dict["parameters"]["media"]["sata"]["ST160LM003"]
        )
        self.assertIn(
            "ata-ST160LM003_HN-M160MBB_S2SYJ9KC102184",
            template_dict["parameters"]["media"]["sata"]["ST160LM003"]["uuid"],
        )
        self.assertIn("ssh", template_dict["actions"]["boot"]["methods"])

    def test_extra_nfs_opts(self):
        data = """{% extends 'panda.jinja2' %}
{% set connection_command = 'telnet serial4 7012' %}
{% set hard_reset_command = '/usr/bin/pduclient --daemon staging-master --hostname pdu15 --command reboot --port 05' %}
{% set power_off_command = '/usr/bin/pduclient --daemon staging-master --hostname pdu15 --command off --port 05' %}
{% set power_on_command = '/usr/bin/pduclient --daemon staging-master --hostname pdu15 --command on --port 05' %}"""
        job_ctx = {}
        template_dict = self.render_device_dictionary_from_text(data, job_ctx)
        for line in template_dict["actions"]["boot"]["methods"]["u-boot"]["nfs"][
            "commands"
        ]:
            if line.startswith("setenv nfsargs"):
                self.assertIn(",tcp,hard ", line)
                self.assertNotIn("nfsvers", line)
        job_ctx = {"extra_nfsroot_args": ",nolock,nfsvers=3"}
        template_dict = self.render_device_dictionary_from_text(data, job_ctx)
        for line in template_dict["actions"]["boot"]["methods"]["u-boot"]["nfs"][
            "commands"
        ]:
            if line.startswith("setenv nfsargs"):
                self.assertIn(",tcp,hard,nolock,nfsvers=3 ", line)
        commands = template_dict["actions"]["boot"]["methods"]["u-boot"]["ramdisk"][
            "commands"
        ]
        checked = False
        for line in commands:
            if "setenv initrd_high" in line:
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
{% set connection_command = 'telnet localhost 7333' %}"""
        template_dict = self.render_device_dictionary_from_text(data)
        self.assertIn("interfaces", template_dict["parameters"])
        self.assertIn("iface0", template_dict["parameters"]["interfaces"])
        self.assertIn("port", template_dict["parameters"]["interfaces"]["iface0"])
        self.assertIn("target", template_dict["parameters"]["interfaces"])
        self.assertIn("ip", template_dict["parameters"]["interfaces"]["target"])
        self.assertIsNone(template_dict["parameters"]["interfaces"]["target"]["ip"])
        self.assertIsNotNone(template_dict["parameters"]["interfaces"]["target"]["mac"])

    def test_ethaddr(self):
        data = """{% extends 'b2260.jinja2' %}
{% set hard_reset_command = '/usr/local/lab-scripts/snmp_pdu_control --port 14 --hostname pdu18 --command reboot' %}
{% set power_off_command = '/usr/local/lab-scripts/snmp_pdu_control --port 14 --hostname pdu18 --command off' %}
{% set connection_command = 'telnet localhost 7114' %}
{% set power_on_command = '/usr/local/lab-scripts/snmp_pdu_control --port 14 --hostname pdu18 --command on' %}
{% set uboot_mac_addr = '00:80:e1:12:81:30' %}"""
        template_dict = self.render_device_dictionary_from_text(data)
        ethaddr = False
        for command in template_dict["actions"]["boot"]["methods"]["u-boot"]["ramdisk"][
            "commands"
        ]:
            if command.startswith("setenv ethaddr"):
                self.assertEqual(command, "setenv ethaddr 00:80:e1:12:81:30")
                ethaddr = True
        self.assertTrue(ethaddr)
        ethaddr = False
        for command in template_dict["actions"]["boot"]["methods"]["u-boot"]["nfs"][
            "commands"
        ]:
            if command.startswith("setenv ethaddr"):
                self.assertEqual(command, "setenv ethaddr 00:80:e1:12:81:30")
                ethaddr = True
        self.assertTrue(ethaddr)

    def test_ip_args(self):
        data = """{% extends 'arndale.jinja2' %}
{% set power_off_command = '/usr/local/lab-scripts/snmp_pdu_control --hostname pdu15 --command off --port 07' %}
{% set hard_reset_command = '/usr/local/lab-scripts/snmp_pdu_control --hostname pdu15 --command reboot --port 07' %}
{% set connection_command = 'telnet serial4 7010' %}
{% set power_on_command = '/usr/local/lab-scripts/snmp_pdu_control --hostname pdu15 --command on --port 07' %}"""
        template_dict = self.render_device_dictionary_from_text(data)
        for line in template_dict["actions"]["boot"]["methods"]["u-boot"]["ramdisk"][
            "commands"
        ]:
            if line.startswith("setenv nfsargs"):
                self.assertIn("ip=:::::eth0:dhcp", line)
                self.assertNotIn("ip=dhcp", line)
            elif line.startswith("setenv bootargs"):
                self.assertIn("drm_kms_helper.edid_firmware=edid-1920x1080.fw", line)

    def test_d03(self):
        data = """{% extends 'd03.jinja2' %}
{% set hard_reset_command = '/usr/bin/pduclient --daemon services --hostname pdu09 --command reboot --port 07' %}
{% set grub_installed_device = '(hd2,gpt1)' %}
{% set power_off_command = '/usr/bin/pduclient --daemon services --hostname pdu09 --command off --port 07' %}
{% set connection_command = 'telnet localhost 7001' %}
{% set power_on_command = '/usr/bin/pduclient --daemon services --hostname pdu09 --command on --port 07' %}
{% set boot_character_delay = 30 %}"""
        template_dict = self.render_device_dictionary_from_text(data)
        self.assertIn("character_delays", template_dict)
        self.assertIn("boot", template_dict["character_delays"])
        self.assertNotIn("test", template_dict["character_delays"])
        self.assertEqual(30, template_dict["character_delays"]["boot"])

    def test_juno_vexpress_template(self):
        data = """{% extends 'juno.jinja2' %}
    {% set connection_command = 'telnet serial4 7001' %}
    {% set hard_reset_command = '/usr/local/lab-scripts/snmp_pdu_control --hostname pdu18 --command reboot --port 10 --delay 10' %}
    {% set power_off_command = '/usr/local/lab-scripts/snmp_pdu_control --hostname pdu18 --command off --port 10 --delay 10' %}
    {% set power_on_command = '/usr/local/lab-scripts/snmp_pdu_control --hostname pdu18 --command on --port 10 --delay 10' %}
    {% set usb_label = 'SanDiskCruzerBlade' %}
    {% set usb_uuid = 'usb-SanDisk_Cruzer_Blade_20060266531DA442AD42-0:0' %}
    {% set usb_device_id = 0 %}"""
        template_dict = self.render_device_dictionary_from_text(data)
        self.assertIsNotNone(template_dict)
        self.assertEqual({"deploy": 30, "boot": 30}, template_dict["character_delays"])
        self.assertIn("error-messages", template_dict["constants"]["u-boot"])
        self.assertEqual(
            "juno#",
            template_dict["actions"]["boot"]["methods"]["u-boot"]["parameters"][
                "bootloader_prompt"
            ],
        )
        self.assertEqual(
            "Shell>",
            template_dict["actions"]["boot"]["methods"]["uefi"]["parameters"][
                "bootloader_prompt"
            ],
        )
        self.assertEqual(
            "Start:",
            template_dict["actions"]["boot"]["methods"]["uefi-menu"]["parameters"][
                "bootloader_prompt"
            ],
        )

        template_dict = self.render_device_dictionary_from_text(
            data, {"bootloader_prompt": "vexpress>"}
        )
        self.assertIsNotNone(template_dict)
        self.assertEqual({"deploy": 30, "boot": 30}, template_dict["character_delays"])
        self.assertIn("error-messages", template_dict["constants"]["u-boot"])
        self.assertEqual(
            "vexpress>",
            template_dict["actions"]["boot"]["methods"]["u-boot"]["parameters"][
                "bootloader_prompt"
            ],
        )
        self.assertEqual(
            "Shell>",
            template_dict["actions"]["boot"]["methods"]["uefi"]["parameters"][
                "bootloader_prompt"
            ],
        )
        self.assertEqual(
            "Start:",
            template_dict["actions"]["boot"]["methods"]["uefi-menu"]["parameters"][
                "bootloader_prompt"
            ],
        )
        self.assertIn("nfs", template_dict["actions"]["boot"]["methods"]["u-boot"])
        self.assertIn(
            "commands", template_dict["actions"]["boot"]["methods"]["u-boot"]["nfs"]
        )
        commands = template_dict["actions"]["boot"]["methods"]["u-boot"]["nfs"][
            "commands"
        ]
        check = 0
        for line in commands:
            if line.startswith("setenv bootargs console"):
                check = 1
                self.assertIn(",vers=3 ", line)
        if not check:
            self.fail("Unable to find setenv nfsargs")

    def test_imx8mq_evk_template(self):
        fastboot_cmd_order = [
            "bootloader",
            "bootloader_a",
            "bootloader_b",
            "bootloader0",
            "gpt",
            "boot",
            "boot_a",
            "boot_b",
            "dtbo",
            "dtbo_a",
            "dtbo_b",
            "vbmeta",
            "vbmeta_a",
            "vbmeta_b",
            "system",
            "system_a",
            "system_b",
            "vendor",
            "vendor_a",
            "vendor_b",
            "recovery",
        ]

        template_dict = self.render_device_dictionary("imx8mq-evk-01")
        self.assertIsNotNone(template_dict)
        self.assertIn("error-messages", template_dict["constants"]["u-boot"])
        self.assertEqual(
            "=>",
            template_dict["actions"]["boot"]["methods"]["u-boot"]["parameters"][
                "bootloader_prompt"
            ],
        )

        context = {"bootloader_prompt": "=>"}
        template_dict = self.render_device_dictionary("imx8mq-evk-01", context)
        self.assertIsNotNone(template_dict)
        self.assertIn("error-messages", template_dict["constants"]["u-boot"])
        self.assertEqual(
            "=>",
            template_dict["actions"]["boot"]["methods"]["u-boot"]["parameters"][
                "bootloader_prompt"
            ],
        )

        for cmd in template_dict["flash_cmds_order"]:
            idx = template_dict["flash_cmds_order"].index(cmd)
            self.assertEqual(cmd, fastboot_cmd_order[idx])
        # test overwriting kernel args
        checked = False
        context = {"console_device": "ttyUSB1"}
        template_dict = self.render_device_dictionary("imx8mq-evk-01", context)
        commands = template_dict["actions"]["boot"]["methods"]["u-boot"]["ramdisk"][
            "commands"
        ]
        self.assertIsNotNone(commands)
        self.assertIsInstance(commands, list)
        for line in commands:
            if "setenv bootargs" in line:
                self.assertIn("console=ttyUSB1", line)
                checked = True
        self.assertTrue(checked)

    def test_x15_template(self):
        # Test that we can override fastboot_deploy_uboot_commands
        rendered = self.render_device_dictionary("x15-01")
        params = rendered["actions"]["deploy"]["methods"]["u-boot"]["parameters"]
        self.assertEqual(params["fastboot"]["commands"], ["fastboot 1"])
        self.assertIsNone(rendered["actions"]["deploy"]["methods"]["fastboot"])

        rendered = self.render_device_dictionary(
            "x15-01",
            job_ctx={"fastboot_deploy_uboot_commands": ["fastboot 0"]},
        )
        params = rendered["actions"]["deploy"]["methods"]["u-boot"]["parameters"]
        self.assertEqual(params["fastboot"]["commands"], ["fastboot 0"])
        self.assertIsNone(rendered["actions"]["deploy"]["methods"]["fastboot"])

        rendered = self.render_device_dictionary(
            "x15-01",
            job_ctx={
                "fastboot_deploy_uboot_commands": [
                    "setenv autoload no",
                    "dhcp",
                    "fastboot udp",
                ]
            },
        )
        params = rendered["actions"]["deploy"]["methods"]["u-boot"]["parameters"]
        self.assertEqual(
            params["fastboot"]["commands"],
            ["setenv autoload no", "dhcp", "fastboot udp"],
        )

    def test_xilinx_zcu102(self):
        template_dict = self.render_device_dictionary("zcu102")
        self.assertIn("u-boot", template_dict["actions"]["boot"]["methods"])
        self.assertIn("ramdisk", template_dict["actions"]["boot"]["methods"]["u-boot"])
        commands = template_dict["actions"]["boot"]["methods"]["u-boot"]["ramdisk"][
            "commands"
        ]
        for command in commands:
            if not command.startswith("setenv loadkernel"):
                continue
            self.assertNotIn("tftp ", command)
            self.assertIn("tftpb", command)

    def test_flasher(self):
        data = """{% extends 'b2260.jinja2' %}
{% set flasher_deploy_commands = ['flashing', 'something --else'] %}
"""
        template_dict = self.render_device_dictionary_from_text(data)
        self.assertEqual(
            ["flashing", "something --else"],
            template_dict["actions"]["deploy"]["methods"]["flasher"]["commands"],
        )

    def test_user_command(self):
        data = """{% extends 'b2260.jinja2' %}
{% set user_commands = {'set_boot_to_usb': {'do': '/bin/true', 'undo': '/bin/true'},
                        'set_boot_to_sd': {'do': '/bin/true', 'undo': '/bin/true'}} %}
"""
        template_dict = self.render_device_dictionary_from_text(data)
        self.assertEqual(
            {
                "set_boot_to_usb": {"do": "/bin/true", "undo": "/bin/true"},
                "set_boot_to_sd": {"do": "/bin/true", "undo": "/bin/true"},
            },
            template_dict["commands"]["users"],
        )

    def test_meson8b_template(self):
        template_dict = self.render_device_dictionary("meson8b-odroidc1-1")
        self.assertIsNotNone(template_dict)
        template_dict["constants"]["u-boot"].get("interrupt_ctrl_list", self.fail)
        self.assertEqual(
            template_dict["constants"]["u-boot"]["interrupt_ctrl_list"], ["c"]
        )

    def test_rzn1d_template(self):
        data = """{% extends 'rzn1d.jinja2' %}"""
        template_dict = self.render_device_dictionary_from_text(data)
        commands = template_dict["actions"]["boot"]["methods"]["u-boot"]["ramdisk"][
            "commands"
        ]
        for line in commands:
            if "setenv initrd_high" in line:
                self.fail("rzn1d should not have initrd_high set")
            if "setenv fdt_high" in line:
                self.fail("rzn1d should not have fdt_high set")
        # Check that "fit" boot command is available
        commands = template_dict["actions"]["boot"]["methods"]["u-boot"]["fit"][
            "commands"
        ]
        self.assertTrue(isinstance(commands, list))
