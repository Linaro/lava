import os
import yaml
import decimal
from django.core.exceptions import MultipleObjectsReturned
from lava_results_app.tests.test_names import TestCaseWithFactory
from lava_scheduler_app.models import (
    TestJob,
    Device,
)
from lava_results_app.dbutils import (
    map_metadata,
    _get_job_metadata, _get_device_metadata,  # pylint: disable=protected-access
    testcase_export_fields,
    export_testcase,
)
from lava_results_app.models import ActionData, MetaType, TestData, TestCase, TestSuite
from lava_dispatcher.pipeline.parser import JobParser
from lava_dispatcher.pipeline.device import PipelineDevice
from lava_dispatcher.pipeline.test.test_defs import allow_missing_path


# pylint: disable=invalid-name,too-few-public-methods,too-many-public-methods,no-member,too-many-ancestors


class TestMetaTypes(TestCaseWithFactory):
    """
    MetaType and ActionData generation
    """
    def test_job(self):
        MetaType.objects.all().delete()
        job = TestJob.from_yaml_and_user(
            self.factory.make_job_yaml(), self.user)
        job_def = yaml.load(job.definition)
        job_ctx = job_def.get('context', {})
        device = Device.objects.get(hostname='fakeqemu1')
        device_config = device.load_device_configuration(job_ctx, system=False)  # raw dict
        parser = JobParser()
        obj = PipelineDevice(device_config, device.hostname)
        pipeline_job = parser.parse(job.definition, obj, job.id, None, None, None, output_dir='/tmp')
        allow_missing_path(pipeline_job.pipeline.validate_actions, self,
                           'qemu-system-x86_64')
        pipeline = pipeline_job.describe()
        map_metadata(yaml.dump(pipeline), job)
        self.assertEqual(MetaType.objects.filter(metatype=MetaType.DEPLOY_TYPE).count(), 1)
        self.assertEqual(MetaType.objects.filter(metatype=MetaType.BOOT_TYPE).count(), 1)
        count = ActionData.objects.all().count()
        self.assertEqual(TestData.objects.all().count(), 1)
        testdata = TestData.objects.all()[0]
        self.assertEqual(testdata.testjob, job)
        for actionlevel in ActionData.objects.all():
            self.assertEqual(actionlevel.testdata, testdata)
        action_levels = []
        for testdata in job.testdata_set.all():
            action_levels.extend(testdata.actionlevels.all())
        self.assertEqual(count, len(action_levels))
        count = ActionData.objects.filter(meta_type__metatype=MetaType.DEPLOY_TYPE).count()
        self.assertNotEqual(ActionData.objects.filter(meta_type__metatype=MetaType.BOOT_TYPE).count(), 0)
        self.assertEqual(ActionData.objects.filter(meta_type__metatype=MetaType.UNKNOWN_TYPE).count(), 0)
        for actionlevel in ActionData.objects.filter(meta_type__metatype=MetaType.BOOT_TYPE):
            self.assertEqual(actionlevel.testdata.testjob.id, job.id)
        self.assertEqual(ActionData.objects.filter(
            meta_type__metatype=MetaType.DEPLOY_TYPE,
            testdata__testjob=job
        ).count(), count)

    def test_export(self):
        job = TestJob.from_yaml_and_user(
            self.factory.make_job_yaml(), self.user)
        test_suite = TestSuite.objects.get_or_create(name='lava', job=job)[0]
        test_case = TestCase(
            name='name',
            suite=test_suite,
            result=TestCase.RESULT_FAIL
        )
        self.assertTrue(
            any(
                map(lambda v: v in testcase_export_fields(), export_testcase(test_case).keys())
            )
        )

    def test_duration(self):
        TestJob.from_yaml_and_user(
            self.factory.make_job_yaml(), self.user)
        metatype = MetaType(name='fake', metatype=MetaType.DEPLOY_TYPE)
        metatype.save()
        action_data = ActionData(meta_type=metatype, action_level='1.2.3', action_name='fake')
        action_data.save()
        action_data.duration = '1.2'
        action_data.save(update_fields=['duration'])
        action_data = ActionData.objects.get(id=action_data.id)  # reload
        self.assertIsInstance(action_data.duration, decimal.Decimal)
        # unit tests check the instance as well as the value.
        self.assertEqual(float(action_data.duration), 1.2)
        action_data.timeout = 300
        action_data.save(update_fields=['timeout'])
        self.assertEqual(action_data.timeout, 300)

    def test_repositories(self):  # pylint: disable=too-many-locals
        job = TestJob.from_yaml_and_user(
            self.factory.make_job_yaml(), self.user)
        job_def = yaml.load(job.definition)
        job_ctx = job_def.get('context', {})
        device = Device.objects.get(hostname='fakeqemu1')
        device_config = device.load_device_configuration(job_ctx, system=False)  # raw dict
        parser = JobParser()
        obj = PipelineDevice(device_config, device.hostname)
        pipeline_job = parser.parse(job.definition, obj, job.id, None, None, None, output_dir='/tmp')
        allow_missing_path(pipeline_job.pipeline.validate_actions, self,
                           'qemu-system-x86_64')
        pipeline = pipeline_job.describe()
        device_values = _get_device_metadata(pipeline['device'])
        self.assertEqual(
            device_values,
            {'target.hostname': 'fakeqemu1', 'target.device_type': 'qemu'}
        )
        del pipeline['device']['device_type']
        self.assertNotIn('device_type', pipeline['device'])
        device_values = _get_device_metadata(pipeline['device'])
        try:
            testdata, _ = TestData.objects.get_or_create(testjob=job)
        except (MultipleObjectsReturned):
            self.fail('multiple objects')
        for key, value in device_values.items():
            if not key or not value:
                continue
            testdata.attributes.create(name=key, value=value)
        retval = _get_job_metadata(pipeline['job']['actions'])
        self.assertEqual(
            retval,
            {
                'test.1.definition.from': 'git',
                'test.0.definition.repository': 'git://git.linaro.org/qa/test-definitions.git',
                'test.0.definition.name': 'smoke-tests',
                'test.1.definition.repository': 'http://git.linaro.org/lava-team/lava-functional-tests.git',
                'boot.0.method': 'qemu',
                'test.1.definition.name': 'singlenode-advanced',
                'test.0.definition.from': 'git',
                'test.0.definition.path': 'ubuntu/smoke-tests-basic.yaml',
                'test.1.definition.path': 'lava-test-shell/single-node/singlenode03.yaml'}
        )

    def test_job_multi(self):
        MetaType.objects.all().delete()
        multi_test_file = os.path.join(os.path.dirname(__file__), 'multi-test.yaml')
        self.assertTrue(os.path.exists(multi_test_file))
        with open(multi_test_file, 'r') as test_support:
            data = test_support.read()
        job = TestJob.from_yaml_and_user(data, self.user)
        job_def = yaml.load(job.definition)
        job_ctx = job_def.get('context', {})
        device = Device.objects.get(hostname='fakeqemu1')
        device_config = device.load_device_configuration(job_ctx, system=False)  # raw dict
        parser = JobParser()
        obj = PipelineDevice(device_config, device.hostname)
        pipeline_job = parser.parse(job.definition, obj, job.id, None, None, None, output_dir='/tmp')
        allow_missing_path(pipeline_job.pipeline.validate_actions, self,
                           'qemu-system-x86_64')
        pipeline = pipeline_job.describe()
        map_metadata(yaml.dump(pipeline), job)
