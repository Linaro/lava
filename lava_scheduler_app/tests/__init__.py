import os
import unittest

from lava_scheduler_app.models import Device


def suite():
    return unittest.TestLoader().discover(
        "lava_scheduler_app.tests",
        pattern="*.py",
        top_level_dir="lava_scheduler_app"
    )


Device.CONFIG_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__),
                                                  "..", "..", "lava_scheduler_app",
                                                  "tests", "devices"))
