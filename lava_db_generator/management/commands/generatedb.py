from django.core.management.base import BaseCommand

from lava_db_generator.factories import UserFactory, TestJobFactory


class Command(BaseCommand):
    help = "Generates dummy database"

    def add_arguments(self, parser):
        parser.add_argument("users", type=int)
        parser.add_argument("jobs", type=int)

    def handle(self, *args, **options):
        UserFactory.create_batch(size=options["users"])
        TestJobFactory.create_batch(size=options["jobs"])
