import unittest


def suite():
    return unittest.TestLoader().discover("lava_scheduler_daemon.tests", pattern="*.py", top_level_dir="lava_scheduler_daemon")
