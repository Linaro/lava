# Copyright (C) 2011 Calxeda, Inc.
#
# This file is part of LAVA Dispatcher.
#
# LAVA Dispatcher is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# LAVA Dispatcher is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, see <http://www.gnu.org/licenses>.

import pexpect
import sys
from lava_dispatcher.config import get_host
from lava_dispatcher.client import LavaClient, SerialIO
from lava_dispatcher.qemu_config import QEMU_PATH, MASTER_STR, TESTER_STR


class LavaQEMUClient(LavaClient):

    def __init__(self, hostname):
        self.sio = SerialIO(sys.stdout)
        self.hostname = hostname
        self.host_config = get_host(hostname)
        
        self.start_qemu()

        # Should U-Boot automatically to master image
        self.proc.expect("Starting kernel")
        
        # will eventually come from the database
        self.board = self.board_type
        self._master_str = MASTER_STR
        self._tester_str = TESTER_STR
        self.in_master_shell()

    @property
    def macaddr(self):
        return self.host_config.get('qemu_macaddr')

    @property
    def disk(self):
        return self.host_config.get('qemu_disk')

    @property
    def board_type(self):
        return self.host_config.get('board_type')

    @property
    def vlan_number(self):
        return self.host_config.get('vlan_number')
   
    @property
    def boot_image(self):
        return self.host_config.get('boot_image')
    
    @property
    def machine_type(self):
        return self.host_config.get('machine_type')
    
    @property
    def additional_options(self):
        return self.host_config.get('additional_options')
    
    @property
    def network_arguments(self):
        if(self.vlan_number is not None and
           self.macaddr is not None):
            return ("-net nic,vlan=%d,macaddr=%s -net vde,vlan=%d " %
                    (self.vlan_number, self.macaddr, self.vlan_number))
        else:
            return ""
        
    @property
    def disk_arguments(self):
        if(self.disk is not None):
            return ('-drive id=disk,if=ide,file=%s '
                    '-device ide-drive,drive=disk,bus=ide.0' % self.disk)
        else:
            return ""

    def start_qemu(self):
        cmd = ("%sqemu-system-arm %s -M %s -kernel %s " %
               (QEMU_PATH, self.additional_options, self.machine_type, 
                self.boot_image))
        cmd += self.network_arguments
        cmd += self.disk_arguments
            
        print "Starting QEMU:\n\t%s\n\n" % cmd   
        self.proc = pexpect.spawn(cmd, timeout=7200, logfile=self.sio)
        self.proc.delaybeforesend=1
        
    def boot_master_image(self):
        """ reboot the system, and check that we are in a master shell
        """
        self.hard_reboot()
        try:
            # Necessary to get past U-Boot
            self.proc.expect("Starting kernel")
            self.in_master_shell()
        except:
            raise
        
    def boot_linaro_image(self):
        """ Reboot the system to the test image
        """
        self.hard_reboot()
        self.enter_uboot()
        uboot_cmds = self.board.uboot_cmds
        self.proc.sendline(uboot_cmds[0])
        for cmd in uboot_cmd[1:]:
            if self.board.type in ["mx51evk", "mx53loco"]:
                self.proc.expect(">")
            else:
                self.proc.expect("#")
            self.proc.sendline(cmd)
        self.in_test_shell()

    def soft_reboot(self):
        # Assume soft reboot will not work
        pass

    def hard_reboot(self):
        self.proc.sendline("reboot")
        self.proc.expect([pexpect.TIMEOUT], timeout=60)
        self.proc.sendcontrol('a')
        self.proc.send('x')
        self.start_qemu()

