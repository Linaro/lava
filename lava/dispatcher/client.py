import pexpect
import sys
import time
from cStringIO import StringIO

from lava.dispatcher.config import (
    BOARDS,
    LAVA_SERVER_IP,
    MASTER_STR,
    TESTER_STR,
    )


class LavaClient(object):
    def __init__(self, hostname):
        cmd = "conmux-console %s" % hostname
        self.sio = SerialIO(sys.stdout)
        self.proc = pexpect.spawn(cmd, timeout=3600, logfile=self.sio)
        #serial can be slow, races do funny things if you don't increase delay
        self.proc.delaybeforesend=1
        self.hostname = hostname
        # will eventually come from the database
        self.board = BOARDS[hostname]

    def in_master_shell(self):
        """ Check that we are in a shell on the master image
        """
        self.proc.sendline("")
        id = self.proc.expect([MASTER_STR, pexpect.TIMEOUT])
        if id == 1:
            raise OperationFailed

    def in_test_shell(self):
        """ Check that we are in a shell on the test image
        """
        self.proc.sendline("")
        id = self.proc.expect([TESTER_STR, pexpect.TIMEOUT])
        if id == 1:
            raise OperationFailed

    def boot_master_image(self):
        """ reboot the system, and check that we are in a master shell
        """
        self.soft_reboot()
        try:
            self.proc.expect("Starting kernel")
            self.in_master_shell()
        except:
            self.hard_reboot()
            try:
                self.in_master_shell()
            except:
                raise

    def boot_linaro_image(self):
        """ Reboot the system to the test image
        """
        self.soft_reboot()
        try:
            self.enter_uboot()
        except:
            self.hard_reboot()
            self.enter_uboot()
        uboot_cmds = self.board.uboot_cmds
        self.proc.sendline(uboot_cmds[0])
        for line in range(1, len(uboot_cmds)):
            if self.board.type in ["mx51evk", "mx53loco"]:
                self.proc.expect(">")
            else:
                self.proc.expect("#")
            self.proc.sendline(uboot_cmds[line])
        self.in_test_shell()

    def enter_uboot(self):
        self.proc.expect("Hit any key to stop autoboot")
        self.proc.sendline("")

    def soft_reboot(self):
        self.proc.sendline("reboot")

    def hard_reboot(self):
        self.proc.send("~$")
        self.proc.sendline("hardreset")

    def run_shell_command(self, cmd, response=None, timeout=-1):
        self.proc.sendline(cmd)
        if response:
            self.proc.expect(response, timeout=timeout)

    def check_network_up(self):
        self.proc.sendline("LC_ALL=C ping -W4 -c1 %s" % LAVA_SERVER_IP)
        id = self.proc.expect(["1 received", "0 received",
            "Network is unreachable"], timeout=5)
        self.proc.expect(MASTER_STR)
        if id == 0:
            return True
        else:
            return False

    def wait_network_up(self, timeout=60):
        now = time.time()
        while time.time() < now+timeout:
            if self.check_network_up():
                return
        raise NetworkError

    def export_display(self):
        #export the display, ignore errors on non-graphical images
        self.run_shell_command("su - linaro -c 'DISPLAY=:0 xhost local:'",
            response=TESTER_STR)
        self.run_shell_command("export DISPLAY=:0", response=TESTER_STR)

    def get_seriallog(self):
        return self.sio.getvalue()


class SerialIO(file):
    def __init__(self, logfile):
        self.serialio = StringIO()
        self.logfile = logfile

    def write(self, text):
        self.serialio.write(text)
        self.logfile.write(text)

    def close(self):
        self.serialio.close()
        self.logfile.close()

    def flush(self):
        self.logfile.flush()

    def getvalue(self):
        return self.serialio.getvalue()

class DispatcherError(Exception):
    """
    Base exception and error class for dispatcher
    """
    def __init__(self, err_action=None):
        if err_action:
            self.err_action = err_action

class CriticalError(DispatcherError):
    """
    The critical error
    """

class GeneralError(DispatcherError):
    """
    The non-critical error
    """

class NetworkError(CriticalError):
    """
    This is used when a network error occurs, such as failing to bring up
    the network interface on the client
    """

class OperationFailed(GeneralError):
    pass

