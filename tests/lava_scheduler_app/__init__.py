import unittest


def suite():
    return unittest.TestLoader().discover(
        "tests.lava_scheduler_app", pattern="*.py", top_level_dir="lava_scheduler_app"
    )
