import os
import unittest
from unittest import TestCase
from unittest.mock import patch

import yaml
from django.conf import settings
from django.contrib.auth.models import User
from jinja2 import TemplateError as JinjaTemplateError

from lava_common.constants import SYS_CLASS_KVM
from lava_common.exceptions import InfrastructureError, JobError
from lava_common.yaml import yaml_safe_dump, yaml_safe_load
from lava_dispatcher.actions.boot.qemu import BootQEMU
from lava_dispatcher.device import PipelineDevice
from lava_dispatcher.parser import JobParser
from lava_dispatcher.protocols.multinode import MultinodeProtocol
from lava_scheduler_app.dbutils import match_vlan_interface
from lava_scheduler_app.models import (
    Device,
    DevicesUnavailableException,
    DeviceType,
    Tag,
    TestJob,
    _pipeline_protocols,
)
from lava_scheduler_app.schema import (
    SubmissionException,
    validate_device,
    validate_submission,
)
from lava_scheduler_app.utils import split_multinode_yaml
from tests.lava_dispatcher.test_defs import check_missing_path
from tests.lava_scheduler_app.test_submission import ModelFactory, TestCaseWithFactory
from tests.utils import DummyLogger

# set to True to see extra processing details
DEBUG = False


class YamlFactory(ModelFactory):
    """
    Override some factory functions to supply YAML instead of JSON
    The YAML **must** be valid for the current pipeline to be able to
    save a TestJob into the database. Hence qemu.yaml.
    """

    def make_device_type(self, name="qemu"):
        device_type = DeviceType.objects.get_or_create(name=name)[0]
        device_type.save()
        return device_type

    def make_device(self, device_type=None, hostname=None, tags=None, **kw):
        if device_type is None:
            device_type = self.ensure_device_type()
        if hostname is None:
            hostname = self.getUniqueString()
        if tags and not isinstance(tags, list):
            tags = []
        device = Device(device_type=device_type, hostname=hostname, **kw)
        if tags:
            device.tags.set(tags)
        if DEBUG:
            print(
                "making a device of type %s %s with tags '%s'",
                device_type,
                device.hostname,
                ", ".join([x.name for x in device.tags.all()]),
            )
        device.save()
        return device

    def make_job_data(self, actions=None, **kw):
        sample_job_file = os.path.join(
            os.path.dirname(__file__), "sample_jobs", "qemu.yaml"
        )
        with open(sample_job_file) as test_support:
            data = yaml_safe_load(test_support)
        data.update(kw)
        return data

    def make_job_yaml(self, **kw):
        return yaml_safe_dump(self.make_job_data(**kw))


class PipelineDeviceTags(TestCaseWithFactory):
    """
    Test the extraction of device tags from submission YAML
    Same tests as test_submission but converted to use and look for YAML.
    """

    def setUp(self):
        super().setUp()
        self.factory = YamlFactory()
        self.device_type = self.factory.make_device_type()
        self.conf = {
            "arch": "amd64",
            "extends": "qemu.jinja2",
            "mac_addr": "52:54:00:12:34:59",
            "memory": "256",
        }

    def test_make_job_yaml(self):
        data = yaml_safe_load(self.factory.make_job_yaml())
        self.assertIn("device_type", data)
        self.assertNotIn("timeout", data)
        self.assertIn("timeouts", data)
        self.assertIn("job", data["timeouts"])
        self.assertIn("context", data)
        self.assertIn("priority", data)
        self.assertEqual(data["context"]["arch"], self.conf["arch"])

    def test_make_device(self):
        hostname = "fakeqemu3"
        device = self.factory.make_device(self.device_type, hostname)
        self.assertEqual(device.device_type.name, "qemu")
        job = self.factory.make_job_yaml()
        self.assertIsNotNone(job)

    def test_no_tags(self):
        self.factory.make_device(self.device_type, "fakeqemu3")
        user = self.factory.make_user()
        TestJob.from_yaml_and_user(self.factory.make_job_yaml(), user)

    def test_priority(self):
        self.factory.make_device(self.device_type, "fakeqemu3")
        user = self.factory.make_user()
        job = TestJob.from_yaml_and_user(self.factory.make_job_yaml(), user)
        self.assertEqual(TestJob.LOW, job.priority)

    def test_yaml_device_tags(self):
        Tag.objects.all().delete()
        tag_list = [self.factory.ensure_tag("usb"), self.factory.ensure_tag("sata")]
        data = yaml_safe_load(self.factory.make_job_yaml(tags=["usb", "sata"]))
        validate_submission(data)
        device = self.factory.make_device(self.device_type, "fakeqemu4", tags=tag_list)
        job_ctx = data.get("context", {})
        device_config = device.load_configuration(job_ctx)  # raw dict
        validate_device(device_config)
        self.assertTrue(device.is_valid())
        self.assertIn("tags", data)
        self.assertEqual(type(data["tags"]), list)
        self.assertIn("usb", data["tags"])
        self.assertEqual(set(Tag.objects.all()), set(device.tags.all()))

    def test_undefined_tags(self):
        Tag.objects.all().delete()
        self.factory.make_device(self.device_type, "fakeqemu1")
        user = self.factory.make_user()
        self.assertRaises(
            yaml.YAMLError,
            TestJob.from_yaml_and_user,
            self.factory.make_job_yaml(tags=["tag1", "tag2"]),
            user,
        )

    def test_from_yaml_unsupported_tags(self):
        self.factory.make_device(self.device_type, "fakeqemu1")
        self.factory.ensure_tag("usb")
        self.factory.ensure_tag("sata")
        user = self.factory.make_user()
        try:
            TestJob.from_yaml_and_user(
                self.factory.make_job_yaml(tags=["usb", "sata"]), user
            )
        except DevicesUnavailableException:
            pass
        else:
            self.fail(
                "Device tags failure: job submitted without any devices supporting the requested tags"
            )

    def test_from_yaml_and_user_sets_multiple_tag_from_device_tags(self):
        tag_list = [self.factory.ensure_tag("tag1"), self.factory.ensure_tag("tag2")]
        self.factory.make_device(self.device_type, hostname="fakeqemu1", tags=tag_list)
        user = self.factory.make_user()
        job = TestJob.from_yaml_and_user(
            self.factory.make_job_yaml(tags=["tag1", "tag2"]), user
        )
        self.assertEqual({tag.name for tag in job.tags.all()}, {"tag1", "tag2"})

    def test_from_yaml_and_user_reuses_tag_objects(self):
        self.factory.ensure_tag("tag")
        tags = list(Tag.objects.filter(name="tag"))
        self.factory.make_device(
            device_type=self.device_type, hostname="fakeqemu1", tags=tags
        )
        user = self.factory.make_user()
        job1 = TestJob.from_yaml_and_user(
            self.factory.make_job_yaml(tags=["tag"]), user
        )
        job2 = TestJob.from_yaml_and_user(
            self.factory.make_job_yaml(tags=["tag"]), user
        )
        self.assertEqual(
            {tag.pk for tag in job1.tags.all()},
            {tag.pk for tag in job2.tags.all()},
        )

    def test_from_yaml_and_user_matches_available_tags(self):
        """
        Test that with more than one device of the requested type supporting
        tags, that the tag list set for the TestJob matches the list requested,
        not a shorter list from a different device or a combined list of multiple
        devices.
        """
        tag_list = [
            self.factory.ensure_tag("common_tag1"),
            self.factory.ensure_tag("common_tag2"),
        ]
        self.factory.make_device(
            device_type=self.device_type, hostname="fakeqemu1", tags=tag_list
        )
        tag_list.append(self.factory.ensure_tag("unique_tag"))
        self.factory.make_device(
            device_type=self.device_type, hostname="fakeqemu2", tags=tag_list
        )
        user = self.factory.make_user()
        job = TestJob.from_yaml_and_user(
            self.factory.make_job_yaml(
                tags=["common_tag1", "common_tag2", "unique_tag"]
            ),
            user,
        )
        self.assertEqual({tag for tag in job.tags.all()}, set(tag_list))


class TestPipelineSubmit(TestCaseWithFactory):
    def setUp(self):
        super().setUp()
        self.factory = YamlFactory()
        self.device_type = self.factory.make_device_type()
        self.factory.make_device(device_type=self.device_type, hostname="fakeqemu1")
        self.factory.make_device(device_type=self.device_type, hostname="fakeqemu3")

    def test_from_yaml_and_user_sets_definition(self):
        definition = self.factory.make_job_yaml()
        user = self.factory.make_user()
        job = TestJob.from_yaml_and_user(definition, user)
        self.assertEqual(definition, job.definition)

    def test_from_yaml_and_user_sets_submitter(self):
        user = self.factory.make_user()
        job = TestJob.from_yaml_and_user(self.factory.make_job_yaml(), user)
        self.assertEqual(user, job.submitter)
        self.assertFalse(job.health_check)

    def test_context(self):
        """
        Test overrides using the job context

        Defaults in the device-type can be overridden by the device dictionary.
        If not overridden by the device dictionary, can be overridden by the job context.
        If the
        """
        device = Device.objects.get(hostname="fakeqemu1")
        user = self.factory.make_user()
        job = TestJob.from_yaml_and_user(self.factory.make_job_yaml(), user)
        job_def = yaml_safe_load(job.definition)
        job_ctx = job_def.get("context", {})
        device_config = device.load_configuration(job_ctx)  # raw dict
        self.assertTrue(device.is_valid())
        self.assertEqual(
            device_config["actions"]["boot"]["methods"]["qemu"]["parameters"][
                "command"
            ],
            "qemu-system-x86_64",
        )

        job_data = yaml_safe_load(self.factory.make_job_yaml())
        job_data["context"].update({"netdevice": "tap"})
        job_ctx = job_data.get("context", {})
        device_config = device.load_configuration(job_ctx)  # raw dict
        opts = " ".join(
            device_config["actions"]["boot"]["methods"]["qemu"]["parameters"]["options"]
        )
        self.assertIn("-net tap", opts)

        hostname = "fakemustang1"
        mustang_type = self.factory.make_device_type("mustang-uefi")
        # this sets a qemu device dictionary, so replace it
        self.factory.make_device(device_type=mustang_type, hostname=hostname)
        device = Device.objects.get(hostname="fakemustang1")
        self.assertEqual("mustang-uefi", device.device_type.name)
        job_ctx = {
            "tftp_mac": "FF:01:00:69:AA:CC",
            "extra_nfsroot_args": ",nolock",
            "console_device": "ttyAMX0",
            "base_ip_args": "ip=dhcp",
        }
        device_config = device.load_configuration(job_ctx)  # raw dict
        self.assertTrue(device.is_valid())
        self.assertIn("uefi-menu", device_config["actions"]["boot"]["methods"])
        self.assertIn("nfs", device_config["actions"]["boot"]["methods"]["uefi-menu"])
        menu_data = device_config["actions"]["boot"]["methods"]["uefi-menu"]["nfs"]
        self.assertIn(
            job_ctx["extra_nfsroot_args"],
            [
                item["select"]["enter"]
                for item in menu_data
                if "enter" in item["select"] and "new Entry" in item["select"]["wait"]
            ][0],
        )
        self.assertEqual(
            [
                item["select"]["items"][0]
                for item in menu_data
                if "select" in item
                and "items" in item["select"]
                and "TFTP" in item["select"]["items"][0]
            ][0],
            "TFTP on MAC Address: FF:01:00:69:AA:CC",  # matches the job_ctx
        )
        # note: the console_device and tftp_mac in the job_ctx has been *ignored* because the device type template
        # has not allowed the job_ctx to use a different name for the variable and the variable is
        # already defined in the device dictionary using the specified name. If the device dictionary lacked
        # the variable, the job could set it to override the device type template default, as shown by the
        # override of the extra_nfsroot_args by allowing nfsroot_args in the device type template..
        self.assertEqual(
            [
                item["select"]["enter"]
                for item in menu_data
                if "select" in item
                and "wait" in item["select"]
                and "Description" in item["select"]["wait"]
            ][0],
            "console=ttyO0,115200 earlyprintk=uart8250-32bit,0x1c020000 debug "
            "root=/dev/nfs rw nfsroot={NFS_SERVER_IP}:{NFSROOTFS},tcp,hard,nolock ip=dhcp",
        )

    def test_metadata(self):
        data = yaml_safe_load(self.factory.make_job_yaml(metadata={15: "test"}))
        validate_submission(data)
        metadata = {
            "build-url": None,
            "build-log": "/consoleText",
            "zephyr-gcc-variant": None,
            "platform": "frdm_k64f",
            "git-url": "https://git.linaro.org/zephyrproject-org/zephyr.git",
            "git-commit": 1234,
            "api_config": {
                "name": "staging.kernelci.org",
                "url": "https://staging.kernelci.org:9000",
                "version": "latest",
            },
            123: ["One", "upon", "a", "time"],
            None: "Invalid",
        }
        data = yaml_safe_load(self.factory.make_job_yaml(metadata=metadata))
        self.assertRaises(SubmissionException, validate_submission, data)
        del metadata[None]
        data = yaml_safe_load(self.factory.make_job_yaml(metadata=metadata))
        validate_submission(data)

    def test_command_list(self):
        hostname = "bbb-02"
        dt = self.factory.make_device_type(name="beaglebone-black")
        device = self.factory.make_device(device_type=dt, hostname=hostname)
        device_dict = device.load_configuration()
        self.assertIsInstance(device_dict["commands"]["hard_reset"], list)
        self.assertTrue(device.is_valid())

    def test_minimal_config(self):
        hostname = "bbb-02"
        dt = self.factory.make_device_type(name="beaglebone-black")
        device = self.factory.make_device(device_type=dt, hostname=hostname)
        device_dict = device.load_configuration()
        self.assertIsNotNone(device_dict)
        self.assertTrue(device.is_valid())
        self.assertIn("commands", device_dict)
        self.assertIn("parameters", device_dict)
        self.assertIn("timeouts", device_dict)
        self.assertIn("actions", device_dict)
        self.assertIn("deploy", device_dict["actions"])
        self.assertIn("boot", device_dict["actions"])
        self.assertIn("connections", device_dict["actions"]["deploy"])
        self.assertIn("connections", device_dict["actions"]["boot"])
        self.assertIn("methods", device_dict["actions"]["deploy"])
        self.assertIn("methods", device_dict["actions"]["boot"])
        device_dict = device.minimise_configuration(device_dict)
        self.assertIsNotNone(device_dict)
        self.assertNotIn("commands", device_dict)
        self.assertNotIn("parameters", device_dict)
        self.assertIn("actions", device_dict)
        self.assertIn("deploy", device_dict["actions"])
        self.assertIn("connections", device_dict["actions"]["deploy"])
        self.assertIn("methods", device_dict["actions"]["deploy"])
        self.assertIn("boot", device_dict["actions"])
        self.assertIn("connections", device_dict["actions"]["boot"])
        self.assertIn("methods", device_dict["actions"]["boot"])
        self.assertIn("timeouts", device_dict)

    def test_auto_login(self):
        data = yaml_safe_load(self.factory.make_job_yaml())
        validate_submission(data)

        boot_params = None
        for name, params in (
            (x, d[x]) for x, d in ((list(d.keys())[0], d) for d in data["actions"])
        ):
            if name == "boot":
                boot_params = params
                break
        self.assertIsNotNone(boot_params)

        auto_login = {}
        boot_params["auto_login"] = auto_login
        self.assertRaises(SubmissionException, validate_submission, data)
        auto_login["login_prompt"] = "login:"
        self.assertRaises(SubmissionException, validate_submission, data)
        auto_login.update(
            {"username": "bob", "password_prompt": "Password:", "password": "hello"}
        )
        validate_submission(data)
        auto_login["login_commands"] = True
        self.assertRaises(SubmissionException, validate_submission, data)
        auto_login["login_commands"] = ["whoami", "sudo su"]
        validate_submission(data)

    # FIXME: extend once the master validation code is exposed for unit tests
    def test_compatibility(self):
        user = self.factory.make_user()
        # public set in the YAML
        yaml_str = self.factory.make_job_yaml()
        yaml_data = yaml_safe_load(yaml_str)
        job = TestJob.from_yaml_and_user(yaml_str, user)
        self.assertTrue(job.can_view(user))
        # initial state prior to validation
        self.assertEqual(job.pipeline_compatibility, 0)
        self.assertNotIn("compatibility", yaml_data)
        # FIXME: dispatcher master needs to make this kind of test more accessible.
        definition = yaml_safe_load(job.definition)
        self.assertNotIn("protocols", definition)
        job.actual_device = Device.objects.get(hostname="fakeqemu1")
        job_def = yaml_safe_load(job.definition)
        job_ctx = job_def.get("context", {})
        parser = JobParser()
        device = job.actual_device

        try:
            device_config = device.load_configuration(job_ctx)  # raw dict
        except (JinjaTemplateError, yaml.YAMLError, OSError) as exc:
            # FIXME: report the exceptions as useful user messages
            self.fail("[%s] jinja2 error: %s" % (job.id, exc))
        if not device_config or not isinstance(device_config, dict):
            # it is an error to have a pipeline device without a device dictionary as it will never get any jobs.
            msg = (
                "Administrative error. Device '%s' has no device dictionary."
                % device.hostname
            )
            self.fail("[%s] device-dictionary error: %s" % (job.id, msg))

        self.assertTrue(device.is_valid())
        device_object = PipelineDevice(
            device_config
        )  # equivalent of the NewDevice in lava-dispatcher, without .yaml file.
        # FIXME: drop this nasty hack once 'target' is dropped as a parameter
        if "target" not in device_object:
            device_object.target = device.hostname
        device_object["hostname"] = device.hostname

        parser_device = device_object
        try:
            pipeline_job = parser.parse(job.definition, parser_device, job.id, None, "")
        except (
            AttributeError,
            JobError,
            NotImplementedError,
            KeyError,
            TypeError,
        ) as exc:
            self.fail("[%s] parser error: %s" % (job.sub_id, exc))
        description = pipeline_job.describe()
        self.assertIn("compatibility", description)
        self.assertGreaterEqual(description["compatibility"], BootQEMU.compatibility)

    def reset_job_device(
        self,
        job,
        device,
        job_state=TestJob.STATE_RUNNING,
        device_state=Device.STATE_RUNNING,
    ):
        device.current_job = job
        job.state = job_state
        device.state = device_state
        job.save()
        device.save()


class TestExtendsSubmit(TestCaseWithFactory):
    def setUp(self):
        super().setUp()
        self.factory = YamlFactory()
        self.device_type = self.factory.make_device_type(name="juno-r2")
        self.factory.make_device(
            device_type=self.device_type, hostname="juno-r2-uboot-01"
        )
        self.factory.make_device(device_type=self.device_type, hostname="juno-r2-01")

    def test_health_checks_extends(self):
        device1 = Device.objects.get(hostname="juno-r2-01")
        self.assertIsNotNone(device1.load_configuration(output_format="raw"))
        self.assertEqual("juno", device1.get_extends())
        self.assertTrue(
            os.path.exists(
                os.path.join(
                    settings.HEALTH_CHECKS_PATH, "%s.yaml" % device1.get_extends()
                )
            )
        )
        self.assertIsNotNone(device1.get_health_check())


class TestYamlMultinode(TestCaseWithFactory):
    def setUp(self):
        super().setUp()
        self.factory = YamlFactory()

    def tearDown(self):
        super().tearDown()
        Device.objects.all().delete()

    def test_multinode_split(self):
        """
        Test just the split of pipeline YAML

        This function does not test the content of 'roles' as this needs information
        which is only available after the devices have been reserved.
        """
        server_check = os.path.join(
            os.path.dirname(__file__), "sample_jobs", "kvm-multinode-server.yaml"
        )
        client_check = os.path.join(
            os.path.dirname(__file__), "sample_jobs", "kvm-multinode-client.yaml"
        )
        with open(
            os.path.join(
                os.path.dirname(__file__), "sample_jobs", "kvm-multinode.yaml"
            ),
        ) as f:
            submission = yaml_safe_load(f)
        target_group = "arbitrary-group-id"  # for unit tests only

        jobs = split_multinode_yaml(submission, target_group)
        self.assertEqual(len(jobs), 2)
        for role, job_list in jobs.items():
            for job in job_list:
                del job["protocols"]["lava-multinode"]["sub_id"]
                yaml_safe_dump(job)  # ensure the jobs can be serialised as YAML
                if role == "client":
                    with open(client_check) as f:
                        self.assertEqual(job, yaml_safe_load(f))
                if role == "server":
                    with open(server_check) as f:
                        self.assertEqual(job, yaml_safe_load(f))

    def test_secondary_connection(self):
        user = self.factory.make_user()
        device_type = self.factory.make_device_type(name="mustang")
        device = self.factory.make_device(device_type, "mustang1")
        with open(
            os.path.join(
                os.path.dirname(__file__),
                "sample_jobs",
                "mustang-ssh-multinode.yaml",
            ),
        ) as f:
            submission = yaml_safe_load(f)
        target_group = "arbitrary-group-id"  # for unit tests only
        jobs_dict = split_multinode_yaml(submission, target_group)
        self.assertIsNotNone(jobs_dict)
        jobs = TestJob.from_yaml_and_user(yaml_safe_dump(submission), user)
        self.assertIsNotNone(jobs)
        host_job = None
        guest_job = None
        for job in jobs:
            if job.device_role == "host":
                host_job = job
            if job.device_role == "guest":
                guest_job = job
        self.assertIsNotNone(host_job)
        self.assertIsNotNone(guest_job)
        self.assertTrue(guest_job.dynamic_connection)
        parser = JobParser()
        job_ctx = {}
        host_job.actual_device = device

        try:
            device_config = device.load_configuration(job_ctx)  # raw dict
        except (JinjaTemplateError, yaml.YAMLError, OSError) as exc:
            # FIXME: report the exceptions as useful user messages
            self.fail("[%d] jinja2 error: %s" % (host_job.id, exc))
        if not device_config or not isinstance(device_config, dict):
            # it is an error to have a pipeline device without a device dictionary as it will never get any jobs.
            msg = (
                "Administrative error. Device '%s' has no device dictionary."
                % device.hostname
            )
            self.fail("[%d] device-dictionary error: %s" % (host_job.id, msg))

        self.assertTrue(device.is_valid())
        device_object = PipelineDevice(
            device_config
        )  # equivalent of the NewDevice in lava-dispatcher, without .yaml file.
        # FIXME: drop this nasty hack once 'target' is dropped as a parameter
        if "target" not in device_object:
            device_object.target = device.hostname
        device_object["hostname"] = device.hostname
        self.assertIsNotNone(device_object)
        parser_device = device_object
        try:
            pipeline_job = parser.parse(
                host_job.definition, parser_device, host_job.id, DummyLogger(), ""
            )
        except (
            AttributeError,
            JobError,
            NotImplementedError,
            KeyError,
            TypeError,
        ) as exc:
            self.fail("[%s] parser error: %s" % (host_job.sub_id, exc))
        pipeline_job._validate()
        self.assertEqual([], pipeline_job.pipeline.errors)

        try:
            pipeline_job = parser.parse(
                guest_job.definition, parser_device, guest_job.id, DummyLogger(), ""
            )
        except (
            AttributeError,
            JobError,
            NotImplementedError,
            KeyError,
            TypeError,
        ) as exc:
            self.fail("[%s] parser error: %s" % (guest_job.sub_id, exc))
        pipeline_job._validate()
        self.assertEqual([], pipeline_job.pipeline.errors)

    def test_multinode_tags(self):
        Tag.objects.all().delete()
        self.factory.ensure_tag("tap"),
        self.factory.ensure_tag("virtio")
        with open(
            os.path.join(
                os.path.dirname(__file__), "sample_jobs", "kvm-multinode.yaml"
            ),
        ) as f:
            submission = yaml_safe_load(f)
        roles_dict = submission["protocols"][MultinodeProtocol.name]["roles"]
        roles_dict["client"]["tags"] = ["tap"]
        roles_dict["server"]["tags"] = ["virtio"]
        submission["protocols"][MultinodeProtocol.name]["roles"] = roles_dict
        target_group = "arbitrary-group-id"  # for unit tests only
        jobs = split_multinode_yaml(submission, target_group)
        self.assertEqual(len(jobs), 2)
        for role, job_list in jobs.items():
            for job in job_list:
                if role == "server":
                    self.assertEqual(
                        job["protocols"]["lava-multinode"]["tags"], ["virtio"]
                    )
                elif role == "client":
                    self.assertEqual(
                        job["protocols"]["lava-multinode"]["tags"], ["tap"]
                    )
                else:
                    self.fail("unexpected role")

    def test_multinode_tags_count(self):
        user = self.factory.make_user()
        device_type = self.factory.make_device_type("qemu")
        client_tags = [self.factory.ensure_tag("client")]
        self.factory.make_device(device_type, "fakeqemu1", tags=client_tags)
        self.factory.make_device(device_type, "fakeqemu2")
        bbb_type = self.factory.make_device_type("beaglebone-black")
        server_tags = [self.factory.ensure_tag("server")]
        self.factory.make_device(
            hostname="bbb-01", device_type=bbb_type, tags=server_tags
        )
        self.factory.make_device(hostname="bbb-02", device_type=bbb_type)
        with open(
            os.path.join(
                os.path.dirname(__file__), "sample_jobs", "bbb-qemu-multinode.yaml"
            ),
        ) as f:
            submission = yaml_safe_load(f)

        # Request devices matching the below tags.
        roles_dict = submission["protocols"][MultinodeProtocol.name]["roles"]
        roles_dict["client"]["tags"] = ["client"]
        roles_dict["server"]["tags"] = ["server"]

        # 1. Test not enough devices available.
        with self.assertRaisesMessage(
            DevicesUnavailableException,
            "Not enough devices available matching the requested tags.",
        ):
            _pipeline_protocols(submission, user)

        # 2. Test enough devices available.
        self.factory.make_device(device_type, "fakeqemu3", tags=client_tags)
        self.factory.make_device(
            hostname="bbb-03", device_type=bbb_type, tags=server_tags
        )
        self.assertTrue(_pipeline_protocols(submission, user))

    def test_multinode_lxc(self):
        with open(
            os.path.join(
                os.path.dirname(__file__), "sample_jobs", "lxc-multinode.yaml"
            ),
        ) as f:
            submission = yaml_safe_load(f)
        target_group = "arbitrary-group-id"  # for unit tests only

        jobs = split_multinode_yaml(submission, target_group)
        protocol_data = {
            "lava-lxc": {
                "name": "pipeline-lxc-test",
                "template": "debian",
                "security_mirror": "http://mirror.csclub.uwaterloo.ca/debian-security/",
                "release": "sid",
                "distribution": "debian",
                "mirror": "http://ftp.us.debian.org/debian/",
            }
        }
        for role, _ in jobs.items():
            if role == "server":
                self.assertNotIn("lava-lxc", jobs[role][0]["protocols"])
            elif role == "client":
                self.assertIn("lava-lxc", jobs[role][0]["protocols"])
                self.assertEqual(
                    jobs[role][0]["protocols"]["lava-lxc"], protocol_data["lava-lxc"]
                )
            else:
                self.fail("Unrecognised role: %s" % role)

    def test_multinode_hikey(self):
        with open(
            os.path.join(
                os.path.dirname(__file__), "sample_jobs", "hikey_multinode.yaml"
            ),
        ) as f:
            submission = yaml_safe_load(f)
        target_group = "arbitrary-group-id"  # for unit tests only

        jobs = split_multinode_yaml(submission, target_group)
        client_protocol_data = {
            "lava-lxc": {
                "name": "pipeline-lxc-test",
                "template": "debian",
                "security_mirror": "http://mirror.csclub.uwaterloo.ca/debian-security/",
                "release": "sid",
                "distribution": "debian",
                "mirror": "http://ftp.us.debian.org/debian/",
            }
        }
        server_protocol_data = {
            "lava-lxc": {
                "distribution": "debian",
                "mirror": "http://mirror.bytemark.co.uk/debian",
                "name": "lxc-hikey-oe",
                "release": "jessie",
                "template": "debian",
            }
        }
        for role, _ in jobs.items():
            if role == "server":
                self.assertIn("lava-lxc", jobs[role][0]["protocols"])
                self.assertEqual(
                    jobs[role][0]["protocols"]["lava-lxc"],
                    server_protocol_data["lava-lxc"],
                )
            elif role == "client":
                self.assertIn("lava-lxc", jobs[role][0]["protocols"])
                self.assertEqual(
                    jobs[role][0]["protocols"]["lava-lxc"],
                    client_protocol_data["lava-lxc"],
                )
            else:
                self.fail("Unrecognised role: %s" % role)

    def test_multinode_nexus4(self):
        with open(
            os.path.join(
                os.path.dirname(__file__), "sample_jobs", "nexus4_multinode.yaml"
            ),
        ) as f:
            submission = yaml_safe_load(f)
        target_group = "arbitrary-group-id"  # for unit tests only

        jobs = split_multinode_yaml(submission, target_group)
        device_protocol_data = {
            "lava-lxc": {
                "name": "lxc-nexus4",
                "template": "debian",
                "release": "sid",
                "distribution": "debian",
            }
        }
        for role, _ in jobs.items():
            if role == "device":
                for job in jobs[role]:
                    self.assertIn("lava-lxc", job["protocols"])
                    self.assertEqual(
                        job["protocols"]["lava-lxc"], device_protocol_data["lava-lxc"]
                    )
                    self.assertIn("reboot_to_fastboot", job)
                    self.assertEqual(job["reboot_to_fastboot"], False)
            else:
                self.fail("Unrecognised role: %s" % role)

    def test_multinode_protocols(self):
        user = self.factory.make_user()
        device_type = self.factory.make_device_type()
        Device.objects.filter(device_type=device_type).delete()
        Tag.objects.all().delete()
        with open(
            os.path.join(
                os.path.dirname(__file__), "sample_jobs", "kvm-multinode.yaml"
            ),
        ) as f:
            submission = yaml_safe_load(f)
        # no devices defined for the specified type
        self.assertRaises(
            DevicesUnavailableException,
            _pipeline_protocols,
            submission,
            user,
            yaml_data=None,
        )

        self.factory.make_device(device_type, "fakeqemu1")
        # specified tags do not exist
        self.assertRaises(yaml.YAMLError, _pipeline_protocols, submission, user)

        client_tag_list = [
            self.factory.ensure_tag("usb-flash"),
            self.factory.ensure_tag("usb-eth"),
        ]
        server_tag_list = [self.factory.ensure_tag("testtag")]
        self.factory.make_device(device_type, "fakeqemu2", tags=server_tag_list)
        # no devices which have the required tags applied
        self.assertRaises(
            DevicesUnavailableException,
            _pipeline_protocols,
            submission,
            user,
            yaml_data=None,
        )

        self.factory.make_device(device_type, "fakeqemu3", tags=client_tag_list)
        job_object_list = _pipeline_protocols(submission, user)
        self.assertEqual(len(job_object_list), 2)
        for job in job_object_list:
            self.assertEqual(list(job.sub_jobs_list), job_object_list)
            check = yaml_safe_load(job.definition)
            if check["protocols"]["lava-multinode"]["role"] == "client":
                self.assertEqual(
                    check["protocols"]["lava-multinode"]["tags"],
                    ["usb-flash", "usb-eth"],
                )
                self.assertNotIn("interfaces", check["protocols"]["lava-multinode"])
                self.assertEqual(set(client_tag_list), set(job.tags.all()))
            if check["protocols"]["lava-multinode"]["role"] == "server":
                self.assertEqual(
                    check["protocols"]["lava-multinode"]["tags"], ["testtag"]
                )
                self.assertNotIn("interfaces", check["protocols"]["lava-multinode"])
                self.assertEqual(
                    {"testtag"}, set(job.tags.all().values_list("name", flat=True))
                )

    def test_multinode_group(self):
        user = self.factory.make_user()
        device_type = self.factory.make_device_type()
        with open(
            os.path.join(
                os.path.dirname(__file__), "sample_jobs", "kvm-multinode.yaml"
            ),
        ) as f:
            submission = yaml_safe_load(f)
        self.factory.make_device(device_type, "fakeqemu1")
        tag_list = [
            self.factory.ensure_tag("usb-flash"),
            self.factory.ensure_tag("usb-eth"),
            self.factory.ensure_tag("testtag"),
        ]
        self.factory.make_device(device_type, "fakeqemu2", tags=tag_list)
        job_object_list = _pipeline_protocols(
            submission, user, yaml_safe_dump(submission)
        )
        for job in job_object_list:
            self.assertEqual(list(job.sub_jobs_list), job_object_list)
        check_one = yaml_safe_load(job_object_list[0].definition)
        check_two = yaml_safe_load(job_object_list[1].definition)
        self.assertEqual(
            job_object_list[0].target_group, job_object_list[1].target_group
        )
        # job 0 needs to have a sub_id of <id>.0
        # job 1 needs to have a sub_id of <id>.1 despite job 1 id being <id>+1
        self.assertEqual(
            int(job_object_list[0].id), int(float(job_object_list[0].sub_id))
        )
        self.assertEqual(int(job_object_list[0].id) + 1, int(job_object_list[1].id))
        self.assertEqual(
            job_object_list[0].sub_id, "%d.%d" % (int(job_object_list[0].id), 0)
        )
        self.assertEqual(
            job_object_list[1].sub_id, "%d.%d" % (int(job_object_list[0].id), 1)
        )
        self.assertNotEqual(
            job_object_list[1].sub_id, "%d.%d" % (int(job_object_list[1].id), 0)
        )
        self.assertNotEqual(
            job_object_list[1].sub_id, "%d.%d" % (int(job_object_list[1].id), 1)
        )
        self.assertNotEqual(
            check_one["protocols"]["lava-multinode"]["role"],
            check_two["protocols"]["lava-multinode"]["role"],
        )

    def test_multinode_definition(self):
        user = self.factory.make_user()
        device_type = self.factory.make_device_type()
        with open(
            os.path.join(
                os.path.dirname(__file__), "sample_jobs", "kvm-multinode.yaml"
            ),
        ) as f:
            submission = yaml_safe_load(f)
        self.factory.make_device(device_type, "fakeqemu1")
        self.factory.make_device(device_type, "fakeqemu2")
        tag_list = [
            self.factory.ensure_tag("usb-flash"),
            self.factory.ensure_tag("usb-eth"),
            self.factory.ensure_tag("testtag"),
        ]
        self.factory.make_device(device_type, "fakeqemu3", tags=tag_list)
        job_object_list = _pipeline_protocols(submission, user, None)
        for job in job_object_list:
            self.assertIsNotNone(job.multinode_definition)
            self.assertNotIn("#", job.multinode_definition)
        with open(
            os.path.join(
                os.path.dirname(__file__), "sample_jobs", "kvm-multinode.yaml"
            ),
        ) as source:
            yaml_str = source.read()
        self.assertIn("# unit test support comment", yaml_str)
        job_object_list = _pipeline_protocols(submission, user, yaml_str)
        for job in job_object_list:
            self.assertIsNotNone(job.multinode_definition)
            self.assertIn("# unit test support comment", job.multinode_definition)

    @patch("lava_dispatcher.actions.deploy.download.requests_retry")
    def test_invalid_multinode(self, requests_mock):
        user = self.factory.make_user()
        device_type = self.factory.make_device_type()
        with open(
            os.path.join(
                os.path.dirname(__file__), "sample_jobs", "kvm-multinode.yaml"
            ),
        ) as f:
            submission = yaml_safe_load(f)

        tag_list = [
            self.factory.ensure_tag("usb-flash"),
            self.factory.ensure_tag("usb-eth"),
            self.factory.ensure_tag("testtag"),
        ]
        self.factory.make_device(device_type, "fakeqemu1")
        self.factory.make_device(device_type, "fakeqemu2")
        self.factory.make_device(device_type, "fakeqemu3", tags=tag_list)
        deploy = [
            action["deploy"] for action in submission["actions"] if "deploy" in action
        ]
        # replace working image with a broken URL
        for block in deploy:
            block["images"] = {
                "rootfs": {
                    "url": "http://localhost/unknown/invalid.gz",
                    "image_arg": "{rootfs}",
                }
            }
        job_object_list = _pipeline_protocols(
            submission, user, yaml_safe_dump(submission)
        )
        self.assertEqual(len(job_object_list), 2)
        self.assertEqual(
            job_object_list[0].sub_id, "%d.%d" % (int(job_object_list[0].id), 0)
        )
        # FIXME: dispatcher master needs to make this kind of test more accessible.
        for job in job_object_list:
            definition = yaml_safe_load(job.definition)
            self.assertNotEqual(definition["protocols"]["lava-multinode"]["sub_id"], "")
            job.actual_device = Device.objects.get(hostname="fakeqemu1")
            job_def = yaml_safe_load(job.definition)
            job_ctx = job_def.get("context", {})
            parser = JobParser()
            device = None
            device_object = None
            if not job.dynamic_connection:
                device = job.actual_device

                try:
                    device_config = device.load_configuration(job_ctx)  # raw dict
                except (JinjaTemplateError, yaml.YAMLError, OSError) as exc:
                    # FIXME: report the exceptions as useful user messages
                    self.fail("[%d] jinja2 error: %s" % (job.id, exc))
                if not device_config or not isinstance(device_config, dict):
                    # it is an error to have a pipeline device without a device dictionary as it will never get any jobs.
                    msg = (
                        "Administrative error. Device '%s' has no device dictionary."
                        % device.hostname
                    )
                    self.fail("[%d] device-dictionary error: %s" % (job.id, msg))

                device_object = PipelineDevice(
                    device_config
                )  # equivalent of the NewDevice in lava-dispatcher, without .yaml file.
                # FIXME: drop this nasty hack once 'target' is dropped as a parameter
                if "target" not in device_object:
                    device_object.target = device.hostname
                device_object["hostname"] = device.hostname

            self.assertTrue(device.is_valid())
            validate_list = job.sub_jobs_list if job.is_multinode else [job]
            for check_job in validate_list:
                parser_device = None if job.dynamic_connection else device_object
                try:
                    pipeline_job = parser.parse(
                        check_job.definition, parser_device, check_job.id, None, ""
                    )
                except (
                    AttributeError,
                    JobError,
                    NotImplementedError,
                    KeyError,
                    TypeError,
                ) as exc:
                    self.fail("[%s] parser error: %s" % (check_job.sub_id, exc))
                with TestCase.assertRaises(
                    self, (JobError, InfrastructureError)
                ) as check:
                    pipeline_job.pipeline.validate_actions()
                    check_missing_path(self, check, "qemu-system-x86_64")
        for job in job_object_list:
            job = TestJob.objects.get(id=job.id)
            self.assertNotEqual(job.sub_id, "")

    def test_multinode_with_retired(self):
        """
        check handling with retired devices in device_list
        """
        user = self.factory.make_user()
        device_type = self.factory.make_device_type()
        self.factory.make_device(device_type, "fakeqemu1")
        self.factory.make_device(device_type, "fakeqemu2")
        self.factory.make_device(device_type, "fakeqemu3")
        self.factory.make_device(device_type, "fakeqemu4")
        with open(
            os.path.join(
                os.path.dirname(__file__), "sample_jobs", "kvm-multinode.yaml"
            ),
        ) as f:
            submission = yaml_safe_load(f)
        role_list = submission["protocols"][MultinodeProtocol.name]["roles"]
        for role in role_list:
            if "tags" in role_list[role]:
                del role_list[role]["tags"]
        job_list = TestJob.from_yaml_and_user(yaml_safe_dump(submission), user)
        self.assertEqual(len(job_list), 2)

    @unittest.skipIf(not os.path.exists(SYS_CLASS_KVM), "Cannot use --enable-kvm")
    def test_multinode_mixed_deploy(self):
        user = self.factory.make_user()
        device_type = self.factory.make_device_type()
        self.factory.make_device(device_type, "fakeqemu1")
        self.factory.make_device(device_type, "fakeqemu2")
        bbb_type = self.factory.make_device_type("beaglebone-black")
        self.factory.make_device(hostname="bbb-01", device_type=bbb_type)
        self.factory.make_device(hostname="bbb-02", device_type=bbb_type)
        with open(
            os.path.join(
                os.path.dirname(__file__), "sample_jobs", "bbb-qemu-multinode.yaml"
            ),
        ) as f:
            submission = yaml_safe_load(f)
        job_object_list = _pipeline_protocols(
            submission, user, yaml_safe_dump(submission)
        )

        for job in job_object_list:
            definition = yaml_safe_load(job.definition)
            self.assertNotEqual(definition["protocols"]["lava-multinode"]["sub_id"], "")
            sub_ids = [job.sub_id for job in job_object_list]
            self.assertEqual(len(set(sub_ids)), len(sub_ids))
            if job.requested_device_type.name == "qemu":
                job.actual_device = Device.objects.get(hostname="fakeqemu1")
            elif job.requested_device_type.name == "beaglebone-black":
                job.actual_device = Device.objects.get(hostname="bbb-01")
            else:
                self.fail("Unrecognised device type: %s" % job.requested_device_type)
            job_def = yaml_safe_load(job.definition)
            job_ctx = job_def.get("context", {})
            parser = JobParser()
            device_object = None
            if not job.dynamic_connection:
                device = job.actual_device

                try:
                    device_config = device.load_configuration(job_ctx)  # raw dict
                except (JinjaTemplateError, yaml.YAMLError, OSError) as exc:
                    # FIXME: report the exceptions as useful user messages
                    self.fail("[%d] jinja2 error: %s" % (job.id, exc))
                if not device_config or not isinstance(device_config, dict):
                    # it is an error to have a pipeline device without a device dictionary as it will never get any jobs.
                    msg = (
                        "Administrative error. Device '%s' has no device dictionary."
                        % device.hostname
                    )
                    self.fail("[%d] device-dictionary error: %s" % (job.id, msg))

                device_object = PipelineDevice(
                    device_config
                )  # equivalent of the NewDevice in lava-dispatcher, without .yaml file.
                # FIXME: drop this nasty hack once 'target' is dropped as a parameter
                if "target" not in device_object:
                    device_object.target = device.hostname
                device_object["hostname"] = device.hostname
                self.assertTrue(device.is_valid())

            self.assertNotEqual(job.device_role, "Error")
            parser_device = None if job.dynamic_connection else device_object
            try:
                pipeline_job = parser.parse(
                    job.definition, parser_device, job.id, None, ""
                )
            except (
                AttributeError,
                JobError,
                NotImplementedError,
                KeyError,
                TypeError,
            ) as exc:
                self.fail("[%s] parser error: %s" % (job.sub_id, exc))
            pipeline_job.pipeline.validate_actions()

        for job in job_object_list:
            job = TestJob.objects.get(id=job.id)
            self.assertNotEqual(job.sub_id, "")

    def test_multinode_essential(self):
        user = self.factory.make_user()
        device_type = self.factory.make_device_type()
        self.factory.make_device(device_type, "fakeqemu1")
        self.factory.make_device(device_type, "fakeqemu2")
        bbb_type = self.factory.make_device_type("beaglebone-black")
        self.factory.make_device(hostname="bbb-01", device_type=bbb_type)
        self.factory.make_device(hostname="bbb-02", device_type=bbb_type)
        with open(
            os.path.join(
                os.path.dirname(__file__), "sample_jobs", "bbb-qemu-multinode.yaml"
            ),
        ) as f:
            submission = yaml_safe_load(f)
        self.assertIn("protocols", submission)
        self.assertIn(MultinodeProtocol.name, submission["protocols"])
        submission["protocols"][MultinodeProtocol.name]["roles"]["server"][
            "essential"
        ] = True
        job_object_list = _pipeline_protocols(
            submission, user, yaml_safe_dump(submission)
        )
        for job in job_object_list:
            definition = yaml_safe_load(job.definition)
            role = definition["protocols"][MultinodeProtocol.name]["role"]
            self.assertNotEqual(definition["protocols"]["lava-multinode"]["sub_id"], "")
            if role == "client":
                self.assertFalse(job.essential_role)
            elif role == "server":
                self.assertTrue(job.essential_role)
            else:
                self.fail("Unexpected role: %s" % role)


class VlanInterfaces(TestCaseWithFactory):
    def setUp(self):
        super().setUp()
        # YAML, pipeline only
        user = User.objects.create_user("test", "e@mail.invalid", "test")
        user.save()
        bbb_type = self.factory.make_device_type("beaglebone-black")
        self.factory.make_device(hostname="bbb-01", device_type=bbb_type)
        ct_type = self.factory.make_device_type("cubietruck")
        self.factory.make_device(hostname="ct-01", device_type=ct_type)
        self.filename = os.path.join(
            os.path.dirname(__file__), "sample_jobs", "bbb-cubie-vlan-group.yaml"
        )

    def test_vlan_interface(self):
        with open(self.filename) as f:
            submission = yaml_safe_load(f)
        self.assertIn("protocols", submission)
        self.assertIn("lava-vland", submission["protocols"])
        roles = [role for role, _ in submission["protocols"]["lava-vland"].items()]
        params = submission["protocols"]["lava-vland"]
        vlans = {}
        for role in roles:
            for name, tags in params[role].items():
                vlans[name] = tags
        self.assertIn("vlan_one", vlans)
        self.assertIn("vlan_two", vlans)
        jobs = split_multinode_yaml(submission, "abcdefghijkl")
        job_roles = {}
        for role in roles:
            self.assertEqual(len(jobs[role]), 1)
            job_roles[role] = jobs[role][0]
        for role in roles:
            self.assertIn("device_type", job_roles[role])
            self.assertIn("protocols", job_roles[role])
            self.assertIn("lava-vland", job_roles[role]["protocols"])
        client_job = job_roles["client"]
        server_job = job_roles["server"]
        self.assertIn("vlan_one", client_job["protocols"]["lava-vland"])
        self.assertIn("10M", client_job["protocols"]["lava-vland"]["vlan_one"]["tags"])
        self.assertIn("vlan_two", server_job["protocols"]["lava-vland"])
        self.assertIn("100M", server_job["protocols"]["lava-vland"]["vlan_two"]["tags"])
        client_job["protocols"]["lava-vland"]["vlan_one"]
        bbb_01 = Device.objects.get(hostname="bbb-01")
        client_config = bbb_01.load_configuration()
        self.assertIn("eth0", client_config["parameters"]["interfaces"])
        self.assertEqual(
            "192.168.0.2", client_config["parameters"]["interfaces"]["eth0"]["switch"]
        )
        self.assertEqual(5, client_config["parameters"]["interfaces"]["eth0"]["port"])

        # find_device_for_job would have a call to match_vlan_interface(device, job.definition) added
        bbb1 = Device.objects.get(hostname="bbb-01")
        self.assertTrue(match_vlan_interface(bbb1, client_job))
        cubie1 = Device.objects.get(hostname="ct-01")
        self.assertTrue(match_vlan_interface(cubie1, server_job))
