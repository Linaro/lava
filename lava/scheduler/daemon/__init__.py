#!/usr/bin/env python

import lockfile
import daemon
import signal
import atexit
import time
import sys
import os

from config import PIDFILE_PATH

def delete_pidfile():
    """
    Delete pidfile
    """
    if os.path.exists(PIDFILE_PATH):
        os.remove(PIDFILE_PATH)

def start():
    """
    Start the daemon
    """
    #Check for pidfile to see if the daemon already runs
    try:
        pf = file(PIDFILE_PATH, 'r')
        pid = int(pf.read().strip())
        pf.close()
    except IOError:
        pid = None

    if pid:
        message = "pidfile %s already exist. Daemon already running?\n"
        sys.stderr.write(message % PIDFILE_PATH)
        sys.exit(1)

    #Register clean-up function
    atexit.register(delete_pidfile)

    #Create pidfile and write pid
    pid = str(os.getpid())
    try:
        file(PIDFILE_PATH, 'w+').write("%s\n" % pid)
    except IOError, err:
        message = "\npidfile %s not created.\n" + str(err)
        sys.stderr.write(message % PIDFILE_PATH)
        sys.exit(1)
    
    #Prepare daemon context
    context = {'working_directory': '.',
               'detach_process': False}
    
    context.update(files_preserve=[sys.stdout, sys.stderr],
                   stdout=sys.stdout,
                   stderr=sys.stderr,
                   umask=0o002,
                   pidfile=lockfile.FileLock(PIDFILE_PATH))
    
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
    try:
        pf = file(PIDFILE_PATH, 'r')
        pid = int(pf.read().strip())
        pf.close()
    except IOError:
        pid = None

    if not pid:
        message = "pidfile %s does not exist. Daemon not running?\n"
        sys.stderr.write(message % PIDFILE_PATH)
        return #Not an error in a restart
    
    #Kill the daemon now
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError, err:
        err = str(err)
        if err.find("No such process") > 0:
            if os.path.exists(PIDFILE_PATH):
                os.remove(PIDFILE_PATH)
        else:
            print err
            sys.exit(1)

def restart():
    """
    Restart the daemon
    """
    stop()
    start()
