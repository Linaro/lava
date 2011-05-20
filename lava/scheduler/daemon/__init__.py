#!/usr/bin/env python

import ConfigParser
import logging
import daemon
import signal
import time
import sys
import os

#Find and import PIDLockFile
try:
    from lockfile.pidlockfile import PIDLockFile
except ImportError:
    from daemon.pidlockfile import PIDLockFile

logger = None
pidfile = None
debug_mode = 0
fh = None

def init(config_path):
    global logger
    global pidfile
    global debug_mode
    global fh

    #Create config parser
    config = ConfigParser.ConfigParser()
    config.read(config_path)

    #Get config params
    pidfile = config.get('files', 'pidfile')
    logfile = config.get('files', 'logfile')
    debug_mode = config.get('debug', 'debug_mode')
    log_level = config.get('debug', 'log_level')

    #Create daemon logger
    logger = logging.getLogger('lava.scheduler.daemon')

    #Set logging level
    if log_level is '1':
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)

    #Create formatter
    formatter = logging.Formatter(
                 '%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    #Create file handler and add it to logger
    fh = logging.FileHandler(logfile)
    fh.setFormatter(formatter)
    logger.addHandler(fh)

    if debug_mode is '1':
        #Create and add console handler if debug mode
        ch = logging.StreamHandler()
        ch.setFormatter(formatter)
        logger.addHandler(ch)

def cleanup(signum, stack):
    """
    Cleanup and exit function
    """
    logger.info('Exiting LAVA Scheduler daemon')
    raise SystemExit()

def start():
    """
    Start the daemon
    """
    logger.info('Starting LAVA Scheduler daemon')

    #Check for pid to see if the daemon already runs
    pid = None
    if os.path.exists(pidfile):
        with open(pidfile) as fd:
            pid = int(fd.read().strip())

    if pid is not None:
        message = "pidfile %s exists, daemon already running?\n"
        logger.info(message % pidfile)
        sys.exit(1)

    #Create signal map
    signal_map = {
        signal.SIGTERM: cleanup,
        signal.SIGHUP: 'terminate',
    }

    #Configure execution mode
    if debug_mode is '1':
        #Debug mode logs both to file and console
        files_preserve = [fh.stream, sys.stdout, sys.stderr]
        std_out = sys.stdout
        std_err = sys.stderr
    else:
        #Default mode logs only to file
        files_preserve = [fh.stream]
        std_out = None
        std_err = None

    #Prepare daemon context
    context = {'working_directory': '.',
               'detach_process': True,
               'signal_map': signal_map,
               'files_preserve': files_preserve,
               'stdout': std_out,
               'stderr': std_err,
               'umask': 0o002,
               'pidfile': PIDLockFile(pidfile)}
    
    with daemon.DaemonContext(**context):
        #Non-functional placeholder for upcoming scheduler code
        while True:
            logger.info("Placeholder for scheduler code")
            time.sleep(60)

def stop():
    """
    Stop the daemon
    """
    logger.info('Stopping LAVA Scheduler daemon')

    #Get pid from the pidfile
    pid = None
    if os.path.exists(pidfile):
        with open(pidfile) as fd:
            pid = int(fd.read().strip())

    if pid is None:
        message = "pidfile %s does not exist, daemon not running?\n"
        logger.warning(message % pidfile)
        return #Not an error in a restart
    
    #Kill the daemon now
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError, err:
        logger.error(str(err))
        sys.exit(1)

def restart():
    """
    Restart the daemon
    """
    stop()
    start()
