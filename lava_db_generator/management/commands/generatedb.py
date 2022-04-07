import random

from django.core.management.base import BaseCommand

from lava_db_generator.factories import (
    DeviceTypeFactory,
    DeviceFactory,
    UserFactory,
    GroupFactory,
    ProjectGroupFactory,
    TestJobFactory,
    TestJobWithActualDevice,
)


class Command(BaseCommand):
    help = "Generates dummy database"

    def add_arguments(self, parser):
        parser.add_argument(
            "--number-of-generated-device-types",
            metavar="SIZE",
            required=True,
            type=int,
        )
        parser.add_argument(
            "--number-of-generated-devices",
            metavar="SIZE",
            required=True,
            type=int,
        )
        parser.add_argument(
            "--number-of-generated-users",
            metavar="SIZE",
            required=True,
            type=int,
        )
        parser.add_argument(
            "--number-of-generated-groups",
            metavar="SIZE",
            required=True,
            type=int,
        )
        parser.add_argument(
            "--number-of-generated-project-groups",
            metavar="SIZE",
            required=True,
            type=int,
        )
        parser.add_argument(
            "--ratio-of-jobs-beloning-to-projects",
            metavar="RATIO",
            required=True,
            type=float,
        )
        parser.add_argument(
            "--number-of-projects-that-can-have-jobs",
            metavar="SIZE",
            type=int,
            required=True,
            nargs="*",
        )
        parser.add_argument(
            "--ratio-of-jobs-with-actual-devices",
            metavar="SIZE",
            required=True,
            type=float,
        )
        parser.add_argument(
            "--number-of-test-jobs",
            metavar="SIZE",
            required=True,
            type=int,
        )

    def handle(self, *args, **options):
        DeviceTypeFactory.create_batch(
            size=options["number_of_generated_device_types"])
        DeviceFactory.create_batch(
            size=options["number_of_generated_devices"])

        UserFactory.create_batch(
            size=options["number_of_generated_users"])
        GroupFactory.create_batch(
            size=options["number_of_generated_groups"])
        pgs = ProjectGroupFactory.create_batch(
            size=options["number_of_generated_project_groups"])

        project_ratios = options["number_of_projects_that_can_have_jobs"]
        projects = pgs[: len(project_ratios)]
        for _ in range(options["number_of_test_jobs"]):
            if random.random() < options["ratio_of_jobs_with_actual_devices"]:
                TestJobFactory()
            else:
                if (random.random()
                        <
                        options["ratio_of_jobs_beloning_to_projects"]):
                    vg = random.choices(projects, project_ratios)[0]
                    TestJobWithActualDevice(viewing_groups=vg)
                else:
                    TestJobWithActualDevice()
