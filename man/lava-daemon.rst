Description
============

Summary
#######

``lava-daemon`` provides daemonisation support for the scheduler within
``lava-server`` for compatibility with sysvinit and can be used with
other init systems which do not support scripts without internal
daemonisation support.

Usage
#####

``lava-daemon`` passes all arguments down to the wrapped process, in the
case of LAVA, this is ``lava-server``.

Limitations
###########

``lava-daemon`` was written for ``lava-server`` and has some hardcoded
values::

 PIDFILE = '/var/run/lava-server.pid'
 LOGFILE = '/var/log/lava-server/lava-scheduler.log'
 DAEMON = '/usr/bin/lava-server'

