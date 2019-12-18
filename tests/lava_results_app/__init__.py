import os
import unittest

from lava_scheduler_app.models import Device


def suite():
    return unittest.TestLoader().discover(
        "tests.lava_results_app", pattern="*.py", top_level_dir="lava_results_app"
    )
