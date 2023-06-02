# Copyright (C) 2014-2019 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import os
import sys
import time
import unittest

import voluptuous
from jinja2 import ChoiceLoader, DictLoader, FileSystemLoader
from jinja2.sandbox import SandboxedEnvironment as JinjaSandboxEnv

from lava_common.exceptions import (
    ConfigurationError,
    InfrastructureError,
    JobError,
    LAVABug,
    LAVAError,
)
from lava_common.schemas import validate as validate_job
from lava_common.schemas.device import validate as validate_device
from lava_common.yaml import yaml_safe_dump, yaml_safe_load
from lava_dispatcher.action import Action, Pipeline
from lava_dispatcher.actions.deploy.image import DeployImages
from lava_dispatcher.device import NewDevice
from lava_dispatcher.parser import JobParser
from tests.utils import DummyLogger


class StdoutTestCase(unittest.TestCase):
    # set to True to update pipeline_references automatically.
    update_ref = False

    @classmethod
    def pipeline_reference(cls, filename, job=None):
        y_file = os.path.join(os.path.dirname(__file__), "pipeline_refs", filename)
        if cls.update_ref:
            sys.stderr.write("WARNING: modifying pipeline references!")
            with open(y_file, "w") as describe:
                yaml_safe_dump(
                    job.pipeline.describe(), describe, default_flow_style=None
                )
        with open(y_file) as f_ref:
            return yaml_safe_load(f_ref)


class TestAction(StdoutTestCase):
    def test_references_a_device(self):
        device = object()
        cmd = Action()
        cmd.device = device
        self.assertIs(cmd.device, device)


class TestPipelineInit(StdoutTestCase):
    class FakeAction(Action):
        def __init__(self):
            self.ran = False
            super().__init__()

        def run(self, connection, max_end_time):
            self.ran = True

        def post_process(self):
            raise NotImplementedError("invalid")

    def setUp(self):
        super().setUp()
        self.sub0 = TestPipelineInit.FakeAction()
        self.sub1 = TestPipelineInit.FakeAction()

    def test_pipeline_init(self):
        self.assertIsNotNone(self.sub0)
        self.assertIsNotNone(self.sub1)
        # prevent reviews leaving update_ref set to True.
        self.assertFalse(self.update_ref)

    def test_parsed_commands(self):
        command_list = ["false"]
        self.assertRaises(JobError, self.sub0.parsed_command, command_list)
        self.assertEqual("", self.sub0.parsed_command(command_list, allow_fail=True))
        self.sub1.command_exception = InfrastructureError
        self.assertRaises(InfrastructureError, self.sub1.parsed_command, command_list)
        command_list = ["true"]
        self.assertEqual("", self.sub0.parsed_command(command_list))
        self.assertEqual("", self.sub0.parsed_command(command_list, allow_fail=True))
        command_list = ["echo", "01234556789"]
        self.assertEqual("01234556789", self.sub0.parsed_command(command_list).strip())
        self.assertEqual(
            "01234556789",
            self.sub0.parsed_command(command_list, allow_fail=True).strip(),
        )
        command_list = ["ls", "./01234556789"]
        self.assertRaises(JobError, self.sub0.parsed_command, command_list)
        self.assertRaises(InfrastructureError, self.sub1.parsed_command, command_list)
        self.assertIn(
            "No such file or directory",
            self.sub0.parsed_command(command_list, allow_fail=True),
        )
        self.assertIn(
            "No such file or directory",
            self.sub1.parsed_command(command_list, allow_fail=True),
        )


class TestValidation(StdoutTestCase):
    def test_action_is_valid_if_there_are_not_errors(self):
        action = Action()
        action.__errors__ = [1]
        self.assertFalse(action.valid)
        action.__errors__ = []
        self.assertTrue(action.valid)

    def test_composite_action_aggregates_errors_from_sub_actions(self):
        # Unable to call Action.validate() as there is no job in this unit test
        sub1 = Action()
        sub1.__errors__ = [1]
        sub2 = Action()
        sub2.name = "sub2"
        sub2.__errors__ = [2]

        pipe = Pipeline()
        sub1.name = "sub1"
        pipe.add_action(sub1)
        pipe.add_action(sub2)
        self.assertEqual([1, 2], pipe.errors)


class Factory:
    """
    Not Model based, this is not a Django factory.
    Factory objects are dispatcher based classes, independent
    of any database objects.
    """

    DEVICE_TYPES_PATH = os.path.abspath(
        os.path.join(
            os.path.dirname(__file__),
            "..",
            "..",
            "etc",
            "dispatcher-config",
            "device-types",
        )
    )

    validate_job_strict = False

    def prepare_jinja_template(self, hostname, jinja_data):
        string_loader = DictLoader({"%s.jinja2" % hostname: jinja_data})
        type_loader = FileSystemLoader([self.DEVICE_TYPES_PATH])
        env = JinjaSandboxEnv(
            loader=ChoiceLoader([string_loader, type_loader]),
            trim_blocks=True,
            autoescape=False,
        )
        return env.get_template("%s.jinja2" % hostname)

    def render_device_dictionary(self, hostname, data, job_ctx=None):
        if not job_ctx:
            job_ctx = {}
        test_template = self.prepare_jinja_template(hostname, data)
        rendered = test_template.render(**job_ctx)
        return rendered

    def validate_data(self, hostname, data, job_ctx=None):
        """
        Needs to be passed a device dictionary (jinja2 format)
        """
        rendered = self.render_device_dictionary(hostname, data, job_ctx)
        try:
            ret = validate_device(yaml_safe_load(rendered))
        except (voluptuous.Invalid, ConfigurationError) as exc:
            print("#######")
            print(rendered)
            print("#######")
            raise exc
        return ret

    def create_device(self, template, job_ctx=None):
        """
        Create a device configuration on-the-fly from in-tree
        device-type Jinja2 template.
        """
        with open(
            os.path.join(
                os.path.dirname(__file__),
                "..",
                "..",
                "tests",
                "lava_scheduler_app",
                "devices",
                template,
            )
        ) as hikey:
            data = hikey.read()
        hostname = template.replace(".jinja2", "")
        rendered = self.render_device_dictionary(hostname, data, job_ctx)
        return (rendered, data)

    def create_custom_job(self, template, job_data, job_ctx=None, validate=True):
        if validate:
            validate_job(job_data, strict=self.validate_job_strict)
        if job_ctx:
            job_data["context"] = job_ctx
        else:
            job_ctx = job_data.get("context")
        (data, device_dict) = self.create_device(template, job_ctx)
        device = NewDevice(yaml_safe_load(data))
        try:
            parser = JobParser()
            job = parser.parse(yaml_safe_dump(job_data), device, "4999", None, "")
        except (ConfigurationError, TypeError) as exc:
            print("####### Parser exception ########")
            print(device)
            print("#######")
            raise ConfigurationError("Invalid device: %s" % exc)
        job.logger = DummyLogger()
        return job

    def create_job(self, template, filename, job_ctx=None, validate=True):
        y_file = os.path.join(os.path.dirname(__file__), filename)
        with open(y_file) as sample_job_data:
            job_data = yaml_safe_load(sample_job_data.read())
        return self.create_custom_job(template, job_data, job_ctx, validate)

    def create_kvm_job(self, filename, validate=False):
        """
        Custom function to allow for extra exception handling.
        """
        job_ctx = {
            "arch": "amd64",
            "no_kvm": True,
        }  # override to allow unit tests on all types of systems
        (data, device_dict) = self.create_device("kvm01.jinja2", job_ctx)
        device = NewDevice(yaml_safe_load(data))
        self.validate_data("hi6220-hikey-01", device_dict)
        kvm_yaml = os.path.join(os.path.dirname(__file__), filename)
        parser = JobParser()
        job_data = ""
        with open(kvm_yaml) as sample_job_data:
            job_data = yaml_safe_load(sample_job_data.read())
        if validate:
            validate_job(job_data, strict=False)
        try:
            job = parser.parse(yaml_safe_dump(job_data), device, 4212, None, "")
            job.logger = DummyLogger()
        except LAVAError as exc:
            print(exc)
            return None
        return job


class TestPipeline(StdoutTestCase):
    class FakeAction(Action):
        name = "fake-action"

        def __init__(self):
            self.ran = False
            super().__init__()

        def run(self, connection, max_end_time):
            time.sleep(1)
            self.ran = True

    def test_create_empty_pipeline(self):
        pipe = Pipeline()
        self.assertEqual(pipe.actions, [])

    def test_add_action_to_pipeline(self):
        action = Action()
        action.name = "test-action"
        action.description = "test action only"
        action.summary = "starter"
        self.assertEqual(action.description, "test action only")
        self.assertEqual(action.summary, "starter")
        # action needs to be added to a top level pipe first
        with self.assertRaises(LAVABug):
            Pipeline(action)
        pipe = Pipeline()
        with self.assertRaises(LAVABug):
            pipe.add_action(None)
        with self.assertRaises(LAVABug):
            pipe.add_action(pipe)
        pipe.add_action(action)
        self.assertEqual(pipe.actions, [action])
        self.assertEqual(action.level, "1")
        try:
            description = pipe.describe()
        except Exception as exc:
            self.fail(exc)
        self.assertIsNotNone(description)
        self.assertIsInstance(description, list)
        self.assertIn("description", description[0])
        self.assertIn("level", description[0])
        self.assertIn("summary", description[0])
        self.assertIn("max_retries", description[0])
        self.assertIn("timeout", description[0])

    def test_create_pipeline(self):
        action = Action()
        action.name = "internal_pipe"
        action.description = "test action only"
        action.summary = "starter"
        pipe = Pipeline()
        pipe.add_action(action)
        self.assertEqual(len(pipe.actions), 1)
        self.assertEqual(action.level, "1")
        action = Action()
        action.name = "child_action"
        action.summary = "child"
        action.description = "action implementing an internal pipe"
        with self.assertRaises(LAVABug):
            Pipeline(action)
        pipe.add_action(action)
        self.assertEqual(action.level, "2")
        self.assertEqual(len(pipe.actions), 2)
        # a formal RetryAction would contain a pre-built pipeline which can be inserted directly
        retry_pipe = Pipeline(action)
        action = Action()
        action.name = "inside_action"
        action.description = "action inside the internal pipe"
        action.summary = "child"
        retry_pipe.add_action(action)
        self.assertEqual(len(retry_pipe.actions), 1)
        self.assertEqual(action.level, "2.1")

    def test_complex_pipeline(self):
        action = Action()
        action.name = "starter_action"
        action.description = "test action only"
        action.summary = "starter"
        pipe = Pipeline()
        pipe.add_action(action)
        self.assertEqual(action.level, "1")
        action = Action()
        action.name = "pipe_action"
        action.description = "action implementing an internal pipe"
        action.summary = "child"
        pipe.add_action(action)
        self.assertEqual(action.level, "2")
        # a formal RetryAction would contain a pre-built pipeline which can be inserted directly
        retry_pipe = Pipeline(action)
        action = Action()
        action.name = "child_action"
        action.description = "action inside the internal pipe"
        action.summary = "child"
        retry_pipe.add_action(action)
        self.assertEqual(action.level, "2.1")
        action = Action()
        action.name = "second-child-action"
        action.description = "second action inside the internal pipe"
        action.summary = "child2"
        retry_pipe.add_action(action)
        self.assertEqual(action.level, "2.2")
        action = Action()
        action.name = "baby_action"
        action.description = "action implementing an internal pipe"
        action.summary = "baby"
        retry_pipe.add_action(action)
        self.assertEqual(action.level, "2.3")
        inner_pipe = Pipeline(action)
        action = Action()
        action.name = "single_action"
        action.description = "single line action"
        action.summary = "single"
        inner_pipe.add_action(action)
        self.assertEqual(action.level, "2.3.1")

        action = Action()
        action.name = "step_out"
        action.description = "step out of inner pipe"
        action.summary = "brother"
        retry_pipe.add_action(action)
        self.assertEqual(action.level, "2.4")
        action = Action()
        action.name = "top-level"
        action.description = "top level"
        action.summary = "action"
        pipe.add_action(action)
        self.assertEqual(action.level, "3")
        self.assertEqual(len(pipe.describe()), 3)

    def test_describe(self):
        factory = Factory()
        job = factory.create_kvm_job("sample_jobs/kvm.yaml")
        self.assertIsNotNone(job)
        pipe = job.pipeline.describe()
        for item in pipe:
            self.assertNotIn("match", item)
            if "pipeline" in item:
                for element in item["pipeline"]:
                    self.assertNotIn("match", element)

    def test_compatibility(self):
        """
        Test compatibility support.

        The class to use in the comparison will change according to which class
        is related to the change which caused the compatibility to be modified.
        """
        factory = Factory()
        job = factory.create_kvm_job("sample_jobs/kvm.yaml")
        self.assertIsNotNone(job)
        pipe = job.describe()
        self.assertEqual(pipe["compatibility"], DeployImages.compatibility)
        self.assertEqual(job.compatibility, DeployImages.compatibility)
        kvm_yaml = os.path.join(os.path.dirname(__file__), "sample_jobs/kvm.yaml")
        with open(kvm_yaml) as kvm_yaml:
            job_def = yaml_safe_load(kvm_yaml)
        job_def["compatibility"] = job.compatibility
        parser = JobParser()
        (rendered, data) = factory.create_device("kvm01.jinja2")
        device = yaml_safe_load(rendered)
        job = parser.parse(yaml_safe_dump(job_def), device, 4212, None, "")
        self.assertIsNotNone(job)
        job_def["compatibility"] = job.compatibility + 1
        self.assertRaises(
            JobError, parser.parse, yaml_safe_dump(job_def), device, 4212, None, ""
        )
        job_def["compatibility"] = 0
        job = parser.parse(yaml_safe_dump(job_def), device, 4212, None, "")
        self.assertIsNotNone(job)

    def test_pipeline_actions(self):
        factory = Factory()
        job = factory.create_kvm_job("sample_jobs/kvm.yaml")
        self.assertEqual(
            ["deploy", "boot", "test", "finalize"],
            [action.section for action in job.pipeline.actions],
        )

    def test_namespace_data(self):
        factory = Factory()
        job = factory.create_kvm_job("sample_jobs/kvm.yaml")
        self.assertIsNotNone(job)
        test_action = job.pipeline.actions[0]
        test_action.validate()
        test_action.set_namespace_data("common", "label", "simple", 1)
        self.assertEqual(test_action.get_namespace_data("common", "label", "simple"), 1)
        test_action.set_namespace_data("common", "ns", "dict", {"key": False})
        self.assertEqual(
            test_action.get_namespace_data("common", "ns", "dict"), {"key": False}
        )
        test_action.set_namespace_data("common", "ns", "list", [1, 2, 3, "4"])
        self.assertEqual(
            test_action.get_namespace_data("common", "ns", "list"), [1, 2, 3, "4"]
        )
        test_action.set_namespace_data("common", "ns", "dict2", {"key": {"nest": True}})
        self.assertEqual(
            test_action.get_namespace_data("common", "ns", "dict2"),
            {"key": {"nest": True}},
        )
        self.assertNotEqual(
            test_action.get_namespace_data("common", "unknown", "simple"), 1
        )


class TestFakeActions(StdoutTestCase):
    class KeepConnection(Action):
        name = "keep-connection"

        def run(self, connection, max_end_time):
            pass

        def post_process(self):
            raise NotImplementedError("invalid")

    class MakeNewConnection(Action):
        name = "make-new-connection"

        def run(self, connection, max_end_time):
            new_connection = object()
            return new_connection

    def setUp(self):
        super().setUp()
        self.sub0 = TestPipeline.FakeAction()
        self.sub1 = TestPipeline.FakeAction()

    def test_list_of_subcommands(self):
        pipe = Pipeline()
        pipe.add_action(self.sub0)
        pipe.add_action(self.sub1)
        self.assertIs(pipe.actions[0], self.sub0)
        self.assertIs(pipe.actions[1], self.sub1)

    def test_runs_subaction(self):
        pipe = Pipeline()
        pipe.add_action(self.sub0)
        pipe.add_action(self.sub1)
        pipe.run_actions(None, None)
        self.assertTrue(self.sub0.ran)
        self.assertTrue(self.sub1.ran)
        self.assertNotEqual(self.sub0.timeout.elapsed_time, 0)
        self.assertNotEqual(self.sub1.timeout.elapsed_time, 0)

    def test_keep_connection(self):
        pipe = Pipeline()
        pipe.add_action(TestFakeActions.KeepConnection())
        conn = object()
        self.assertIs(conn, pipe.run_actions(conn, None))

    def test_change_connection(self):
        pipe = Pipeline()
        pipe.add_action(TestFakeActions.MakeNewConnection())
        conn = object()
        self.assertIsNot(conn, pipe.run_actions(conn, None))


class TestStrategySelector(StdoutTestCase):
    """
    Check the lambda operation
    """

    class Base:
        priority = 0

    class First(Base):
        priority = 1

    class Second(Base):
        priority = 2

    class Third(Base):
        priority = 3

    def test_willing(self):
        willing = [
            TestStrategySelector.First(),
            TestStrategySelector.Third(),
            TestStrategySelector.Second(),
        ]
        willing.sort(key=lambda x: x.priority, reverse=True)
        self.assertIsInstance(willing[0], TestStrategySelector.Third)
