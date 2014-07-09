import sys
import os
from StringIO import StringIO
import unittest
import yaml

from lava_dispatcher.pipeline import Pipeline, Action
from lava_dispatcher.pipeline.parser import JobParser
from lava_dispatcher.pipeline.job import Job
from lava_dispatcher.tests.helper import create_device_config, create_config
from lava_dispatcher.config import get_config
from lava_dispatcher.context import LavaContext
from lava_dispatcher.device.qemu import QEMUTarget


class TestAction(unittest.TestCase):

    def test_references_a_device(self):
        device = object()
        cmd = Action()
        cmd.device = device
        self.assertIs(cmd.device, device)


class TestPipelineInit(unittest.TestCase):

    class FakeAction(Action):

        def __init__(self):
            self.ran = False
            super(FakeAction, self).__init__(None)

        def run(self, connection, args=None):
            self.ran = True

    def setUp(self):
        self.sub0 = TestPipelineInit.FakeAction()
        self.sub1 = TestPipelineInit.FakeAction()


class TestJobParser(unittest.TestCase):

    def setUp(self):
        factory = Factory()
        self.job = factory.create_job('sample_jobs/basics.yaml')

    def test_parser_creates_a_job_with_a_pipeline(self):
        self.assertIsInstance(self.job, Job)
        self.assertIsInstance(self.job.pipeline, Pipeline)

    def test_pipeline_gets_multiple_actions_in_it(self):
        self.assertTrue(self.job.actions > 1)

# FIXME: disabled as the current parser relies on a real file, not a string.
# class TestJobSnippet(unittest.TestCase):

#    def setUp(self):
#        factory = Factory()
#        fake_qemu = os.path.join(os.path.dirname(__file__), '..', '..', 'tests', 'test-config', 'bin', 'fake-qemu')
#        device = factory.create_kvm_target({'qemu-binary': fake_qemu})
#        self.parser = JobParser()
#        self.job = self.parser.parse(self.boot_from_sata, device)

#    def boot_from_sata(self):
#        return StringIO({
#            'actions': [
#                {'deploy': {'to': 'sata', 'image': 'file:///path/to/image.img'}},
#            ]
#        })

#    def test_boot_from_sata(self):
#        self.assertEquals(1, len(self.job.actions))
#        self.assertEquals(self.job.actions[self.job.pipeline][0].level, "1")

#    def test_action_data(self):
#        deploy_action = self.job.actions[self.job.pipeline][0]
#        self.assertEqual(type(deploy_action), DeployAction)
#        self.assertEquals('sata', deploy_action.parameters['to'])
#        self.assertEquals('file:///path/to/image.img', deploy_action.parameters['image'])

#    def test_action_class(self):
#        job = self.parser.parse(self.boot_from_sata)
#        deploy_action = job.actions[job.pipeline][0]
#
#        self.assertIsInstance(deploy_action, DeployAction)


class TestValidation(unittest.TestCase):

    def test_action_is_valid_if_there_are_not_errors(self):
        action = Action()
        action.__errors__ = [1]
        self.assertFalse(action.valid)
        action.__errors__ = []
        self.assertTrue(action.valid)

    def test_composite_action_aggregates_errors_from_sub_actions(self):
        sub1 = Action()
        sub1.__errors__ = [1]
        sub2 = Action()
        sub2.name = "sub2"
        sub2.__errors__ = [2]

        pipe = Pipeline()
        self.assertRaises(RuntimeError, pipe.add_action, sub1)
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
    def create_kvm_target(self, extra_device_config=None):
        if not extra_device_config:
            extra_device_config = {}
        create_config('lava-dispatcher.conf', {})

        device_config_data = {'device_type': 'kvm'}
        device_config_data.update(extra_device_config)
        device_config = create_device_config('fakekvm', device_config_data)  # use a device name unlikely to exist

        dispatcher_config = get_config()

        context = LavaContext('fakekvm', dispatcher_config, None, None, None)
        return QEMUTarget(context, device_config)

    def create_fake_qemu_job(self):
        factory = Factory()
        fake_qemu = os.path.join(os.path.dirname(__file__), '..', '..', 'tests', 'test-config', 'bin', 'fake-qemu')
        device = factory.create_kvm_target({'qemu-binary': fake_qemu})
        sample_job_file = os.path.join(os.path.dirname(__file__), 'sample_jobs/basics.yaml')
        self.sample_job_data = open(sample_job_file)
        self.parser = JobParser()
        job = self.parser.parse(self.sample_job_data, device)
        return job

    def create_job(self, filename, output_dir=None):
        device = self.create_kvm_target()
        kvm_yaml = os.path.join(os.path.dirname(__file__), filename)
        self.sample_job_data = open(kvm_yaml)
        self.parser = JobParser()
        job = self.parser.parse(self.sample_job_data, device, output_dir)
        job.context = LavaContext(device.config.hostname, get_config(), sys.stderr, job.parameters, '/tmp')
        return job


class TestPipeline(unittest.TestCase):

    class FakeAction(Action):

        def __init__(self):
            self.ran = False
            super(TestPipeline.FakeAction, self).__init__()
            self.name = "fake-action"

        def run(self, connection, args=None):
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
        except:
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
        self.assertEqual(len(pipe.describe().values()), 8)

    def test_simulated_action(self):
        factory = Factory()
        job = factory.create_job('sample_jobs/basics.yaml')
        # uncomment to see the YAML dump of the pipeline.
        # print yaml.dump(job.pipeline.describe())


class TestFakeActions(unittest.TestCase):

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
        self.assertNotEqual(self.sub0.elapsed_time, False)
        self.assertNotEqual(self.sub1.elapsed_time, False)

    def test_prepare(self):
        class PrepareAction(Action):

            def __init__(self, pipeline):
                self.called = False
                super(PrepareAction, self).__init__()
                self.name = "prepare"

            def prepare(self):
                self.called = True

        pipe = Pipeline()
        prepare = PrepareAction(pipe)
        pipe.add_action(prepare)
        pipe.prepare_actions()
        self.assertTrue(prepare.called)

    def test_post_process(self):

        class PostProcess(Action):

            def __init__(self, pipeline):
                self.called = False
                super(PostProcess, self).__init__()
                self.name = "post-process"

            def post_process(self):
                self.called = True

        pipe = Pipeline()
        post_process = PostProcess(pipe)
        pipe.add_action(post_process)
        pipe.post_process_actions()
        self.assertTrue(post_process.called)

    def test_keep_connection(self):
        class KeepConnection(Action):
            def __init__(self):
                super(KeepConnection, self).__init__()
                self.name = "keep-connection"

            def run(self, connection, args=None):
                pass

        pipe = Pipeline()
        pipe.add_action(KeepConnection())
        conn = object()
        self.assertIs(conn, pipe.run_actions(conn))

    def test_change_connection(self):
        class MakeNewConnection(Action):
            def __init__(self):
                super(MakeNewConnection, self).__init__()
                self.name = "make-new-connection"

            def run(self, connection, args=None):
                new_connection = object()
                return new_connection

        pipe = Pipeline()
        pipe.add_action(MakeNewConnection())
        conn = object()
        self.assertIsNot(conn, pipe.run_actions(conn))
