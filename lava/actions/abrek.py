#!/usr/bin/python
from lava.actions import BaseAction
from lava.client import OperationFailed

class cmd_test_abrek(BaseAction):
    def run(self, test_name, timeout=-1):
        print "abrek run %s" % test_name

        #Make sure in test image now, abrek will install in master image
        self.in_test_shell()

        self.test_abrek(self, test_name, timeout)

    def test_abrek(self, test_name, timeout):
        """
        Invoke test suite by abrek
        """
        self.client.run_shell_command('abrek run %s' % test_name,
            response = self.tester_str, timeout)

    """
    Define tester_str temply, should be a constant imported from other module
    """
    tester_str = "root@localhost:"
