import random

from django.core.management.base import BaseCommand

from lava_db_generator.factories import (
    DeviceTypeFactory,
    DeviceFactory,
    UserFactory,
    ProjectGroupFactory,
    TestJobWithActualDevice,
)


class Command(BaseCommand):
    help = "Generates dummy database"

    def add_arguments(self, parser):
        parser.add_argument(
            "--number-of-generated-device-types",
            metavar="SIZE",
            default=0,
            type=int,
        )
        parser.add_argument(
            "--number-of-generated-devices",
            metavar="SIZE",
            default=0,
            type=int,
        )
        parser.add_argument(
            "--number-of-generated-users",
            metavar="SIZE",
            default=0,
            type=int,
        )
        parser.add_argument(
            "--number-of-generated-project-groups",
            metavar="SIZE",
            default=0,
            type=int,
        )
        parser.add_argument(
            "--number-of-test-jobs",
            metavar="SIZE",
            default=0,
            type=int,
        )

    def handle(self, *args, **options):
        DeviceTypeFactory.create_batch(
            size=options["number_of_generated_device_types"])
        DeviceFactory.create_batch(
            size=options["number_of_generated_devices"])

        UserFactory.create_batch(
            size=options["number_of_generated_users"])
        projects = ProjectGroupFactory.create_batch(
            size=options["number_of_generated_project_groups"])

        for _ in range(options["number_of_test_jobs"]):
            vg = random.choice(projects)
            TestJobWithActualDevice(viewing_groups=vg)
