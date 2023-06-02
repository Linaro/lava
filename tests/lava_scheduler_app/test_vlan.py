import os
import tempfile

from lava_common.yaml import yaml_safe_dump, yaml_safe_load
from lava_dispatcher.device import NewDevice
from lava_dispatcher.parser import JobParser
from lava_dispatcher.protocols.multinode import MultinodeProtocol
from lava_dispatcher.protocols.vland import VlandProtocol
from lava_scheduler_app.dbutils import match_vlan_interface
from lava_scheduler_app.models import Tag, TestJob
from lava_scheduler_app.utils import split_multinode_yaml
from tests.lava_scheduler_app.test_base_templates import prepare_jinja_template
from tests.lava_scheduler_app.test_pipeline import YamlFactory
from tests.lava_scheduler_app.test_submission import TestCaseWithFactory

# pylint does not like TestCaseWithFactory


class VlandFactory(YamlFactory):
    def __init__(self):
        super().__init__()
        self.bbb1 = None
        self.cubie1 = None
        self.bbb_type = None

    def setUp(self):
        self.bbb_type = self.make_device_type(name="bbb")
        self.cubie_type = self.make_device_type(name="cubietruck")
        self.bbb1 = self.make_device(self.bbb_type, hostname="bbb-01")
        self.cubie1 = self.make_device(self.cubie_type, hostname="cubie1")

    def make_vland_job(self, **kw):
        sample_job_file = os.path.join(
            os.path.dirname(__file__), "sample_jobs", "bbb-cubie-vlan-group.yaml"
        )
        with open(sample_job_file) as test_support:
            data = yaml_safe_load(test_support)
        data.update(kw)
        return data


class TestVlandSplit(TestCaseWithFactory):
    """
    Test the splitting of lava-vland data from submission YAML
    Same tests as test_submission but converted to use and look for YAML.
    """

    def setUp(self):
        super().setUp()
        self.factory = VlandFactory()

    def test_split_vland(self):
        target_group = "unit-test-only"
        job_dict = split_multinode_yaml(self.factory.make_vland_job(), target_group)
        self.assertEqual(len(job_dict), 2)
        roles = job_dict.keys()
        self.assertEqual({"server", "client"}, set(roles))
        for role in roles:
            self.assertEqual(len(job_dict[role]), 1)  # count = 1
        client_job = job_dict["client"][0]
        server_job = job_dict["server"][0]
        self.assertIn("lava-multinode", client_job["protocols"])
        self.assertIn("lava-multinode", server_job["protocols"])
        self.assertIn("lava-vland", client_job["protocols"])
        self.assertIn("lava-vland", server_job["protocols"])
        client_vlan = client_job["protocols"]["lava-vland"]
        server_vlan = server_job["protocols"]["lava-vland"]
        self.assertIn("vlan_one", client_vlan)
        self.assertIn("vlan_two", server_vlan)
        self.assertEqual(["RJ45", "10M"], list(client_vlan.values())[0]["tags"])
        self.assertEqual(["RJ45", "100M"], list(server_vlan.values())[0]["tags"])


class TestVlandDevices(TestCaseWithFactory):
    """
    Test the matching of vland device requirements with submission YAML
    """

    def setUp(self):
        super().setUp()
        self.factory = VlandFactory()
        self.factory.setUp()

    def test_match_devices_without_map(self):
        """
        Without a map, there is no support for knowing which interfaces to
        put onto a VLAN, so these devices cannot be assigned to a VLAN testjob
        See http://localhost/static/docs/v2/vland.html#vland-and-interface-tags-in-lava
        """
        self.bbb3 = self.factory.make_device(self.factory.bbb_type, hostname="bbb-03")
        self.cubie2 = self.factory.make_device(
            self.factory.cubie_type, hostname="cubie2"
        )
        devices = [self.bbb3, self.cubie2]
        self.factory.ensure_tag("usb-eth")
        self.factory.ensure_tag("sata")
        self.factory.bbb1.tags.set(Tag.objects.filter(name="usb-eth"))
        self.factory.cubie1.tags.set(Tag.objects.filter(name="sata"))
        user = self.factory.make_user()
        sample_job_file = os.path.join(
            os.path.dirname(__file__), "sample_jobs", "bbb-cubie-vlan-group.yaml"
        )
        with open(sample_job_file) as test_support:
            data = yaml_safe_load(test_support)
        vlan_job = TestJob.from_yaml_and_user(yaml_safe_dump(data), user)
        assignments = {}
        for job in vlan_job:
            self.assertFalse(
                match_vlan_interface(self.bbb3, yaml_safe_load(job.definition))
            )
            self.assertFalse(
                match_vlan_interface(self.cubie2, yaml_safe_load(job.definition))
            )

    def test_jinja_template(self):
        yaml_data = self.factory.bbb1.load_configuration()
        self.assertIn("parameters", yaml_data)
        self.assertIn("interfaces", yaml_data["parameters"])
        self.assertIn("bootm", yaml_data["parameters"])
        self.assertIn("bootz", yaml_data["parameters"])
        self.assertIn("actions", yaml_data)
        self.assertIn("eth0", yaml_data["parameters"]["interfaces"])
        self.assertIn("eth1", yaml_data["parameters"]["interfaces"])
        self.assertIn("sysfs", yaml_data["parameters"]["interfaces"]["eth0"])
        self.assertEqual(
            "/sys/devices/pci0000:00/0000:00:1c.1/0000:03:00.0/net/eth1",
            yaml_data["parameters"]["interfaces"]["eth1"]["sysfs"],
        )


class TestVlandProtocolSplit(TestCaseWithFactory):
    """
    Test the handling of protocols in dispatcher after splitting the YAML
    """

    def setUp(self):
        super().setUp()
        self.factory = VlandFactory()
        self.factory.setUp()

    def test_job_protocols(self):
        self.factory.ensure_tag("usb-eth")
        self.factory.ensure_tag("sata")
        self.factory.bbb1.tags.set(Tag.objects.filter(name="usb-eth"))
        self.factory.cubie1.tags.set(Tag.objects.filter(name="sata"))
        target_group = "unit-test-only"
        job_dict = split_multinode_yaml(self.factory.make_vland_job(), target_group)
        client_job = job_dict["client"][0]
        client_handle, client_file_name = tempfile.mkstemp()
        with open(client_file_name, "w") as f:
            yaml_safe_dump(client_job, f)
        # YAML device file, as required by lava-dispatch --target
        data = "{% extends 'beaglebone-black.jinja2' %}"
        device_yaml_file = prepare_jinja_template("bbb-01", data, raw=False)
        parser = JobParser()
        bbb_device = NewDevice(device_yaml_file)
        with open(client_file_name) as sample_job_data:
            bbb_job = parser.parse(sample_job_data, bbb_device, 4212, None, "")
        os.close(client_handle)
        os.unlink(client_file_name)
        self.assertIn("protocols", bbb_job.parameters)
        self.assertIn(VlandProtocol.name, bbb_job.parameters["protocols"])
        self.assertIn(MultinodeProtocol.name, bbb_job.parameters["protocols"])
