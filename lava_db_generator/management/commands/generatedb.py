from django.core.management.base import BaseCommand

from lava_db_generator.factories import UserFactory, TestJobFactory


class Command(BaseCommand):
    help = "Generates dummy database"

    def add_arguments(self, parser):
        parser.add_argument("jobs", type=int)

    def handle(self, *args, **options):
        user = UserFactory()
        TestJobFactory.create_batch(size=options["jobs"], submitter=user)
