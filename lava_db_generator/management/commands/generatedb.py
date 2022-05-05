from __future__ import annotations
from django.core.management.base import BaseCommand

from lava_db_generator.factories import (
    DeviceTypeFactory,
    DeviceFactory,
    UserFactory,
    ProjectGroupFactory,
    TestJobFactory,
)
from argparse import ArgumentParser


class Command(BaseCommand):
    help = "Generates dummy database"

    def add_arguments(self, parser: ArgumentParser):
        subparsers = parser.add_subparsers(required=True)

        # Device Types
        device_type_subparser = subparsers.add_parser('device-type')
        device_type_subparser.add_argument(
            "number_generated",
            metavar="SIZE",
            type=int,
        )
        device_type_subparser.set_defaults(func=generate_device_types)

        # Devices
        device_subparser = subparsers.add_parser('device')
        device_subparser.add_argument(
            "number_generated",
            metavar="SIZE",
            type=int,
        )
        device_subparser.set_defaults(func=generate_devices)

        # Project
        project_subparser = subparsers.add_parser('project')
        project_subparser.add_argument(
            "number_generated",
            metavar="SIZE",
            type=int,
        )
        project_subparser.set_defaults(func=generate_projects)

        # User
        user_subparser = subparsers.add_parser('user')
        user_subparser.add_argument(
            "number_generated",
            metavar="SIZE",
            type=int,
        )
        user_subparser.add_argument(
            '--number-of-particpated-projects',
            type=int,
            default=0,
        )
        user_subparser.set_defaults(func=generate_users)

        # Testjob
        testjob_subparser = subparsers.add_parser('testjob')
        testjob_subparser.add_argument(
            "number_generated",
            metavar="SIZE",
            type=int,
        )
        testjob_subparser.add_argument(
            "--is-private",
            action='store_true',
        )
        testjob_subparser.add_argument(
            "--number-of-particpated-projects",
            default=0,
            type=int,
        )
        testjob_subparser.add_argument(
            "--is-submitter-lava-health",
            default=False,
            type=bool,
        )
        testjob_subparser.set_defaults(func=generate_testjobs)

    def handle(self, *args, **options):
        func = options.pop("func")
        func(*args, **options)


def generate_device_types(number_generated: int, **kwargs) -> None:
    DeviceTypeFactory.create_batch(
            size=number_generated)


def generate_devices(number_generated: int, **kwargs) -> None:
    DeviceFactory.create_batch(
            size=number_generated)


def generate_users(number_generated: int,
                   number_of_particpated_projects: int,
                   **kwargs) -> None:
    UserFactory.create_batch(
            size=number_generated,
            number_of_particpated_projects=number_of_particpated_projects)


def generate_projects(number_generated: int, **kwargs) -> None:
    ProjectGroupFactory.create_batch(
            size=number_generated)


def generate_testjobs(number_generated: int,
                      is_private: bool,
                      number_of_particpated_projects: int,
                      is_submitter_lava_health: bool,
                      **kwargs,
                      ) -> None:

    TestJobFactory.create_batch(
            size=number_generated,
            is_public=(not is_private),
            number_of_particpated_projects=number_of_particpated_projects,
            is_submitter_lava_health=is_submitter_lava_health)
