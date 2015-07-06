import os
import yaml
import decimal
import unittest
from lava_results_app.tests.test_names import TestCaseWithFactory
from lava_scheduler_app.models import (
    TestJob,
    Device,
)
from lava_results_app.dbutils import map_metadata, testcase_export_fields, export_testcase
from lava_results_app.models import ActionData, MetaType, TestData, TestCase, TestSuite
from lava_dispatcher.pipeline.parser import JobParser
from lava_dispatcher.pipeline.device import PipelineDevice


# pylint: disable=invalid-name,too-few-public-methods,too-many-public-methods,no-member,too-many-ancestors


class TestMetaTypes(TestCaseWithFactory):
    """
    MetaType and ActionData generation
    Needs to skip if no /dev/loop0 as it tests job validation
    """
    @unittest.skipIf(not os.path.exists('/dev/loop0'), "loopback support not found")
    def test_job(self):
        user = self.factory.make_user()
        job = TestJob.from_yaml_and_user(
            self.factory.make_job_yaml(), user)
        job_def = yaml.load(job.definition)
        job_ctx = job_def.get('context', {})
        device = Device.objects.get(hostname='fakeqemu1')
        device_config = device.load_device_configuration(job_ctx)  # raw dict
        parser = JobParser()
        obj = PipelineDevice(device_config, device.hostname)
        pipeline_job = parser.parse(job.definition, obj, job.id, None, output_dir='/tmp')
        pipeline_job.pipeline.validate_actions()
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
        for testdata in job.test_data.all():
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
        user = self.factory.make_user()
        job = TestJob.from_yaml_and_user(
            self.factory.make_job_yaml(), user)
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
        user = self.factory.make_user()
        job = TestJob.from_yaml_and_user(
            self.factory.make_job_yaml(), user)
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
