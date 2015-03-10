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
import time
import unittest
import simplejson
import yaml

from lava_dispatcher.pipeline.utils.filesystem import mkdtemp
from lava_dispatcher.pipeline.action import Pipeline, Action
from lava_dispatcher.pipeline.parser import JobParser
from lava_dispatcher.pipeline.job import Job
from lava_dispatcher.pipeline.device import NewDevice


class TestAction(unittest.TestCase):  # pylint: disable=too-many-public-methods

    def test_references_a_device(self):
        device = object()
        cmd = Action()
        cmd.device = device
        self.assertIs(cmd.device, device)


class TestPipelineInit(unittest.TestCase):  # pylint: disable=too-many-public-methods

    class FakeAction(Action):  # pylint: disable=abstract-class-not-used

        def __init__(self):
            self.ran = False
            super(TestPipelineInit.FakeAction, self).__init__()

        def run(self, connection, args=None):
            self.ran = True

        def post_process(self):
            raise NotImplementedError("invalid")

    def setUp(self):
        self.sub0 = TestPipelineInit.FakeAction()
        self.sub1 = TestPipelineInit.FakeAction()

    def test_pipeline_init(self):
        self.assertIsNotNone(self.sub0)
        self.assertIsNotNone(self.sub1)


class TestJobParser(unittest.TestCase):  # pylint: disable=too-many-public-methods

    def setUp(self):
        factory = Factory()
        self.job = factory.create_kvm_job('sample_jobs/basics.yaml', mkdtemp())

    def test_parser_creates_a_job_with_a_pipeline(self):  # pylint: disable=invalid-name
        if not self.job:
            return unittest.skip("not all deployments have been implemented")
        self.assertIsInstance(self.job, Job)
        self.assertIsInstance(self.job.pipeline, Pipeline)

    def test_pipeline_gets_multiple_actions_in_it(self):  # pylint: disable=invalid-name
        if not self.job:
            return unittest.skip("not all deployments have been implemented")
        self.assertTrue(self.job.actions > 1)


def pipeline_reference(filename):
    with open(os.path.join(os.path.dirname(__file__),
              'pipeline_refs', filename), 'r') as f_ref:
        return yaml.load(f_ref)


class TestValidation(unittest.TestCase):  # pylint: disable=too-many-public-methods

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


class Factory(object):
    """
    Not Model based, this is not a Django factory.
    Factory objects are dispatcher based classes, independent
    of any database objects.
    """
    def create_fake_qemu_job(self, output_dir=None):  # pylint: disable=no-self-use
        device = NewDevice(os.path.join(os.path.dirname(__file__), '../devices/kvm01.yaml'))
        sample_job_file = os.path.join(os.path.dirname(__file__), 'sample_jobs/basics.yaml')
        parser = JobParser()
        try:
            with open(sample_job_file) as sample_job_data:
                job = parser.parse(sample_job_data, device, 4212, None, output_dir=output_dir)
        except NotImplementedError:
            # some deployments listed in basics.yaml are not implemented yet
            return None
        return job

    def create_kvm_job(self, filename, output_dir='/tmp/'):  # pylint: disable=no-self-use
        device = NewDevice(os.path.join(os.path.dirname(__file__), '../devices/kvm01.yaml'))
        kvm_yaml = os.path.join(os.path.dirname(__file__), filename)
        parser = JobParser()
        try:
            with open(kvm_yaml) as sample_job_data:
                job = parser.parse(sample_job_data, device, 4212, None, output_dir=output_dir)
        except NotImplementedError:
            # some deployments listed in basics.yaml are not implemented yet
            return None
        return job


class TestPipeline(unittest.TestCase):  # pylint: disable=too-many-public-methods

    class FakeAction(Action):

        def __init__(self):
            self.ran = False
            super(TestPipeline.FakeAction, self).__init__()
            self.name = "fake-action"

        def run(self, connection, args=None):
            time.sleep(1)
            self.ran = True

    def test_create_empty_pipeline(self):
        pipe = Pipeline()
        self.assertEqual(pipe.children, {pipe: []})

    def test_add_action_to_pipeline(self):
        action = Action()
        action.name = "test-action"
        action.description = "test action only"
        action.summary = "starter"
        self.assertEqual(action.description, "test action only")
        self.assertEqual(action.summary, "starter")
        # action needs to be added to a top level pipe first
        with self.assertRaises(RuntimeError):
            Pipeline(action)
        pipe = Pipeline()
        with self.assertRaises(RuntimeError):
            pipe.add_action(None)
        with self.assertRaises(RuntimeError):
            pipe.add_action(pipe)
        pipe.add_action(action)
        self.assertNotEqual(pipe.children, {pipe: []})
        self.assertEqual(pipe.children, {pipe: [action]})
        self.assertEqual(action.level, "1")
        try:
            simplejson.loads(pipe.describe())
        except:  # pylint: disable=bare-except
            self.assertFalse(0)

    def test_create_internal_pipeline(self):
        action = Action()
        action.name = "internal_pipe"
        action.description = "test action only"
        action.summary = "starter"
        pipe = Pipeline()
        pipe.add_action(action)
        self.assertEqual(len(pipe.children[pipe]), 1)
        self.assertEqual(action.level, "1")
        action = Action()
        action.name = "child_action"
        action.summary = "child"
        action.description = "action implementing an internal pipe"
        with self.assertRaises(RuntimeError):
            Pipeline(action)
        pipe.add_action(action)
        self.assertEqual(action.level, "2")
        self.assertEqual(len(pipe.children[pipe]), 2)
        # a formal RetryAction would contain a pre-built pipeline which can be inserted directly
        retry_pipe = Pipeline(action)
        action = Action()
        action.name = "inside_action"
        action.description = "action inside the internal pipe"
        action.summary = "child"
        retry_pipe.add_action(action)
        self.assertEqual(len(retry_pipe.children[retry_pipe]), 1)
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
        job = factory.create_kvm_job('sample_jobs/basics.yaml', mkdtemp())
        if not job:
            return unittest.skip("not all deployments have been implemented")
        self.assertIsNotNone(job)

    def test_describe(self):
        factory = Factory()
        job = factory.create_kvm_job('sample_jobs/kvm.yaml', mkdtemp())
        self.assertIsNotNone(job)
        pipe = job.pipeline.describe()
        for item in pipe:
            self.assertNotIn('match', item)
            if 'pipeline' in item:
                for element in item['pipeline']:
                    self.assertNotIn('match', element)


class TestFakeActions(unittest.TestCase):  # pylint: disable=too-many-public-methods

    class KeepConnection(Action):  # pylint: disable=abstract-class-not-used
        def __init__(self):
            super(TestFakeActions.KeepConnection, self).__init__()
            self.name = "keep-connection"

        def run(self, connection, args=None):
            pass

        def post_process(self):
            raise NotImplementedError("invalid")

    class MakeNewConnection(Action):
        def __init__(self):
            super(TestFakeActions.MakeNewConnection, self).__init__()
            self.name = "make-new-connection"

        def run(self, connection, args=None):
            new_connection = object()
            return new_connection

    def setUp(self):
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
        pipe.run_actions(None)
        self.assertTrue(self.sub0.ran)
        self.assertTrue(self.sub1.ran)
        self.assertNotEqual(self.sub0.elapsed_time, 0)
        self.assertNotEqual(self.sub1.elapsed_time, 0)

    def test_keep_connection(self):

        pipe = Pipeline()
        pipe.add_action(TestFakeActions.KeepConnection())
        conn = object()
        self.assertIs(conn, pipe.run_actions(conn))

    def test_change_connection(self):

        pipe = Pipeline()
        pipe.add_action(TestFakeActions.MakeNewConnection())
        conn = object()
        self.assertIsNot(conn, pipe.run_actions(conn))
