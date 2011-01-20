import pexpect

class SerialClient:
    def __init__(self, hostname):
        cmd = "console %s" % hostname
        self.proc = pexpect.spawn(cmd, timeout=30)

    def in_master_shell(self):
        """ Check that we are in a shell on the master image
        """
        self.proc.sendline("")
        id = self.proc.expect(['root@localhost:~#', pexpect.TIMEOUT])
        if id == 0:
            return True
        if id == 1:
            return False

    def recover_machine(self):
        """ reboot the system, and check that we are in a master shell
        """
        self.soft_reboot()
        if not self.in_master_shell():
            self.hard_reboot()
        if self.in_master_shell():
            return True
        return False

    def soft_reboot(self):
        self.proc.sendline("reboot")

    def hard_reboot(self):
        self.proc.send("~$")
        self.proc.sendline("hardreset")

