# Copyright (C) 2014-2019 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

import os
import sys
import time
import unittest
from functools import cache
from pathlib import Path
from random import randint
from signal import alarm
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING
from unittest.mock import MagicMock
from warnings import warn

import voluptuous
from jinja2 import FileSystemLoader

from lava_common.exceptions import (
    ConfigurationError,
    InfrastructureError,
    JobError,
    LAVABug,
)
from lava_common.jinja import create_device_templates_env
from lava_common.log import YAMLLogger
from lava_common.schemas import validate as validate_job
from lava_common.schemas.device import validate as validate_device
from lava_common.timeout import Timeout
from lava_common.yaml import yaml_safe_dump, yaml_safe_load
from lava_dispatcher.action import Action, Pipeline
from lava_dispatcher.device import NewDevice
from lava_dispatcher.job import Job
from lava_dispatcher.parser import JobParser

if TYPE_CHECKING:
    from collections.abc import Callable
    from typing import Any, Optional

    from jinja2.sandbox import SandboxedEnvironment


class LavaDispatcherTestCase(unittest.TestCase):
    # set to True to update pipeline_references automatically.
    update_ref = False

    def create_temporary_directory(self) -> Path:
        tmp_dir = TemporaryDirectory(prefix=self.__call__.__name__)
        self.addCleanup(tmp_dir.cleanup)
        return Path(tmp_dir.name)

    TESTCASE_JOB_LOGGER = YAMLLogger("lava_dispatcher_testcase_job_logger")

    def create_job_mock(self) -> Job:
        return MagicMock(spec=Job)

    def create_simple_job(
        self, device_dict: Optional[dict] = None, job_parameters: Optional[dict] = None
    ) -> Job:
        if device_dict is None:
            device_dict = {}

        if job_parameters is None:
            job_parameters = {}

        new_job = Job(
            job_id=randint(0, 2**32 - 1),
            parameters=job_parameters,
            logger=LavaDispatcherTestCase.TESTCASE_JOB_LOGGER,
            device=NewDevice(device_dict),
            timeout=Timeout(
                f"unittest-timeout-{self.__class__.__name__}",
                None,
                duration=3,
            ),
        )
        return new_job

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

    def tearDown(self) -> None:
        super().tearDown()

        if alarm(0) != 0:
            warn("SIGALRM not cleaned-up", RuntimeWarning)


class TestPipelineInit(LavaDispatcherTestCase):
    class FakeAction(Action):
        def __init__(self, job: Job):
            self.ran = False
            super().__init__(job)

        def run(self, connection, max_end_time):
            self.ran = True

        def post_process(self):
            raise NotImplementedError("invalid")

    def setUp(self):
        super().setUp()
        job = self.create_job_mock()
        self.sub0 = TestPipelineInit.FakeAction(job)
        self.sub1 = TestPipelineInit.FakeAction(job)

    def test_pipeline_init(self):
        self.assertIsNotNone(self.sub0)
        self.assertIsNotNone(self.sub1)
        # prevent reviews leaving update_ref set to True.
        self.assertFalse(self.update_ref)

    def test_parsed_commands(self):
        command_list = ["false"]
        self.assertRaises(JobError, self.sub0.parsed_command, command_list)
        self.assertEqual(
            "Command '['false']' returned non-zero exit status 1.",
            self.sub0.parsed_command(command_list, allow_fail=True),
        )
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


class TestValidation(LavaDispatcherTestCase):
    def test_action_is_valid_if_there_are_not_errors(self):
        job = self.create_job_mock()
        action = Action(job)
        action.__errors__ = [1]
        self.assertFalse(action.valid)
        action.__errors__ = []
        self.assertTrue(action.valid)

    def test_composite_action_aggregates_errors_from_sub_actions(self):
        job = self.create_simple_job()
        # Unable to call Action.validate() as there is no job in this unit test
        sub1 = Action(job)
        sub1.__errors__ = [1]
        sub2 = Action(job)
        sub2.name = "sub2"
        sub2.__errors__ = [2]

        pipe = Pipeline(job=self.create_simple_job())
        sub1.name = "sub1"
        pipe.add_action(sub1)
        pipe.add_action(sub2)
        self.assertEqual([1, 2], pipe.errors)


@cache
def get_test_template_env() -> SandboxedEnvironment:
    test_dir = Path(__file__).parent
    device_types_templates_path = test_dir / "../../etc/dispatcher-config/device-types"
    device_templates_path = test_dir / "../lava_scheduler_app/devices"

    return create_device_templates_env(
        loader=FileSystemLoader((device_types_templates_path, device_templates_path)),
        cache_size=-1,
    )


class Factory:
    """
    Not Model based, this is not a Django factory.
    Factory objects are dispatcher based classes, independent
    of any database objects.
    """

    validate_job_strict = False

    def get_device_jinja_template(self, device_name: str):
        env = get_test_template_env()
        return env.get_template(f"{device_name}.jinja2")

    def render_device_dictionary(
        self, device_name: str, job_context: Optional[dict[str, Any]] = None
    ) -> str:
        if job_context is None:
            job_context = {}
        test_template = self.get_device_jinja_template(device_name)
        return test_template.render(**job_context)

    def validate_device_dict(self, device_dict: dict[str, Any]) -> None:
        try:
            validate_device(device_dict)
        except (voluptuous.Invalid, ConfigurationError) as exc:
            print("#######")
            print(repr(device_dict))
            print("#######")
            raise exc

    def load_device_configuration_dict(
        self, device_name: str, job_context: Optional[dict[str, Any]] = None
    ) -> dict[str, Any]:
        device_dict_str = self.render_device_dictionary(device_name, job_context)
        device_dict = yaml_safe_load(device_dict_str)
        self.validate_device_dict(device_dict)
        return device_dict

    def create_custom_job(
        self,
        device_name: str,
        job_dict: dict[str, Any],
        job_context: dict[str, Any] = None,
        validate: bool = True,
        dispatcher_config=None,
        env_dut=None,
        *,
        device_dict_preprocessor: Optional[Callable[[dict[str, Any], None]]] = None,
    ):
        if validate:
            validate_job(job_dict, strict=self.validate_job_strict)
        if job_context is not None:
            job_dict["context"] = job_context
        else:
            job_context = job_dict.get("context")

        device_dict = self.load_device_configuration_dict(device_name, job_context)
        if device_dict_preprocessor is not None:
            device_dict_preprocessor(device_dict)
        device = NewDevice(device_dict)
        try:
            parser = JobParser()
            job = parser.parse(
                content=yaml_safe_dump(job_dict),
                device=device,
                job_id=str(randint(1, 2**32 - 1)),
                logger=YAMLLogger("lava_dispatcher_testcase_job_logger"),
                dispatcher_config=dispatcher_config,
                env_dut=env_dut,
            )
        except (ConfigurationError, TypeError) as exc:
            print("####### Parser exception ########")
            print(device)
            print("#######")
            raise ConfigurationError("Invalid device: %s" % exc) from exc

        return job

    def create_job(
        self,
        device_name: str,
        filename: str,
        job_context: dict[str, Any] = None,
        validate: bool = True,
        dispatcher_config=None,
        env_dut=None,
        *,
        device_dict_preprocessor: Optional[Callable[[dict[str, Any], None]]] = None,
        job_dict_preprocessor: Optional[Callable[[dict[str, Any], None]]] = None,
    ):
        y_file = os.path.join(os.path.dirname(__file__), filename)
        with open(y_file) as sample_job_data:
            job_dict = yaml_safe_load(sample_job_data.read())

        if job_dict_preprocessor is not None:
            job_dict_preprocessor(job_dict)

        return self.create_custom_job(
            device_name,
            job_dict,
            job_context,
            validate,
            dispatcher_config,
            env_dut,
            device_dict_preprocessor=device_dict_preprocessor,
        )

    def create_kvm_job(self, filename: str, validate=False):
        return self.create_job(
            "kvm01",
            filename,
            {"arch": "amd64", "no_kvm": True},
            validate,
        )


class TestPipeline(LavaDispatcherTestCase):
    class FakeAction(Action):
        name = "fake-action"

        def __init__(self, job: Job):
            self.ran = False
            super().__init__(job)

        def run(self, connection, max_end_time):
            time.sleep(0.01)
            self.ran = True

    def test_create_empty_pipeline(self):
        pipe = Pipeline(job=self.create_simple_job())
        self.assertEqual(pipe.actions, [])

    def test_add_action_to_pipeline(self):
        action = Action(self.create_simple_job())
        action.name = "test-action"
        action.description = "test action only"
        action.summary = "starter"
        self.assertEqual(action.description, "test action only")
        self.assertEqual(action.summary, "starter")
        # action needs to be added to a top level pipe first
        with self.assertRaises(LAVABug):
            Pipeline(job=self.create_simple_job(), parent=action)
        pipe = Pipeline(job=self.create_simple_job())
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
        job = self.create_simple_job()
        action = Action(job)
        action.name = "internal_pipe"
        action.description = "test action only"
        action.summary = "starter"
        pipe = Pipeline(job=job)
        pipe.add_action(action)
        self.assertEqual(len(pipe.actions), 1)
        self.assertEqual(action.level, "1")
        action = Action(job)
        action.name = "child_action"
        action.summary = "child"
        action.description = "action implementing an internal pipe"
        with self.assertRaises(LAVABug):
            Pipeline(job=self.create_simple_job(), parent=action)
        pipe.add_action(action)
        self.assertEqual(action.level, "2")
        self.assertEqual(len(pipe.actions), 2)
        # a formal RetryAction would contain a pre-built pipeline
        # which can be inserted directly
        job = self.create_simple_job()
        retry_pipe = Pipeline(job=job, parent=action)
        action = Action(job)
        action.name = "inside_action"
        action.description = "action inside the internal pipe"
        action.summary = "child"
        retry_pipe.add_action(action)
        self.assertEqual(len(retry_pipe.actions), 1)
        self.assertEqual(action.level, "2.1")

    def test_complex_pipeline(self):
        job = self.create_simple_job()
        action = Action(job)
        action.name = "starter_action"
        action.description = "test action only"
        action.summary = "starter"
        pipe = Pipeline(job=job)
        pipe.add_action(action)
        self.assertEqual(action.level, "1")
        action = Action(job)
        action.name = "pipe_action"
        action.description = "action implementing an internal pipe"
        action.summary = "child"
        pipe.add_action(action)
        self.assertEqual(action.level, "2")
        # a formal RetryAction would contain a pre-built pipeline
        # which can be inserted directly
        job = self.create_simple_job()
        retry_pipe = Pipeline(job=self.create_simple_job(), parent=action)
        action = Action(job)
        action.name = "child_action"
        action.description = "action inside the internal pipe"
        action.summary = "child"
        retry_pipe.add_action(action)
        self.assertEqual(action.level, "2.1")
        action = Action(job)
        action.name = "second-child-action"
        action.description = "second action inside the internal pipe"
        action.summary = "child2"
        retry_pipe.add_action(action)
        self.assertEqual(action.level, "2.2")
        action = Action(job)
        action.name = "baby_action"
        action.description = "action implementing an internal pipe"
        action.summary = "baby"
        retry_pipe.add_action(action)
        self.assertEqual(action.level, "2.3")
        job = self.create_simple_job()
        inner_pipe = Pipeline(job=job, parent=action)
        action = Action(job)
        action.name = "single_action"
        action.description = "single line action"
        action.summary = "single"
        inner_pipe.add_action(action)
        self.assertEqual(action.level, "2.3.1")

        action = Action(job)
        action.name = "step_out"
        action.description = "step out of inner pipe"
        action.summary = "brother"
        retry_pipe.add_action(action)
        self.assertEqual(action.level, "2.4")
        action = Action(job)
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


class TestFakeActions(LavaDispatcherTestCase):
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
        self.job = self.create_simple_job()
        self.sub0 = TestPipeline.FakeAction(self.job)
        self.sub1 = TestPipeline.FakeAction(self.job)

    def test_list_of_subcommands(self):
        pipe = Pipeline(job=self.job)
        pipe.add_action(self.sub0)
        pipe.add_action(self.sub1)
        self.assertIs(pipe.actions[0], self.sub0)
        self.assertIs(pipe.actions[1], self.sub1)

    def test_runs_subaction(self):
        pipe = Pipeline(job=self.job)
        pipe.add_action(self.sub0)
        pipe.add_action(self.sub1)
        with pipe.job.timeout(None, None) as max_end_time:
            pipe.run_actions(None, max_end_time)
        self.assertTrue(self.sub0.ran)
        self.assertTrue(self.sub1.ran)
        self.assertNotEqual(self.sub0.timeout.elapsed_time, 0)
        self.assertNotEqual(self.sub1.timeout.elapsed_time, 0)

    def test_keep_connection(self):
        job = self.create_simple_job()
        pipe = Pipeline(job=job)
        pipe.add_action(TestFakeActions.KeepConnection(job))
        conn = object()
        with pipe.job.timeout(None, None) as max_end_time:
            self.assertIs(conn, pipe.run_actions(conn, max_end_time))

    def test_change_connection(self):
        job = self.create_simple_job()
        pipe = Pipeline(job=job)
        pipe.add_action(TestFakeActions.MakeNewConnection(job))
        conn = object()
        with pipe.job.timeout(None, None) as max_end_time:
            self.assertIsNot(conn, pipe.run_actions(conn, max_end_time))


class TestStrategySelector(LavaDispatcherTestCase):
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
