# Copyright (C) 2014 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
#
# This file is part of LAVA Dispatcher.
#
# LAVA Dispatcher is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# LAVA Dispatcher is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along
# with this program; if not, see <http://www.gnu.org/licenses>.

import os
import sys
import time
import jinja2
import unittest
import logging
import yaml

from lava_dispatcher.action import (
    Pipeline,
    Action,
)
from lava_common.exceptions import (
    JobError,
    LAVABug,
    LAVAError,
    ConfigurationError,
)
from lava_dispatcher.parser import JobParser
from lava_dispatcher.job import Job
from lava_dispatcher.device import NewDevice
from lava_scheduler_app.schema import validate_device, SubmissionException
from lava_dispatcher.actions.deploy.image import DeployImages
from lava_dispatcher.test.utils import DummyLogger

# pylint: disable=superfluous-parens,too-few-public-methods


class StdoutTestCase(unittest.TestCase):  # pylint: disable=too-many-public-methods

    def setUp(self):
        super().setUp()
        logger = logging.getLogger('dispatcher')
        logger.disabled = True
        logger.propagate = False
        # set to True to update pipeline_references automatically.
        self.update_ref = False
        self.job = None

    def pipeline_reference(self, filename, job=None):
        y_file = os.path.join(os.path.dirname(__file__), 'pipeline_refs', filename)
        if self.update_ref:
            if not job:
                job = self.job
            sys.stderr.write('WARNING: modifying pipeline references!')
            with open(y_file, 'w') as describe:
                yaml.dump(job.pipeline.describe(False), describe)
        with open(y_file, 'r') as f_ref:
            return yaml.safe_load(f_ref)


class TestAction(StdoutTestCase):  # pylint: disable=too-many-public-methods

    def test_references_a_device(self):
        device = object()
        cmd = Action()
        cmd.device = device
        self.assertIs(cmd.device, device)


class TestPipelineInit(StdoutTestCase):  # pylint: disable=too-many-public-methods

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


class TestJobParser(StdoutTestCase):  # pylint: disable=too-many-public-methods

    def setUp(self):
        super().setUp()
        factory = Factory()
        self.job = factory.create_kvm_job('sample_jobs/basics.yaml')

    def test_parser_creates_a_job_with_a_pipeline(self):  # pylint: disable=invalid-name
        if not self.job:
            return unittest.skip("not all deployments have been implemented")
        self.assertIsInstance(self.job, Job)
        self.assertIsInstance(self.job.pipeline, Pipeline)

    def test_pipeline_gets_multiple_actions_in_it(self):  # pylint: disable=invalid-name
        if not self.job:
            return unittest.skip("not all deployments have been implemented")
        self.assertTrue(self.job.actions > 1)  # pylint: disable=no-member


class TestValidation(StdoutTestCase):  # pylint: disable=too-many-public-methods

    def test_action_is_valid_if_there_are_not_errors(self):  # pylint: disable=invalid-name
        action = Action()
        action.__errors__ = [1]
        self.assertFalse(action.valid)
        action.__errors__ = []
        self.assertTrue(action.valid)

    def test_composite_action_aggregates_errors_from_sub_actions(self):  # pylint: disable=invalid-name
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

    def __init__(self):
        logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
        logger = logging.getLogger('unittests')
        logger.disabled = True
        logger.propagate = False
        logger = logging.getLogger('dispatcher')
        logger.disabled = True
        logger.propagate = False
        self.debug = False

    CONFIG_PATH = os.path.abspath(
        os.path.join(
            os.path.dirname(__file__), "..", "..",
            "lava_scheduler_app", "tests", "devices"))

    def prepare_jinja_template(self, hostname, jinja_data):
        string_loader = jinja2.DictLoader({'%s.jinja2' % hostname: jinja_data})
        path = os.path.dirname(self.CONFIG_PATH)
        type_loader = jinja2.FileSystemLoader([os.path.join(path, 'device-types')])
        env = jinja2.Environment(  # nosec - YAML, not HTML, no XSS scope.
            loader=jinja2.ChoiceLoader([string_loader, type_loader]),
            trim_blocks=True, autoescape=False)
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
            ret = validate_device(yaml.safe_load(rendered))
        except (SubmissionException, ConfigurationError) as exc:
            print('#######')
            print(rendered)
            print('#######')
            self.fail(exc)
        return ret

    def create_device(self, template, job_ctx=None):
        """
        Create a device configuration on-the-fly from in-tree
        device-type Jinja2 template.
        """
        with open(
            os.path.join(
                os.path.dirname(__file__),
                '..', '..', 'lava_scheduler_app', 'tests',
                'devices', template)) as hikey:
            data = hikey.read()
        hostname = template.replace('.jinja2', '')
        rendered = self.render_device_dictionary(hostname, data, job_ctx)
        return (rendered, data)

    def create_custom_job(self, template, job_data):
        job_ctx = job_data.get('context')
        (data, device_dict) = self.create_device(template, job_ctx)
        device = NewDevice(yaml.safe_load(data))
        if self.debug:
            print('####### Device configuration #######')
            print(data)
            print('#######')
        try:
            parser = JobParser()
            job = parser.parse(yaml.dump(job_data), device, 4999, None, "")
        except (ConfigurationError, TypeError) as exc:
            print('####### Parser exception ########')
            print(device)
            print('#######')
            raise ConfigurationError("Invalid device: %s" % exc)
        job.logger = DummyLogger()
        return job

    def create_job(self, template, filename):
        y_file = os.path.join(os.path.dirname(__file__), filename)
        with open(y_file) as sample_job_data:
            job_data = yaml.safe_load(sample_job_data.read())
        return self.create_custom_job(template, job_data)

    def create_fake_qemu_job(self):
        return self.create_job('qemu01.jinja2', 'sample_jobs/basics.yaml')

    def create_kvm_job(self, filename):  # pylint: disable=no-self-use
        """
        Custom function to allow for extra exception handling.
        """
        (data, device_dict) = self.create_device('kvm01.jinja2')
        device = NewDevice(yaml.safe_load(data))
        if self.debug:
            print('####### Device configuration #######')
            print(data)
            print('#######')
        self.validate_data('hi6220-hikey-01', device_dict)
        kvm_yaml = os.path.join(os.path.dirname(__file__), filename)
        parser = JobParser()
        try:
            with open(kvm_yaml) as sample_job_data:
                job = parser.parse(sample_job_data, device, 4212, None, "")
            job.logger = DummyLogger()
        except LAVAError as exc:
            print(exc)
            # some deployments listed in basics.yaml are not implemented yet
            return None
        return job


class TestPipeline(StdoutTestCase):  # pylint: disable=too-many-public-methods

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
        except Exception as exc:  # pylint: disable=broad-except
            self.fail(exc)
        self.assertIsNotNone(description)
        self.assertIsInstance(description, list)
        self.assertIn('description', description[0])
        self.assertIn('level', description[0])
        self.assertIn('summary', description[0])
        self.assertIn('max_retries', description[0])
        self.assertIn('timeout', description[0])

    def test_create_internal_pipeline(self):
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

    def test_complex_pipeline(self):  # pylint: disable=too-many-statements
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

    def test_simulated_action(self):
        factory = Factory()
        job = factory.create_kvm_job('sample_jobs/basics.yaml')
        if not job:
            return unittest.skip("not all deployments have been implemented")
        self.assertIsNotNone(job)

    def test_describe(self):
        factory = Factory()
        job = factory.create_kvm_job('sample_jobs/kvm.yaml')
        self.assertIsNotNone(job)
        pipe = job.pipeline.describe()
        for item in pipe:
            self.assertNotIn('match', item)
            if 'pipeline' in item:
                for element in item['pipeline']:
                    self.assertNotIn('match', element)

    def test_compatibility(self):
        """
        Test compatibility support.

        The class to use in the comparison will change according to which class
        is related to the change which caused the compatibility to be modified.
        """
        factory = Factory()
        job = factory.create_kvm_job('sample_jobs/kvm.yaml')
        pipe = job.describe()
        self.assertEqual(pipe['compatibility'], DeployImages.compatibility)
        self.assertEqual(job.compatibility, DeployImages.compatibility)
        kvm_yaml = os.path.join(os.path.dirname(__file__), 'sample_jobs/kvm.yaml')
        with open(kvm_yaml, 'r') as kvm_yaml:
            job_def = yaml.safe_load(kvm_yaml)
        job_def['compatibility'] = job.compatibility
        parser = JobParser()
        (rendered, data) = factory.create_device('kvm01.jinja2')
        device = yaml.safe_load(rendered)
        try:
            job = parser.parse(yaml.dump(job_def), device, 4212, None, "")
        except NotImplementedError:
            # some deployments listed in basics.yaml are not implemented yet
            pass
        self.assertIsNotNone(job)
        job_def['compatibility'] = job.compatibility + 1
        self.assertRaises(
            JobError, parser.parse, yaml.dump(job_def), device, 4212, None, ""
        )
        job_def['compatibility'] = 0
        try:
            job = parser.parse(yaml.dump(job_def), device, 4212, None, "")
        except NotImplementedError:
            # some deployments listed in basics.yaml are not implemented yet
            pass
        self.assertIsNotNone(job)

    def test_pipeline_actions(self):
        factory = Factory()
        job = factory.create_kvm_job('sample_jobs/kvm.yaml')
        self.assertEqual(
            ['deploy', 'boot', 'test', 'finalize'],
            [action.section for action in job.pipeline.actions]
        )

    def test_namespace_data(self):
        factory = Factory()
        job = factory.create_kvm_job('sample_jobs/kvm.yaml')
        self.assertIsNotNone(job)
        test_action = job.pipeline.actions[0]
        test_action.validate()
        test_action.set_namespace_data('common', 'label', 'simple', 1)
        self.assertEqual(test_action.get_namespace_data('common', 'label', 'simple'), 1)
        test_action.set_namespace_data('common', 'ns', 'dict', {'key': False})
        self.assertEqual(test_action.get_namespace_data('common', 'ns', 'dict'), {'key': False})
        test_action.set_namespace_data('common', 'ns', 'list', [1, 2, 3, '4'])
        self.assertEqual(test_action.get_namespace_data('common', 'ns', 'list'), [1, 2, 3, '4'])
        test_action.set_namespace_data('common', 'ns', 'dict2', {'key': {'nest': True}})
        self.assertEqual(test_action.get_namespace_data('common', 'ns', 'dict2'), {'key': {'nest': True}})
        self.assertNotEqual(test_action.get_namespace_data('common', 'unknown', 'simple'), 1)


class TestFakeActions(StdoutTestCase):  # pylint: disable=too-many-public-methods

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
        willing = [TestStrategySelector.First(), TestStrategySelector.Third(), TestStrategySelector.Second()]
        willing.sort(key=lambda x: x.priority, reverse=True)
        self.assertIsInstance(willing[0], TestStrategySelector.Third)
