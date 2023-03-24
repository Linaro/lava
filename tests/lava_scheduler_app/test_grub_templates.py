from tests.lava_scheduler_app.test_base_templates import (
    BaseTemplate,
    prepare_jinja_template,
)


class TestGrubTemplates(BaseTemplate.BaseTemplateCases):
    """
    Test rendering of jinja2 templates

    When adding or modifying a jinja2 template, add or update the test here.
    Use realistic data - complete exports of the device dictionary preferably.
    Set debug to True to see the content of the rendered templates
    """

    def test_mustang_pxe_grub_efi_template(self):
        data = """{% extends 'mustang-grub-efi.jinja2' %}
{% set hard_reset_command = '/usr/bin/pduclient --daemon services --hostname pdu09 --command reboot --port 05' %}
{% set power_off_command = '/usr/bin/pduclient --daemon services --hostname pdu09 --command off --port 05' %}
{% set power_on_command = '/usr/bin/pduclient --daemon services --hostname pdu09 --command on --port 05' %}
{% set connection_command = 'telnet localhost 7012' %}"""
        self.assertTrue(self.validate_data("staging-mustang-01", data))
        template_dict = prepare_jinja_template("staging-mustang-01", data, raw=False)
        self.assertIn("uefi-menu", template_dict["actions"]["boot"]["methods"])
        self.assertIn(
            "pxe-grub", template_dict["actions"]["boot"]["methods"]["uefi-menu"]
        )
        self.assertNotIn(
            "grub", template_dict["actions"]["boot"]["methods"]["uefi-menu"]
        )
        # label class regex is mangled by jinja/yaml processing
        self.assertNotIn(
            "label_class",
            template_dict["actions"]["boot"]["methods"]["uefi-menu"]["parameters"],
        )
        self.assertIn("grub-efi", template_dict["actions"]["boot"]["methods"])
        self.assertIn(
            "menu_options", template_dict["actions"]["boot"]["methods"]["grub-efi"]
        )
        self.assertEqual(
            template_dict["actions"]["boot"]["methods"]["grub-efi"]["menu_options"],
            "pxe-grub",
        )
        self.assertIn(
            "ramdisk", template_dict["actions"]["boot"]["methods"]["grub-efi"]
        )
        self.assertIn(
            "commands",
            template_dict["actions"]["boot"]["methods"]["grub-efi"]["ramdisk"],
        )
        self.assertIn("nfs", template_dict["actions"]["boot"]["methods"]["grub-efi"])
        self.assertIn(
            "commands", template_dict["actions"]["boot"]["methods"]["grub-efi"]["nfs"]
        )
        nfs_commands = template_dict["actions"]["boot"]["methods"]["grub-efi"]["nfs"][
            "commands"
        ]
        self.assertNotIn("insmod efinet", nfs_commands)
        self.assertNotIn("net_bootp", nfs_commands)

    def test_mustang_grub_efi_template(self):
        data = """{% extends 'mustang-grub-efi.jinja2' %}
{% set grub_efi_method = 'grub' %}
{% set hard_reset_command = '/usr/bin/pduclient --daemon services --hostname pdu09 --command reboot --port 05' %}
{% set power_off_command = '/usr/bin/pduclient --daemon services --hostname pdu09 --command off --port 05' %}
{% set power_on_command = '/usr/bin/pduclient --daemon services --hostname pdu09 --command on --port 05' %}
{% set connection_command = 'telnet localhost 7012' %}"""
        self.assertTrue(self.validate_data("staging-mustang-01", data))
        template_dict = prepare_jinja_template("staging-mustang-01", data, raw=False)
        self.assertIn("uefi-menu", template_dict["actions"]["boot"]["methods"])
        self.assertNotIn(
            "pxe-grub", template_dict["actions"]["boot"]["methods"]["uefi-menu"]
        )
        self.assertIn("grub", template_dict["actions"]["boot"]["methods"]["uefi-menu"])
        self.assertEqual(
            template_dict["actions"]["boot"]["methods"]["grub-efi"]["menu_options"],
            "grub",
        )
        self.assertIn(
            "ramdisk", template_dict["actions"]["boot"]["methods"]["grub-efi"]
        )
        self.assertIn(
            "commands",
            template_dict["actions"]["boot"]["methods"]["grub-efi"]["ramdisk"],
        )
        self.assertIn("nfs", template_dict["actions"]["boot"]["methods"]["grub-efi"])
        self.assertIn(
            "commands", template_dict["actions"]["boot"]["methods"]["grub-efi"]["nfs"]
        )
        nfs_commands = template_dict["actions"]["boot"]["methods"]["grub-efi"]["nfs"][
            "commands"
        ]
        self.assertIn("insmod efinet", nfs_commands)
        self.assertIn("net_bootp", nfs_commands)

    def test_mustang_secondary_media(self):
        data = """{% extends 'mustang-grub-efi.jinja2' %}
{% set sata_label = 'ST500DM002' %}
{% set sata_uuid = 'ata-ST500DM002-1BD142_S2AKYFSN' %}
{% set grub_efi_method = 'pxe-grub' %}
{% set hard_reset_command = '/usr/bin/pduclient --daemon services --hostname pdu09 --command reboot --port 05' %}
{% set power_off_command = '/usr/bin/pduclient --daemon services --hostname pdu09 --command off --port 05' %}
{% set power_on_command = '/usr/bin/pduclient --daemon services --hostname pdu09 --command on --port 05' %}
{% set connection_command = 'telnet localhost 7012' %}"""
        self.assertTrue(self.validate_data("staging-mustang-01", data))
        template_dict = prepare_jinja_template("staging-mustang-01", data, raw=False)
        parameters = {
            "parameters": {
                "media": {
                    "sata": {
                        "ST500DM002": {
                            "boot_part": 1,
                            "device_id": 0,
                            "grub_interface": "hd0",
                            "uboot_interface": "scsi",
                            "uuid": "ata-ST500DM002-1BD142_S2AKYFSN",
                        },
                        "UUID-required": True,
                    }
                }
            }
        }
        self.assertTrue(template_dict["parameters"] == parameters["parameters"])
        self.assertIn("sata", template_dict["actions"]["boot"]["methods"]["grub-efi"])
        commands = {
            "commands": [
                "insmod gzio",
                "linux (hd0,gpt1)/{KERNEL} console=ttyS0,115200n8 debug root=/dev/sda2 rw ip=:::::eth0:dhcp",
                "initrd (hd0,gpt1/{RAMDISK}",
                "boot",
            ]
        }
        self.assertEqual(
            commands, template_dict["actions"]["boot"]["methods"]["grub-efi"]["sata"]
        )

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
        self.assertTrue(self.validate_data("staging-overdrive-01", data))
        template_dict = prepare_jinja_template("staging-overdrive-01", data, raw=False)
        self.assertIsNotNone(template_dict)
        self.assertIn("parameters", template_dict)
        self.assertIn("interfaces", template_dict["parameters"])
        self.assertIn("actions", template_dict)
        self.assertIn("character_delays", template_dict)
        self.assertIn("boot", template_dict["character_delays"])
        self.assertEqual(100, template_dict["character_delays"]["boot"])
        self.assertIn("iface2", template_dict["parameters"]["interfaces"])
        self.assertIn("iface1", template_dict["parameters"]["interfaces"])
        self.assertIn("iface0", template_dict["parameters"]["interfaces"])
        self.assertIn("sysfs", template_dict["parameters"]["interfaces"]["iface2"])
        self.assertEqual(
            [
                check
                for check in template_dict["actions"]["boot"]["methods"]["grub"]["nfs"][
                    "commands"
                ]
                if "nfsroot" in check
            ][0].count("nfsroot"),
            1,
        )
        self.assertIn(
            " rw",
            [
                check
                for check in template_dict["actions"]["boot"]["methods"]["grub"]["nfs"][
                    "commands"
                ]
                if "nfsroot" in check
            ][0],
        )

    def test_synquacer_acpi_template(self):
        template_dict = self.render_device_dictionary_file(
            "synquacer-acpi-01.jinja2", raw=False
        )
        self.assertIsNotNone(template_dict["actions"]["boot"]["methods"]["grub"])
        self.assertIn("ramdisk", template_dict["actions"]["boot"]["methods"]["grub"])
        self.assertIn(
            "commands", template_dict["actions"]["boot"]["methods"]["grub"]["ramdisk"]
        )
        self.assertIn(
            "net_add_addr lava efinet0 192.168.25.43",
            template_dict["actions"]["boot"]["methods"]["grub"]["ramdisk"]["commands"],
        )
        self.assertIn(
            "linux (tftp,{SERVER_IP})/{KERNEL}  ip=192.168.25.43::192.168.25.1:255.255.255.0:::off:192.168.25.1: ",
            template_dict["actions"]["boot"]["methods"]["grub"]["ramdisk"]["commands"],
        )

    def test_synquacer_dtb_template(self):
        template_dict = self.render_device_dictionary_file(
            "synquacer-dtb-01.jinja2", raw=False
        )
        self.assertIsNotNone(template_dict["actions"]["boot"]["methods"]["grub"])
        self.assertIn("ramdisk", template_dict["actions"]["boot"]["methods"]["grub"])
        self.assertIn(
            "commands", template_dict["actions"]["boot"]["methods"]["grub"]["ramdisk"]
        )
        self.assertIn(
            "net_add_addr lava efinet0 192.168.25.42",
            template_dict["actions"]["boot"]["methods"]["grub"]["ramdisk"]["commands"],
        )
        self.assertIn(
            "linux (tftp,{SERVER_IP})/{KERNEL}  ip=192.168.25.42::192.168.25.1:255.255.255.0:::off:192.168.25.1: ",
            template_dict["actions"]["boot"]["methods"]["grub"]["ramdisk"]["commands"],
        )

    def test_moonshot_m400_template(self):
        template_dict = self.render_device_dictionary_file(
            "moonshot-m400-17.jinja2", raw=False
        )
        self.assertIsNotNone(template_dict["actions"]["boot"]["methods"]["grub"])
        self.assertIn("ramdisk", template_dict["actions"]["boot"]["methods"]["grub"])
        self.assertIn(
            "commands", template_dict["actions"]["boot"]["methods"]["grub"]["ramdisk"]
        )
        self.assertIn(
            "linux (tftp,{SERVER_IP})/{KERNEL} console=ttyS0,9600 ip=dhcp ",
            template_dict["actions"]["boot"]["methods"]["grub"]["ramdisk"]["commands"],
        )

    def test_minnowboard_turbot_template(self):
        template_dict = self.render_device_dictionary_file(
            "minnowboard-turbot-E3826-01.jinja2", raw=False
        )
        grub = template_dict["actions"]["boot"]["methods"]["grub"]
        self.assertIsNotNone(grub)

        self.assertIn("ramdisk", grub)
        self.assertIn("commands", grub["ramdisk"])
        ramdisk_commands = grub["ramdisk"]["commands"]
        ramdisk_ref_commands = [
            "set net_default_server={SERVER_IP}",
            "linux (tftp)/{KERNEL} console=tty0 console=ttyS0,115200 root=/dev/ram0 ip=:::::eth0:dhcp",
            "initrd (tftp)/{RAMDISK}",
            "boot",
        ]
        self.assertEqual(ramdisk_commands, ramdisk_ref_commands)

        self.assertIn("nfs", grub)
        self.assertIn("commands", grub["nfs"])
        nfs_commands = grub["nfs"]["commands"]
        nfs_ref_commands = [
            "set net_default_server={SERVER_IP}",
            "linux (tftp)/{KERNEL} console=tty0 console=ttyS0,115200 root=/dev/nfs rw nfsroot={NFS_SERVER_IP}:{NFSROOTFS},tcp,hard ip=dhcp",
            "initrd (tftp)/{RAMDISK}",
            "boot",
        ]
        self.assertEqual(nfs_commands, nfs_ref_commands)

    def test_qdf2400_template(self):
        template_dict = self.render_device_dictionary_file(
            "qcom-qdf2400-01.jinja2", raw=False
        )
        grub = template_dict["actions"]["boot"]["methods"]["grub"]
        self.assertIsNotNone(grub)
        nfs_commands = template_dict["actions"]["boot"]["methods"]["grub"]["nfs"][
            "commands"
        ]
        self.assertIn("insmod efinet", nfs_commands)
        self.assertNotIn("net_bootp", nfs_commands)
