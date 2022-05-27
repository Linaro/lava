from __future__ import annotations
from django.core.management.base import BaseCommand
from argparse import ArgumentParser


def profiling_helper(function):
    from cProfile import Profile
    from pstats import Stats

    with Profile() as pr:
        function()

    stats = Stats(pr)

    return stats


class Command(BaseCommand):
    help = "Run simulation"

    def add_arguments(self, parser: ArgumentParser):
        parser.add_argument("simulation_name")

    def handle(self, *args, **options):
        simulation_name = options['simulation_name']

        if simulation_name == 'scheduler':
            simulate_scheduler()
        else:
            raise ValueError("Unknown simulation")


def simulate_scheduler() -> None:
    from lava_scheduler_app.models import Device, DeviceType, Worker
    from logging import getLogger, INFO

    logger = getLogger('scheduler simulation')
    logger.setLevel(INFO)
    workers = set(Worker.objects.all())
    device_types = set(DeviceType.objects.all())

    from lava_scheduler_app.scheduler import schedule

    logger.info("Pre-cache device templates")
    for device in Device.objects.all():
        device.is_valid()
    logger.info("Pre-cache complete")

    schedule(logger, device_types, workers)
