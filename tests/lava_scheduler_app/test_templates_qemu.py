# Copyright (C) 2019 Linaro Limited
#
# Author: Antonio Terceiro <antonio.terceiro@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from .test_templates import BaseTemplateTest


class TestQemuTemplates(BaseTemplateTest):
    """
    Test rendering of jinja2 templates

    When adding or modifying a jinja2 template, add or update the test here.
    Use realistic data - complete exports of the device dictionary preferably.
    Set debug to True to see the content of the rendered templates
    """

    def test_qemu_template(self):
        data = """{% extends 'qemu.jinja2' %}
{% set mac_addr = 'DE:AD:BE:EF:28:01' %}
{% set memory = 512 %}"""
        job_ctx = {"arch": "amd64", "no_kvm": True}
        template_dict = self.render_device_dictionary_from_text(data, job_ctx)
        options = template_dict["actions"]["boot"]["methods"]["qemu"]["parameters"][
            "options"
        ]
        self.assertNotIn("-enable-kvm", options)
        job_ctx = {"arch": "amd64", "no_kvm": False}
        template_dict = self.render_device_dictionary_from_text(data, job_ctx)
        options = template_dict["actions"]["boot"]["methods"]["qemu"]["parameters"][
            "options"
        ]
        self.assertIn("-enable-kvm", options)

    def test_qemu_installer(self):
        data = """{% extends 'qemu.jinja2' %}
{% set mac_addr = 'DE:AD:BE:EF:28:01' %}
{% set memory = 512 %}"""
        job_ctx = {"arch": "amd64"}
        template_dict = self.render_device_dictionary_from_text(data, job_ctx)
        self.assertEqual(
            "c",
            template_dict["actions"]["boot"]["methods"]["qemu"]["parameters"][
                "boot_options"
            ]["boot_order"],
        )

    def test_qemu_cortex_a57(self):
        data = """{% extends 'qemu.jinja2' %}
{% set memory = 2048 %}
{% set mac_addr = '52:54:00:12:34:59' %}
{% set arch = 'arm64' %}
{% set base_guest_fs_size = 2048 %}
        """
        job_ctx = {
            "arch": "amd64",
            "boot_root": "/dev/vda",
            "extra_options": [
                "-global",
                "virtio-blk-device.scsi=off",
                "-smp",
                1,
                "-device",
                "virtio-scsi-device,id=scsi",
            ],
        }
        template_dict = self.render_device_dictionary_from_text(data, job_ctx)
        options = template_dict["actions"]["boot"]["methods"]["qemu"]["parameters"][
            "options"
        ]
        self.assertIn("-cpu cortex-a57", options)
        self.assertNotIn("-global", options)
        extra = template_dict["actions"]["boot"]["methods"]["qemu"]["parameters"][
            "extra"
        ]
        self.assertIn("-global", extra)
        self.assertNotIn("-cpu cortex-a57", extra)
        options.extend(extra)
        self.assertIn("-global", options)
        self.assertIn("-cpu cortex-a57", options)

    def test_qemu_cortex_a57_nfs(self):
        data = """{% extends 'qemu.jinja2' %}
{% set memory = 2048 %}
{% set mac_addr = '52:54:00:12:34:59' %}
{% set arch = 'arm64' %}
{% set base_guest_fs_size = 2048 %}
        """
        job_ctx = {
            "arch": "amd64",
            "qemu_method": "qemu-nfs",
            "netdevice": "tap",
            "extra_options": ["-smp", 1],
        }
        template_dict = self.render_device_dictionary_from_text(data, job_ctx)
        self.assertIn("qemu-nfs", template_dict["actions"]["boot"]["methods"])
        params = template_dict["actions"]["boot"]["methods"]["qemu-nfs"]["parameters"]
        self.assertIn("command", params)
        self.assertEqual(params["command"], "qemu-system-aarch64")
        self.assertIn("options", params)
        self.assertIn("-cpu cortex-a57", params["options"])
        self.assertEqual("qemu-system-aarch64", params["command"])
        self.assertIn("-smp", params["extra"])
        self.assertIn("append", params)
        self.assertIn("nfsrootargs", params["append"])
        self.assertEqual(params["append"]["root"], "/dev/nfs")
        self.assertEqual(params["append"]["console"], "ttyAMA0")

    def test_docker_template(self):
        data = "{% extends 'docker.jinja2' %}"
        template_dict = self.render_device_dictionary_from_text(data)
        self.assertEqual(
            {
                "docker": {"options": {"remote": None}},
                "ssh": {
                    "options": [
                        "-o",
                        "Compression=yes",
                        "-o",
                        "PasswordAuthentication=no",
                        "-o",
                        "LogLevel=FATAL",
                    ],
                    "host": "",
                    "port": 22,
                    "user": "root",
                    "identity_file": "dynamic_vm_keys/lava",
                },
            },
            template_dict["actions"]["deploy"]["methods"],
        )
        self.assertEqual(
            {
                "docker": {
                    "options": {
                        "remote": None,
                        "cpus": 0.0,
                        "memory": 0,
                        "privileged": False,
                        "capabilities": [],
                        "devices": [],
                        "networks": [],
                        "volumes": [],
                        "extra_arguments": [],
                    }
                },
                "ssh": None,
            },
            template_dict["actions"]["boot"]["methods"],
        )

        data = """{% extends 'docker.jinja2' %}
{% set docker_cpus=2.1 %}
{% set docker_memory="120M" %}
{% set docker_capabilities = ["NET_ADMIN"] %}"
{% set docker_devices = ["/dev/kvm:/dev/kvm"] %}"
{% set docker_networks = ["mynet"] %}"
{% set docker_volumes = ["/home", "/tmp"] %}"""
        template_dict = self.render_device_dictionary_from_text(data)
        self.assertEqual(
            {
                "docker": {"options": {"remote": None}},
                "ssh": {
                    "options": [
                        "-o",
                        "Compression=yes",
                        "-o",
                        "PasswordAuthentication=no",
                        "-o",
                        "LogLevel=FATAL",
                    ],
                    "host": "",
                    "port": 22,
                    "user": "root",
                    "identity_file": "dynamic_vm_keys/lava",
                },
            },
            template_dict["actions"]["deploy"]["methods"],
        )
        self.assertEqual(
            {
                "docker": {
                    "options": {
                        "remote": None,
                        "cpus": 2.1,
                        "memory": "120M",
                        "privileged": False,
                        "capabilities": ["NET_ADMIN"],
                        "devices": ["/dev/kvm:/dev/kvm"],
                        "networks": ["mynet"],
                        "volumes": ["/home", "/tmp"],
                        "extra_arguments": [],
                    }
                },
                "ssh": None,
            },
            template_dict["actions"]["boot"]["methods"],
        )

        data = """{% extends 'docker.jinja2' %}
{% set docker_cpus=2.1 %}
{% set docker_memory="120M" %}
{% set docker_devices=["/dev/kvm"] %}
{% set docker_privileged = True %}"""
        template_dict = self.render_device_dictionary_from_text(data)
        self.assertEqual(
            {
                "docker": {"options": {"remote": None}},
                "ssh": {
                    "options": [
                        "-o",
                        "Compression=yes",
                        "-o",
                        "PasswordAuthentication=no",
                        "-o",
                        "LogLevel=FATAL",
                    ],
                    "host": "",
                    "port": 22,
                    "user": "root",
                    "identity_file": "dynamic_vm_keys/lava",
                },
            },
            template_dict["actions"]["deploy"]["methods"],
        )
        self.assertEqual(
            {
                "docker": {
                    "options": {
                        "remote": None,
                        "cpus": 2.1,
                        "memory": "120M",
                        "privileged": True,
                        "capabilities": [],
                        "devices": ["/dev/kvm"],
                        "networks": [],
                        "volumes": [],
                        "extra_arguments": [],
                    }
                },
                "ssh": None,
            },
            template_dict["actions"]["boot"]["methods"],
        )

        data = """{% extends 'docker.jinja2' %}
{% set docker_remote="tcp://10.192.244.7:2375" %}
{% set docker_cpus=2.1 %}
{% set docker_memory="120M" %}
{% set docker_devices=["/dev/kvm"] %}
{% set docker_privileged = True %}"""
        template_dict = self.render_device_dictionary_from_text(data)
        self.assertEqual(
            {
                "docker": {"options": {"remote": "tcp://10.192.244.7:2375"}},
                "ssh": {
                    "options": [
                        "-o",
                        "Compression=yes",
                        "-o",
                        "PasswordAuthentication=no",
                        "-o",
                        "LogLevel=FATAL",
                    ],
                    "host": "",
                    "port": 22,
                    "user": "root",
                    "identity_file": "dynamic_vm_keys/lava",
                },
            },
            template_dict["actions"]["deploy"]["methods"],
        )
        self.assertEqual(
            {
                "docker": {
                    "options": {
                        "remote": "tcp://10.192.244.7:2375",
                        "cpus": 2.1,
                        "memory": "120M",
                        "privileged": True,
                        "capabilities": [],
                        "devices": ["/dev/kvm"],
                        "networks": [],
                        "volumes": [],
                        "extra_arguments": [],
                    }
                },
                "ssh": None,
            },
            template_dict["actions"]["boot"]["methods"],
        )

    def test_lava_slave_docker(self):
        data = "{% extends 'lava-slave-docker.jinja2' %}"
        template_dict = self.render_device_dictionary_from_text(data)
        self.assertEqual(
            {
                "/srv/tftp:/srv/tftp",
                "/var/lib/lava/dispatcher/tmp:/var/lib/lava/dispatcher/tmp",
                "/etc/lava-coordinator:/etc/lava-coordinator",
                "/boot:/boot",
                "/lib/modules:/lib/modules",
            },
            set(
                template_dict["actions"]["boot"]["methods"]["docker"]["options"][
                    "volumes"
                ]
            ),
        )

    def test_qemu_misc(self):
        job_ctx = {"arch": "microblaze"}
        template_dict = self.render_device_dictionary("qemu01", job_ctx)
        self.assertIsNotNone(template_dict)
        self.assertEqual(
            {
                "arm64",
                "arm",
                "aarch64",
                "amd64",
                "x86_64",
                "i386",
                "alpha",
                "cris",
                "hppa",
                "lm32",
                "m68k",
                "microblaze",
                "microblazeel",
                "mips",
                "mipsel",
                "mips64",
                "mips64el",
                "moxie",
                "nios2",
                "or32",
                "ppc",
                "ppc64",
                "ppc64le",
                "riscv32",
                "riscv64",
                "s390x",
                "sh4",
                "sh4eb",
                "sparc",
                "sparc64",
                "tricore",
                "unicore32",
                "xtensa",
                "xtensaeb",
            },
            set(template_dict["available_architectures"]),
        )
        params = template_dict["actions"]["boot"]["methods"]["qemu"]["parameters"]
        self.assertIsNotNone(params["command"])
        self.assertEqual(params["command"], "qemu-system-" + job_ctx["arch"])
