from django.test import SimpleTestCase

from lava_db_generator.factories import UserFactory, TestJobFactory


class FillTestCase(SimpleTestCase):
    databases = "__all__"

    def tearDown(self):
        pass

    @classmethod
    def tearDownClass(cls):
        pass


class TestFillTestJobs(FillTestCase):
    def setUp(self):
        self.user = UserFactory()

    def test_job_limit(self):
        TestJobFactory.create_batch(size=100000, submitter=self.user)
