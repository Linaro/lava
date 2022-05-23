from __future__ import annotations
from django.core.management.base import BaseCommand
from argparse import ArgumentParser


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
    from lava_scheduler_app.models import DeviceType, Worker
    from logging import getLogger, DEBUG

    logger = getLogger('scheduler simulation')
    logger.setLevel(DEBUG)
    workers = set(Worker.objects.all())
    device_types = set(DeviceType.objects.all())

    from lava_scheduler_app.scheduler import schedule

    schedule(logger, device_types, workers)
