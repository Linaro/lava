#!/usr/bin/env python

import launch_control.tests.sample


from unittest import main, TestLoader
from doctest import DocTestSuite

class DocTestAwareTestLoader(TestLoader):
    """
    An extension to TestLoader that spots __doctest_module__
    attribute and uses it to load doctests
    """
    def loadTestsFromModule(self, module):
        suite = TestLoader.loadTestsFromModule(self, module)
        if hasattr(module, '__doctest_module__'):
            doc_suite = DocTestSuite(module.__doctest_module__)
            suite.addTest(doc_suite)
        return suite

if __name__ == "__main__":
    main(launch_control.tests.sample, testLoader=DocTestAwareTestLoader())
