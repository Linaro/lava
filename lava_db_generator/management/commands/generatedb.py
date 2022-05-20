from __future__ import annotations
from django.core.management.base import BaseCommand

from lava_scheduler_app.models import TestJob, Device
from lava_db_generator.factories import (
    DeviceTypeFactory,
    DeviceFactory,
    UserFactory,
    ProjectGroupFactory,
    TestJobFactory,
    WorkerFactory,
)
from argparse import ArgumentParser
import factory
from django.contrib.auth.models import User
from typing import Optional


class Command(BaseCommand):
    help = "Generates dummy database"

    def add_arguments(self, parser: ArgumentParser):
        subparsers = parser.add_subparsers(required=True)

        # Worker
        worker_subparser = subparsers.add_parser("worker")
        worker_subparser.add_argument(
            "number_generated",
            metavar="SIZE",
            type=int,
        )
        worker_subparser.set_defaults(func=generate_workers)

        # Device Types
        device_type_subparser = subparsers.add_parser("device-type")
        device_type_subparser.add_argument(
            "number_generated",
            metavar="SIZE",
            type=int,
        )
        device_type_subparser.set_defaults(func=generate_device_types)

        # Devices
        device_subparser = subparsers.add_parser("device")
        device_subparser.add_argument(
            "number_generated",
            metavar="SIZE",
            type=int,
        )
        device_subparser.add_argument("--device-health")
        device_subparser.add_argument("--device-state")
        device_subparser.set_defaults(func=generate_devices)

        # Project
        project_subparser = subparsers.add_parser("project")
        project_subparser.add_argument(
            "number_generated",
            metavar="SIZE",
            type=int,
        )
        project_subparser.set_defaults(func=generate_projects)

        # User
        user_subparser = subparsers.add_parser("user")
        user_subparser.add_argument(
            "number_generated",
            metavar="SIZE",
            type=int,
        )
        user_subparser.add_argument(
            "--number-of-particpated-projects",
            type=int,
            default=0,
        )
        user_subparser.add_argument(
            "--set-password-to",
        )
        user_subparser.add_argument(
            "--username-sequence",
        )
        user_subparser.set_defaults(func=generate_users)

        # Testjob
        testjob_subparser = subparsers.add_parser("testjob")
        testjob_subparser.add_argument(
            "number_generated",
            metavar="SIZE",
            type=int,
        )
        testjob_subparser.add_argument(
            "--is-private",
            action="store_true",
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
        testjob_subparser.add_argument(
            "--job-state",
        )
        testjob_subparser.set_defaults(func=generate_testjobs)

        scenario_subparser = subparsers.add_parser("scenario")
        scenario_subparser.add_argument("scenario_name")
        scenario_subparser.set_defaults(func=generate_scenario)

    def handle(self, *args, **options):
        func = options.pop("func")
        func(*args, **options)


def generate_scenario(scenario_name: str, **kwargs) -> None:
    if scenario_name == "viewing_groups_test":
        generate_workers(2)
        generate_device_types(300)
        generate_devices(1000)
        generate_projects(100)
        generate_users(300, 1)
        generate_testjobs(
            200_000,
            is_private=False,
            number_of_particpated_projects=1,
            is_submitter_lava_health=True,
        )
    elif scenario_name == "scheduler_test":
        generate_workers(3)
        generate_device_types(300)
        generate_devices(1000, device_health="HEALTH_GOOD", device_state="STATE_IDLE")
        generate_projects(100)
        generate_users(300, 0)
        generate_testjobs(
            100_000,
            is_private=False,
            job_state="STATE_SUBMITTED",
        )
    else:
        raise ValueError("Unknown scenario.")


def generate_workers(number_generated: int, **kwargs) -> None:
    WorkerFactory.create_batch(
        size=number_generated,
    )


def generate_device_types(number_generated: int, **kwargs) -> None:
    DeviceTypeFactory.create_batch(size=number_generated)


def generate_devices(
    number_generated: int,
    device_health: Optional[str] = None,
    device_state: Optional[str] = None,
    **kwargs,
) -> None:
    options = {
        "size": number_generated,
    }

    if device_health is not None:
        options["health"] = getattr(Device, device_health)

    if device_state is not None:
        options["state"] = getattr(Device, device_state)

    DeviceFactory.create_batch(size=number_generated)


def generate_users(
    number_generated: int,
    number_of_particpated_projects: int = 0,
    set_password_to: Optional[str] = None,
    username_sequence: Optional[str] = None,
    **kwargs,
) -> None:

    options = {
        "size": number_generated,
        "number_of_particpated_projects": number_of_particpated_projects,
    }

    if set_password_to is not None:
        options["set_password_to"] = set_password_to

    if username_sequence is not None:
        options["username"] = factory.Sequence(lambda n: f"{username_sequence}{n}")

    UserFactory.create_batch(**options)


def generate_projects(number_generated: int, **kwargs) -> None:
    ProjectGroupFactory.create_batch(size=number_generated)


def generate_testjobs(
    number_generated: int,
    is_private: bool = False,
    number_of_particpated_projects: int = 0,
    is_submitter_lava_health: bool = False,
    job_state: Optional[str] = None,
    **kwargs,
) -> None:
    options = {
        "size": number_generated,
        "is_public": (not is_private),
        "number_of_particpated_projects": number_of_particpated_projects,
    }

    if is_submitter_lava_health:
        options["submitter"] = User.objects.filter(username="lava-health")[0]
    else:
        options["submitter"] = factory.fuzzy.FuzzyChoice(User.objects.all())

    if job_state is not None:
        options["state"] = getattr(TestJob, job_state)

    TestJobFactory.create_batch(**options)
