import random

from django.core.management.base import BaseCommand

from lava_db_generator.factories import (
    UserFactory,
    GroupFactory,
    ProjectGroupFactory,
    TestJobFactory,
    TestJobWithViewingGroupFactory,
)


class Command(BaseCommand):
    help = "Generates dummy database"

    def add_arguments(self, parser):
        parser.add_argument("--auth_user", metavar="SIZE", type=int)
        parser.add_argument("--auth_group", metavar="SIZE", type=int)
        parser.add_argument("--project_group", metavar="SIZE", type=int)
        parser.add_argument("--project_group_ratio", metavar="SIZE", type=float)
        parser.add_argument("--project_ratios", metavar="SIZE", type=int, nargs="*")
        parser.add_argument("--testjob", metavar="SIZE", type=int)

    def handle(self, *args, **options):
        UserFactory.create_batch(size=options["auth_user"])
        GroupFactory.create_batch(size=options["auth_group"])
        pgs = ProjectGroupFactory.create_batch(size=options["project_group"])

        project_ratios = options["project_ratios"]
        projects = pgs[: len(project_ratios)]
        for _ in range(options["testjob"]):
            if random.random() < options["project_group_ratio"]:
                vg = random.choices(projects, project_ratios)[0]
                TestJobWithViewingGroupFactory(viewing_groups=vg)
            else:
                TestJobFactory()
