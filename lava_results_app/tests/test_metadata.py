import yaml
from lava_results_app.tests.test_names import TestCaseWithFactory
from lava_scheduler_app.models import (
    TestJob,
    Device,
)
from lava_results_app.dbutils import map_metadata
from lava_results_app.models import ActionData, MetaType, TestData
from lava_dispatcher.pipeline.parser import JobParser
from lava_dispatcher.pipeline.device import PipelineDevice


# pylint: disable=invalid-name,too-few-public-methods,too-many-public-methods,no-member,too-many-ancestors


class TestMetaTypes(TestCaseWithFactory):
    """
    MetaType and ActionData generation
    """
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
