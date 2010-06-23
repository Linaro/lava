#!/usr/bin/env python
"""
Helper script for runnint launch_control tests
"""

import unittest

if __name__ == "__main__":
    # XXX: Hack, this is related to the fact that unittest uses
    # __import__() and does not use fromlist=[''] to import packages
    # correctly. Fortunately (?) python imports sub-packages when the
    # package itself is already imported. This is ugly but it works
    import launch_control.tests
    unittest.main(defaultTest='launch_control.tests.test_suite')
