#  Copyright 2013 Linaro Limited
#  Author: Neil Williams <neil.williams@linaro.org>
#
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
#  MA 02110-1301, USA.
#

import os
import signal
import sys
import logging
import daemon
try:
    import daemon.pidlockfile as pidlockfile
except ImportError:
    from lockfile import pidlockfile
from logging.handlers import WatchedFileHandler
from subprocess import Popen

# Daemonise support for lava-dispatcher daemons, copied from
# lava-coordinator.

# pylint: disable=superfluous-parens,invalid-name
child = None


def signal_handler(sig, frame):  # pylint: disable=unused-argument
    global child  # pylint: disable=global-statement
    try:
        logging.info("Closing daemon and child %d", child.pid)
        child.send_signal(sig)
        child = None
        sys.exit(os.EX_OK)
    except Exception as e:
        raise Exception('Error in signal handler: ' + str(e))


def getDaemonLogger(filePath, log_format=None, loglevel=logging.INFO):
    logger = logging.getLogger()
    logger.setLevel(loglevel)
    try:
        watchedHandler = WatchedFileHandler(filePath)
    except Exception as e:  # pylint: disable=broad-except
        return e, None

    watchedHandler.setFormatter(logging.Formatter(log_format or '%(asctime)s %(msg)s'))
    logger.addHandler(watchedHandler)
    return logger, watchedHandler


def daemonise(pidfile, logfile):
    global child  # pylint: disable=global-statement
    client_logger, watched_file_handler = getDaemonLogger(logfile, loglevel=logging.DEBUG)
    if isinstance(client_logger, Exception):
        print("Fatal error creating client_logger: " + str(client_logger))
        sys.exit(os.EX_OSERR)
    # noinspection PyArgumentList
    lockfile = pidlockfile.PIDLockFile(pidfile)
    if lockfile.is_locked():
        logging.error("PIDFile %s already locked", pidfile)
        sys.exit(os.EX_OSERR)
    context = daemon.DaemonContext(
        detach_process=True,
        working_directory=os.getcwd(),
        pidfile=lockfile,
        files_preserve=[watched_file_handler.stream],
        stderr=watched_file_handler.stream,
        stdout=watched_file_handler.stream)
    context.signal_map = {
        signal.SIGTERM: signal_handler,
        signal.SIGHUP: signal_handler
    }
    # pass the args down to the process to be run in the daemon context
    args = sys.argv
    args.pop(0)
    args.insert(0, 'lava-dispatcher-slave')  # each daemon shares a call to the django wrapper
    arg_str = " ".join(args)
    with context:
        logging.info("Running LAVA Daemon")
        child = Popen(args)
        logging.debug("LAVA Daemon: %s pid: %d" % (arg_str, child.pid))
        child.communicate()
        logging.info("Closing LAVA Daemon.")
    return 0
