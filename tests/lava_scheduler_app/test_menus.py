import os

from lava_common.yaml import yaml_safe_load
from tests.lava_scheduler_app.test_pipeline import YamlFactory
from tests.lava_scheduler_app.test_submission import TestCaseWithFactory


class YamlMenuFactory(YamlFactory):
    def make_fake_mustang_device(self, hostname="fakemustang1"):
        assert hostname == "fakemustang1"  # nosec - unit test support

    def make_job_data(self, actions=None, **kw):
        sample_job_file = os.path.join(
            os.path.dirname(__file__), "sample_jobs", "mustang-menu-ramdisk.yaml"
        )
        with open(sample_job_file) as test_support:
            data = yaml_safe_load(test_support)
        data.update(kw)
        return data


class TestPipelineMenu(TestCaseWithFactory):
    """
    Test the building and override support of pipeline menus from submission YAML
    """

    def setUp(self):
        super().setUp()
        self.factory = YamlMenuFactory()
        self.device_type = self.factory.make_device_type(name="mustang-uefi")

    def test_make_job_yaml(self):
        data = yaml_safe_load(self.factory.make_job_yaml())
        self.assertIn("device_type", data)
        self.assertNotIn("timeout", data)
        self.assertIn("timeouts", data)
        self.assertIn("job", data["timeouts"])
        self.assertIn("priority", data)

    def test_menu_device(self):
        job_ctx = {}
        hostname = "fakemustang2"
        device = self.factory.make_device(self.device_type, hostname)
        self.assertEqual(device.device_type.name, "mustang-uefi")

        config = device.load_configuration()
        self.assertIsNotNone(config)
        self.assertIsNotNone(config["actions"]["boot"]["methods"]["uefi-menu"]["nfs"])
        menu_data = config["actions"]["boot"]["methods"]["uefi-menu"]["nfs"]
        tftp_menu = [
            item
            for item in menu_data
            if "items" in item["select"] and "TFTP" in item["select"]["items"][0]
        ][0]
        tftp_mac = "52:54:00:12:34:59"
        # value from device dictionary correctly replaces device type default
        self.assertIn(tftp_mac, tftp_menu["select"]["items"][0])

    def test_menu_context(self):
        job_ctx = {
            "menu_early_printk": "",
            "menu_interrupt_prompt": "The default boot selection will start in",
            "base_ip_args": "ip=dhcp",
        }
        hostname = "fakemustang2"
        device = self.factory.make_device(self.device_type, hostname)
        config = device.load_configuration(job_ctx)
        self.assertIsNotNone(config)
        self.assertIsNotNone(config["actions"]["boot"]["methods"]["uefi-menu"]["nfs"])
        menu_data = config["actions"]["boot"]["methods"]["uefi-menu"]
        # assert that menu_interrupt_prompt replaces the default 'The default boot selection will start in'
        self.assertEqual(
            menu_data["parameters"]["interrupt_prompt"],
            job_ctx["menu_interrupt_prompt"],
        )
        # assert that menu_early_printk replaces the default earlyprintk default
        self.assertEqual(
            [
                e
                for e in menu_data["nfs"]
                if "enter" in e["select"] and "new Entry" in e["select"]["wait"]
            ][0]["select"]["enter"],
            "console=ttyS0,115200  debug root=/dev/nfs rw nfsroot={NFS_SERVER_IP}:{NFSROOTFS},tcp,hard ip=dhcp",
        )
