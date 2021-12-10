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
        parser.add_argument("--device_type", metavar="SIZE", type=int)
        parser.add_argument("--device", metavar="SIZE", type=int)
        parser.add_argument("--auth_user", metavar="SIZE", type=int)
        parser.add_argument("--auth_group", metavar="SIZE", type=int)
        parser.add_argument("--project_group", metavar="SIZE", type=int)
        parser.add_argument("--project_group_ratio", metavar="SIZE", type=float)
        parser.add_argument("--project_ratios", metavar="SIZE", type=int, nargs="*")
        parser.add_argument("--scheduled_ratio", metavar="SIZE", type=float)
        parser.add_argument("--testjob", metavar="SIZE", type=int)

    def handle(self, *args, **options):
        DeviceTypeFactory.create_batch(size=options["device_type"])
        DeviceFactory.create_batch(size=options["device"])

        UserFactory.create_batch(size=options["auth_user"])
        GroupFactory.create_batch(size=options["auth_group"])
        pgs = ProjectGroupFactory.create_batch(size=options["project_group"])

        project_ratios = options["project_ratios"]
        projects = pgs[: len(project_ratios)]
        for _ in range(options["testjob"]):
            if random.random() < options["scheduled_ratio"]:
                TestJobFactory()
            else:
                if random.random() < options["project_group_ratio"]:
                    vg = random.choices(projects, project_ratios)[0]
                    TestJobWithActualDevice(viewing_groups=vg)
                else:
                    TestJobWithActualDevice()
