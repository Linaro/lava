# Copyright (C) 2019 Linaro Limited
#
# Author: Antonio Terceiro <antonio.terceiro@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from .test_templates import BaseTemplateTest


class TestFastbootTemplates(BaseTemplateTest):
    """
    Test rendering of jinja2 templates

    When adding or modifying a jinja2 template, add or update the test here.
    Use realistic data - complete exports of the device dictionary preferably.
    Set debug to True to see the content of the rendered templates
    """

    def test_nexus4_template(self):
        data = """{% extends 'nexus4.jinja2' %}
{% set adb_serial_number = 'R32D300FRYP' %}
{% set fastboot_serial_number = 'R32D300FRYP' %}
{% set device_info = [{'board_id': 'R32D300FRYP'}] %}
{% set static_info = [{'board_id': 'R32D300FRYP'}] %}
"""
        template_dict = self.render_device_dictionary_from_text(data)
        self.assertEqual("R32D300FRYP", template_dict["adb_serial_number"])
        self.assertEqual("R32D300FRYP", template_dict["fastboot_serial_number"])
        self.assertEqual([], template_dict["fastboot_options"])
        self.assertIsNotNone(template_dict)
        self.assertIsInstance(template_dict["device_info"], list)
        self.assertIsInstance(template_dict["static_info"], list)

    def test_x15_template(self):
        data = """{% extends 'x15.jinja2' %}
{% set adb_serial_number = '1234567890' %}
{% set fastboot_serial_number = '1234567890' %}
{% set interrupt_prompt = "interrupt bootloader" %}
"""
        template_dict = self.render_device_dictionary_from_text(data)
        self.assertIsInstance(template_dict["adb_serial_number"], str)
        self.assertEqual("1234567890", template_dict["adb_serial_number"])
        self.assertEqual("1234567890", template_dict["fastboot_serial_number"])
        self.assertEqual([], template_dict["fastboot_options"])
        self.assertIn("u-boot", template_dict["actions"]["boot"]["methods"])
        self.assertIn(
            "parameters", template_dict["actions"]["boot"]["methods"]["u-boot"]
        )
        self.assertIn(
            "interrupt_prompt",
            template_dict["actions"]["boot"]["methods"]["u-boot"]["parameters"],
        )
        self.assertEqual(
            "interrupt bootloader",
            template_dict["actions"]["boot"]["methods"]["u-boot"]["parameters"][
                "interrupt_prompt"
            ],
        )
        # fastboot deploy to eMMC
        self.assertIn("mmc", template_dict["actions"]["boot"]["methods"]["u-boot"])
        self.assertIn(
            "commands", template_dict["actions"]["boot"]["methods"]["u-boot"]["mmc"]
        )
        # NFS using standard U-Boot TFTP
        self.assertIn("nfs", template_dict["actions"]["boot"]["methods"]["u-boot"])
        self.assertIn(
            "commands", template_dict["actions"]["boot"]["methods"]["u-boot"]["nfs"]
        )
        for command in template_dict["actions"]["boot"]["methods"]["u-boot"]["nfs"][
            "commands"
        ]:
            if "setenv bootargs" in command:
                # x15 needs both consoles enabled.
                self.assertIn("ttyS2", command)
                self.assertNotIn("console=ttyO2", command)
        for board in template_dict["device_info"]:
            self.assertEqual(template_dict["fastboot_serial_number"], board["board_id"])

    def test_sharkl2_template(self):
        data = """{% extends 'sharkl2.jinja2' %}
{% set adb_serial_number = 'R32D300FRYP' %}
{% set fastboot_serial_number = 'R32D300FRYP' %}
"""
        template_dict = self.render_device_dictionary_from_text(data)
        self.assertEqual("R32D300FRYP", template_dict["adb_serial_number"])
        self.assertEqual("R32D300FRYP", template_dict["fastboot_serial_number"])
        self.assertEqual([], template_dict["fastboot_options"])
        self.assertIn("u-boot", template_dict["actions"]["boot"]["methods"])
        self.assertIn(
            "parameters", template_dict["actions"]["boot"]["methods"]["u-boot"]
        )
        self.assertIn(
            "interrupt_prompt",
            template_dict["actions"]["boot"]["methods"]["u-boot"]["parameters"],
        )
        # fastboot boot off eMMC
        self.assertIn("fastboot", template_dict["actions"]["boot"]["methods"])
        self.assertIn("reboot", template_dict["actions"]["boot"]["methods"]["fastboot"])

    def test_nexus10_template(self):
        data = """{% extends 'nexus10.jinja2' %}
{% set adb_serial_number = 'R32D300FRYP' %}
{% set fastboot_serial_number = 'R32D300FRYP' %}
{% set soft_reboot_command = 'adb -s R32D300FRYP reboot bootloader' %}
{% set connection_command = 'adb -s R32D300FRYP shell' %}
{% set device_info = [{'board_id': 'R32D300FRYP'}] %}
{% set static_info = [{'board_id': 'R32D300FRYP'}] %}
"""
        template_dict = self.render_device_dictionary_from_text(data)
        self.assertIsNotNone(template_dict)
        self.assertIsInstance(template_dict["device_info"], list)
        self.assertIsInstance(template_dict["static_info"], list)

    def test_hikey_r2_template(self):
        template_dict = self.render_device_dictionary("hi6220-hikey-r2-01")
        self.assertIsNotNone(template_dict)
        self.assertIsInstance(template_dict["device_info"], list)
        self.assertIsInstance(template_dict["static_info"], list)
        self.assertEqual(template_dict["device_info"][0]["board_id"], "0123456789")
        self.assertEqual(template_dict["static_info"][0]["board_id"], "S_N0123456")
        self.assertIsInstance(template_dict["fastboot_options"], list)
        self.assertEqual(template_dict["fastboot_options"], ["-S", "256M"])
        order = template_dict["flash_cmds_order"]
        self.assertEqual(0, order.index("ptable"))
        self.assertEqual(1, order.index("xloader"))
        self.assertEqual(2, order.index("fastboot"))

    def test_hikey_template(self):
        template_dict = self.render_device_dictionary("hi6220-hikey-01")
        self.assertIsNotNone(template_dict)
        self.assertIsInstance(template_dict["device_info"], list)
        self.assertIsInstance(template_dict["static_info"], list)
        self.assertEqual(template_dict["device_info"][0]["board_id"], "0123456789")
        self.assertEqual(template_dict["static_info"][0]["board_id"], "S_N0123456")
        self.assertIsInstance(template_dict["fastboot_options"], list)
        self.assertEqual(template_dict["fastboot_options"], ["-S", "256M"])
        order = template_dict["flash_cmds_order"]
        self.assertEqual(0, order.index("ptable"))
        self.assertEqual(1, order.index("fastboot"))
        self.assertIn("cache", order)
        self.assertIn("system", order)
        self.assertIn("userdata", order)
        self.assertNotIn("xloader", order)

        # test support for retrieving MAC from device.
        data = """{% extends 'hi6220-hikey-01.jinja2' %}
{% set device_mac = '00:E0:4C:53:44:58' %}"""
        template_dict = self.render_device_dictionary_from_text(
            data, use_device_templates=True
        )
        self.assertIn("parameters", template_dict)
        self.assertIn("interfaces", template_dict["parameters"])
        self.assertIn("target", template_dict["parameters"]["interfaces"])
        self.assertIn("mac", template_dict["parameters"]["interfaces"]["target"])
        self.assertIn("ip", template_dict["parameters"]["interfaces"]["target"])
        self.assertIsNotNone(template_dict["parameters"]["interfaces"]["target"]["mac"])
        self.assertNotEqual(
            "", template_dict["parameters"]["interfaces"]["target"]["mac"]
        )
        self.assertIsNone(template_dict["parameters"]["interfaces"]["target"]["ip"])

    def test_hikey_grub_efi(self):
        job_ctx = {"kernel": "Image", "devicetree": "hi6220-hikey.dtb"}
        template_dict = self.render_device_dictionary("hi6220-hikey-01", job_ctx)
        self.assertIsNotNone(template_dict)
        self.assertIsNotNone(template_dict["actions"]["boot"]["methods"])
        self.assertIn("grub-efi", template_dict["actions"]["boot"]["methods"])
        self.assertEqual(
            "fastboot",
            template_dict["actions"]["boot"]["methods"]["grub-efi"]["menu_options"],
        )
        params = template_dict["actions"]["boot"]["methods"]["grub-efi"]
        self.assertEqual(params["parameters"]["bootloader_prompt"], "grub>")
        for command in params["installed"]["commands"]:
            if command.startswith("search"):
                self.assertIn("rootfs", command)
            elif command.startswith("linux"):
                self.assertIn("/boot/Image", command)
            elif command.startswith("devicetree"):
                self.assertIn("hi6220-hikey.dtb", command)
            elif "root=" in command:
                self.assertIn("/dev/mmcblk0p9", command)
                self.assertIn("ttyAMA3", command)
            else:
                self.assertEqual("boot", command)
        self.assertIn("ssh", template_dict["actions"]["deploy"]["methods"])
        params = template_dict["actions"]["deploy"]["methods"]["ssh"]
        self.assertIsNotNone(params)
        self.assertIn("port", params)
        self.assertIn("user", params)
        self.assertIn("options", params)
        self.assertIn("identity_file", params)

    def test_hikey620_uarts(self):
        template_dict = self.render_device_dictionary("hi6220-hikey-01")
        self.assertIsNotNone(template_dict)
        self.assertIn("commands", template_dict)
        self.assertNotIn("connect", template_dict["commands"])
        self.assertIn("connections", template_dict["commands"])
        self.assertIn("uart0", template_dict["commands"]["connections"])
        self.assertIn("uart1", template_dict["commands"]["connections"])
        self.assertIn("tags", template_dict["commands"]["connections"]["uart1"])
        self.assertIn(
            "primary", template_dict["commands"]["connections"]["uart1"]["tags"]
        )
        self.assertNotIn("tags", template_dict["commands"]["connections"]["uart0"])
        self.assertEqual(
            template_dict["commands"]["connections"]["uart0"]["connect"],
            "telnet localhost 4002",
        )
        self.assertEqual(
            template_dict["commands"]["connections"]["uart1"]["connect"],
            "telnet 192.168.1.200 8001",
        )

    def test_hikey960_grub(self):
        template_dict = self.render_device_dictionary("hi960-hikey-01")
        self.assertIsNotNone(template_dict)
        self.assertIsNotNone(template_dict["actions"]["boot"]["methods"])
        self.assertNotIn(
            "menu_options", template_dict["actions"]["boot"]["methods"]["grub"]
        )
        self.assertIn("grub", template_dict["actions"]["boot"]["methods"])
        params = template_dict["actions"]["boot"]["methods"]["grub"]
        for command in params["installed"]["commands"]:
            self.assertEqual("boot", command)
        self.assertIn("ssh", template_dict["actions"]["deploy"]["methods"])
        params = template_dict["actions"]["deploy"]["methods"]["ssh"]
        self.assertIsNotNone(params)
        self.assertIn("port", params)
        self.assertIn("user", params)
        self.assertIn("options", params)
        self.assertIn("identity_file", params)

        # test support for retrieving MAC from device using base-fastboot.
        data = """{% extends 'hi960-hikey-01.jinja2' %}
{% set device_mac = '00:E0:4C:53:44:58' %}"""
        template_dict = self.render_device_dictionary_from_text(
            data, use_device_templates=True
        )
        self.assertIn("parameters", template_dict)
        self.assertIn("interfaces", template_dict["parameters"])
        self.assertIn("target", template_dict["parameters"]["interfaces"])
        self.assertIn("mac", template_dict["parameters"]["interfaces"]["target"])
        self.assertIn("ip", template_dict["parameters"]["interfaces"]["target"])
        self.assertIsNotNone(template_dict["parameters"]["interfaces"]["target"]["mac"])
        self.assertNotEqual(
            "", template_dict["parameters"]["interfaces"]["target"]["mac"]
        )
        self.assertEqual(
            "00:E0:4C:53:44:58",
            template_dict["parameters"]["interfaces"]["target"]["mac"],
        )
        self.assertIsNone(template_dict["parameters"]["interfaces"]["target"]["ip"])

    def test_nexus5x_template(self):
        data = """{% extends 'nexus5x.jinja2' %}
{% set adb_serial_number = '10de1214adae123' %}
{% set fastboot_serial_number = '10de1214adae123' %}
{% set device_info = [{'board_id': '10de1214adae123'}] %}
{% set static_info = [{'board_id': '10de1214adae123'}] %}
"""
        template_dict = self.render_device_dictionary_from_text(data)
        self.assertIsNotNone(template_dict)
        self.assertIsInstance(template_dict["device_info"], list)
        self.assertIsInstance(template_dict["static_info"], list)

    def test_pixel_template(self):
        data = """{% extends 'pixel.jinja2' %}
{% set adb_serial_number = 'FDAC1231DAD' %}
{% set fastboot_serial_number = 'FDAC1231DAD' %}
{% set device_info = [{'board_id': 'FDAC1231DAD'}] %}
{% set static_info = [{'board_id': 'FDAC1231DAD'}] %}
"""
        template_dict = self.render_device_dictionary_from_text(data)
        self.assertIsNotNone(template_dict)
        self.assertIsInstance(template_dict["device_info"], list)
        self.assertIsInstance(template_dict["static_info"], list)

    def test_nuc_template(self):
        template_data = """{% extends 'adb-nuc.jinja2' %}
{% set device_ip = '192.168.1.11' %}
"""
        self.render_device_dictionary_from_text(template_data)

    def test_ifc6410(self):
        data = """{% extends 'ifc6410.jinja2' %}
{% set adb_serial_number = 'e080c212' %}
{% set fastboot_serial_number = 'e080c212' %}
        """
        template_dict = self.render_device_dictionary_from_text(data)
        self.assertEqual("e080c212", template_dict["adb_serial_number"])
        self.assertEqual("e080c212", template_dict["fastboot_serial_number"])
        self.assertEqual([], template_dict["fastboot_options"])
        methods = template_dict["actions"]["boot"]["methods"]["fastboot"]
        self.assertIn("reboot", methods)
        self.assertIn("boot", methods)
        self.assertIn("auto-login", methods)
        self.assertIn("overlay-unpack", methods)

    def test_db820c_template(self):
        data = """{% extends 'dragonboard-820c.jinja2' %}
{% set adb_serial_number = '3083f595' %}
{% set fastboot_serial_number = '3083f595' %}
"""
        template_dict = self.render_device_dictionary_from_text(data)
        self.assertEqual("3083f595", template_dict["adb_serial_number"])
        self.assertEqual("3083f595", template_dict["fastboot_serial_number"])
        self.assertEqual([], template_dict["fastboot_options"])

    def test_recovery_mode(self):
        template_dict = self.render_device_dictionary("hi6220-hikey-bl-01")
        recovery = template_dict["actions"]["deploy"]["methods"]
        self.assertIsNotNone("recovery", recovery)
        self.assertIn("recovery", recovery)
        self.assertIn("commands", recovery["recovery"])
        self.assertIsNotNone("recovery", recovery["recovery"]["commands"])
        self.assertIn("recovery_mode", recovery["recovery"]["commands"])
        self.assertEqual(
            [
                "/home/neil/lava-lab/shared/lab-scripts/eth008_control -a 10.15.0.171 -r 1 -s off",
                "/home/neil/lava-lab/shared/lab-scripts/eth008_control -a 10.15.0.171 -r 2 -s on",
            ],
            recovery["recovery"]["commands"]["recovery_mode"],
        )
        self.assertIn("recovery_exit", recovery["recovery"]["commands"])
        self.assertEqual(
            [
                "/home/neil/lava-lab/shared/lab-scripts/eth008_control -a 10.15.0.171 -r 1 -s on",
                "/home/neil/lava-lab/shared/lab-scripts/eth008_control -a 10.15.0.171 -r 2 -s off",
            ],
            recovery["recovery"]["commands"]["recovery_exit"],
        )

    def test_sdm845_mtp_template(self):
        fastboot_cmd_order = [
            "update",
            "ptable",
            "partition",
            "hyp",
            "modem",
            "rpm",
            "sbl1",
            "sbl2",
            "sec",
            "tz",
            "aboot",
            "cdt",
            "boot",
            "rootfs",
            "vendor",
            "system",
            "cache",
            "userdata",
        ]

        template_dict = self.render_device_dictionary("sdm845-mtp-05")
        self.assertEqual("5c302cef", template_dict["adb_serial_number"])
        self.assertEqual("5c302cef", template_dict["fastboot_serial_number"])
        self.assertEqual(False, template_dict["device_info"][0]["wait_device_board_id"])
        self.assertEqual([], template_dict["fastboot_options"])

        for cmd in template_dict["flash_cmds_order"]:
            idx = template_dict["flash_cmds_order"].index(cmd)
            self.assertEqual(cmd, fastboot_cmd_order[idx])
