import os
import unittest

from lava_scheduler_app.models import Device


def suite():
    return unittest.TestLoader().discover(
        "lava_results_app.tests", pattern="*.py", top_level_dir="lava_results_app"
    )
