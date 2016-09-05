Description
============

Summary
#######

``lava-master`` provides daemonisation support for the zeromq master
dispatcher within ``lava-server`` for compatibility with sysvinit and
can be used with other init systems which do not support scripts
without internal daemonisation support.

Usage
#####

``lava-master`` passes all arguments down to the wrapped process, in the
case of LAVA, this is ``lava-server manage dispatcher-master``.

Options
#######

Options can be passed by editing /etc/lava-server/lava-master


Limitations
###########

``lava-master`` was written for ``lava-server`` and has some hardcoded
values::

 PIDFILE = '/var/run/lava-master.pid'
 LOGFILE = '/var/log/lava-server/lava-master.log'

Systemd support
###############

The default install uses systemd translation of the sysvinit script
but a systemd service file is available, if desired::

 /usr/share/lava-server/lava-master.service

This file can be copied to ``/lib/systemd/system/``.

