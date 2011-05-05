#!/usr/bin/env python

import daemon
import signal
import time
import sys
import os

from lockfile.pidlockfile import PIDLockFile

PIDFILE_PATH = '/tmp/schedulerd.pid'

def cleanup(signum, stack):
    """
    Cleanup and exit function
    """
    raise SystemExit('Exiting LAVA Scheduler daemon')

def start():
    """
    Start the daemon
    """
    #Check for pidfile to see if the daemon already runs
    pid = None
    if os.path.exists(PIDFILE_PATH):
        with open(PIDFILE_PATH) as fd:
            pid = int(fd.read().strip())

    if pid is not None:
        message = "pidfile %s exists, daemon already running?"
        print >> sys.stderr, message % PIDFILE_PATH
        sys.exit(1)

    #Create signal map
    signal_map = {
        signal.SIGTERM: cleanup,
        signal.SIGHUP: 'terminate',
    }

    #Prepare daemon context
    context = {'working_directory': '.',
               'detach_process': True,
               'signal_map': signal_map,
               'files_preserve': [sys.stdout, sys.stderr],
               'stdout': sys.stdout,
               'stderr': sys.stderr,
               'umask': 0o002,
               'pidfile': PIDLockFile(PIDFILE_PATH)}

    with daemon.DaemonContext(**context):
        #Non-functional placeholder for upcoming scheduler code
        while True:
            print "Placeholder for scheduler code"
            time.sleep(60)

def stop():
    """
    Stop the daemon
    """
    #Get pid from the pidfile
    pid = None
    if os.path.exists(PIDFILE_PATH):
        with open(PIDFILE_PATH) as fd:
            pid = int(fd.read().strip())

    if pid is None:
        message = "pidfile %s does not exist, daemon not running?\n"
        print >> sys.stderr, message % PIDFILE_PATH
        return #Not an error in a restart

    #Kill the daemon now
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError, err:
        print >> sys.stderr, str(err)
        sys.exit(1)

def restart():
    """
    Restart the daemon
    """
    stop()
    start()
