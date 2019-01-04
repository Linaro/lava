import yaml

# pylint: disable=superfluous-parens,ungrouped-imports
from lava_scheduler_app.tests.test_base_templates import (
    BaseTemplate,
    prepare_jinja_template,
)

# pylint: disable=too-many-branches,too-many-public-methods
# pylint: disable=too-many-nested-blocks


class TestQemuTemplates(BaseTemplate.BaseTemplateCases):
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

    def test_qemu_template(self):
        data = """{% extends 'qemu.jinja2' %}
{% set mac_addr = 'DE:AD:BE:EF:28:01' %}
{% set memory = 512 %}"""
        job_ctx = {"arch": "amd64", "no_kvm": True}
        self.assertTrue(self.validate_data("staging-qemu-01", data, job_ctx))
        test_template = prepare_jinja_template(
            "staging-qemu-01", data, job_ctx=None, raw=True
        )
        rendered = test_template.render(**job_ctx)
        template_dict = yaml.safe_load(rendered)
        options = template_dict["actions"]["boot"]["methods"]["qemu"]["parameters"][
            "options"
        ]
        self.assertNotIn("-enable-kvm", options)
        job_ctx = {"arch": "amd64", "no_kvm": False}
        rendered = test_template.render(**job_ctx)
        template_dict = yaml.safe_load(rendered)
        options = template_dict["actions"]["boot"]["methods"]["qemu"]["parameters"][
            "options"
        ]
        self.assertIn("-enable-kvm", options)

    def test_qemu_installer(self):
        data = """{% extends 'qemu.jinja2' %}
{% set mac_addr = 'DE:AD:BE:EF:28:01' %}
{% set memory = 512 %}"""
        job_ctx = {"arch": "amd64"}
        template_dict = prepare_jinja_template(
            "staging-qemu-01", data, job_ctx=job_ctx, raw=False
        )
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
        self.assertTrue(self.validate_data("staging-qemu-01", data))
        template_dict = prepare_jinja_template(
            "staging-juno-01", data, job_ctx=job_ctx, raw=False
        )
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
        self.assertTrue(self.validate_data("staging-qemu-01", data))
        template_dict = prepare_jinja_template(
            "staging-juno-01", data, job_ctx=job_ctx, raw=False
        )
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
        self.assertTrue(self.validate_data("docker-01", data))
        template_dict = prepare_jinja_template("docker-01", data, raw=False)
        self.assertEqual(
            {"docker": None}, template_dict["actions"]["deploy"]["methods"]
        )
        self.assertEqual(
            {
                "docker": {
                    "options": {"cpus": 0.0, "memory": 0, "devices": [], "volumes": []}
                }
            },
            template_dict["actions"]["boot"]["methods"],
        )

        data = """{% extends 'docker.jinja2' %}
{% set docker_cpus=2.1 %}
{% set docker_memory="120M" %}
{% set docker_volumes=["/home", "/tmp"] %}"""
        self.assertTrue(self.validate_data("docker-01", data))
        template_dict = prepare_jinja_template("docker-01", data, raw=False)
        self.assertEqual(
            {"docker": None}, template_dict["actions"]["deploy"]["methods"]
        )
        self.assertEqual(
            {
                "docker": {
                    "options": {
                        "cpus": 2.1,
                        "memory": "120M",
                        "devices": [],
                        "volumes": ["/home", "/tmp"],  # nosec - unit test support.
                    }
                }
            },
            template_dict["actions"]["boot"]["methods"],
        )

        data = """{% extends 'docker.jinja2' %}
{% set docker_cpus=2.1 %}
{% set docker_memory="120M" %}
{% set docker_devices=["/dev/kvm"] %}"""
        self.assertTrue(self.validate_data("docker-01", data))
        template_dict = prepare_jinja_template("docker-01", data, raw=False)
        self.assertEqual(
            {"docker": None}, template_dict["actions"]["deploy"]["methods"]
        )
        self.assertEqual(
            {
                "docker": {
                    "options": {
                        "cpus": 2.1,
                        "memory": "120M",
                        "devices": ["/dev/kvm"],
                        "volumes": [],
                    }
                }
            },
            template_dict["actions"]["boot"]["methods"],
        )

    def test_qemu_misc(self):
        job_ctx = {"arch": "microblaze"}
        template_dict = self.render_device_dictionary_file(
            "qemu01.jinja2", job_ctx, raw=False
        )
        self.assertIsNotNone(template_dict)
        self.assertEqual(
            set(
                [
                    "arm64",
                    "arm",
                    "aarch64",
                    "amd64",
                    "x86_64",
                    "i386",
                    "alpha",
                    "cris",
                    "lm32",
                    "m68k",
                    "microblaze",
                    "microblazeel",
                    "mips",
                    "mipsel",
                    "mips64",
                    "moxie",
                    "or32",
                    "ppc",
                    "ppc64",
                    "s390x",
                    "sh4",
                    "sh4eb",
                    "sparc",
                    "sparc64",
                    "tricore",
                    "unicore32",
                    "xtensa",
                    "xtensaeb",
                ]
            ),
            set(template_dict["available_architectures"]),
        )
        params = template_dict["actions"]["boot"]["methods"]["qemu"]["parameters"]
        self.assertIsNotNone(params["command"])
        self.assertEqual(params["command"], "qemu-system-" + job_ctx["arch"])
