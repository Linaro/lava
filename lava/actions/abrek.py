#!/usr/bin/python
from lava.actions import BaseAction
from lava.client import OperationFailed

class cmd_test_abrek(BaseAction):
    def run(self, test_name, timeout=-1):
        print "abrek run %s" % test_name

        #Make sure in test image now
        self.in_test_shell()

        self.install_test_suite(self, test_name)

        self.test_abrek(self, test_name, timeout)

    def install_test_suite(self, test_name):
        """
        Install test suite if not installed
        """
        rc = self.client.run_shell_command(
            'abrek list-installed | grep %s' % test_name,
            response = test_name, timeout=10)
        if not rc:
            #Is the installation time enough?
            self.client.run_shell_command(
                'abrek install %s' % test_name,
                response = self.tester_str, timeout=600)
        if not rc:
            raise OperationFailed("Install test suite")

    def test_abrek(self, test_name, timeout):
        """
        Invoke test suite by abrek
        """
        rc = self.client.run_shell_command('abrek run %s' % test_name,
            response = self.tester_str, timeout)
        if not rc:
            raise OperationFailed("Abrek run error with test suite %s" 
                    % test_name)

    """
    Define tester_str temply, should be a constant imported from other module
    """
    tester_str = "root@localhost:"
