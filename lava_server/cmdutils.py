# -*- coding: utf-8 -*-
# Copyright (C) 2017-2019 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
#         Remi Duraffort <remi.duraffort@linaro.org>
#
# This file is part of LAVA.
#
# LAVA is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License version 3
# as published by the Free Software Foundation
#
# LAVA is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with LAVA.  If not, see <http://www.gnu.org/licenses/>.

import ctypes
import ctypes.util
import fcntl
import grp
import logging
import logging.handlers
import os
import pwd
import signal

from django.core.management.base import BaseCommand


class LAVADaemonCommand(BaseCommand):
    def add_arguments(self, parser):
        log = parser.add_argument_group("logging")
        log.add_argument(
            "-l",
            "--level",
            choices=["ERROR", "WARN", "INFO", "DEBUG"],
            default="DEBUG",
            help="Logging level (ERROR, WARN, INFO, DEBUG) " "Default: DEBUG",
        )

        log.add_argument(
            "-o", "--log-file", default=self.default_logfile, help="Logging file path"
        )

        priv = parser.add_argument_group("privileges")
        priv.add_argument(
            "-u",
            "--user",
            default="lavaserver",
            help="Run the process under this user. It should "
            "be the same user as the gunicorn process.",
        )

        priv.add_argument(
            "-g",
            "--group",
            default="lavaserver",
            help="Run the process under this group. It should "
            "be the same group as the gunicorn process.",
        )

    def drop_privileges(self, user, group):
        try:
            user_id = pwd.getpwnam(user)[2]
            group_id = grp.getgrnam(group)[2]
        except KeyError:
            self.logger.error("Unable to lookup the user or the group")
            return False
        self.logger.debug(
            "Switching to (%s(%d), %s(%d))", user, user_id, group, group_id
        )

        try:
            os.setgid(group_id)
            os.setuid(user_id)
        except OSError:
            self.logger.error("Unable to the set (user, group)=(%s, %s)", user, group)
            return False

        # Set a restrictive umask (rwxr-xr-x)
        os.umask(0o022)

        return True

    def setup_logging(self, logger_name, level, log_file, log_format):
        del logging.root.handlers[:]
        del logging.root.filters[:]
        # Create the logger
        self.logger = logging.getLogger(logger_name)
        if log_file == "-":
            handler = logging.StreamHandler()
        else:
            handler = logging.handlers.WatchedFileHandler(log_file)
        handler.setFormatter(logging.Formatter(log_format))
        self.logger.addHandler(handler)

        # Set log level
        if level == "ERROR":
            self.logger.setLevel(logging.ERROR)
        elif level == "WARN":
            self.logger.setLevel(logging.WARN)
        elif level == "INFO":
            self.logger.setLevel(logging.INFO)
        else:
            self.logger.setLevel(logging.DEBUG)

    def setup_zmq_signal_handler(self):
        # Mask signals and create a pipe that will receive a bit for each
        # signal received. Poll the pipe along with the zmq socket so that we
        # can only be interupted while reading data.
        (pipe_r, pipe_w) = os.pipe()
        flags = fcntl.fcntl(pipe_w, fcntl.F_GETFL, 0)
        fcntl.fcntl(pipe_w, fcntl.F_SETFL, flags | os.O_NONBLOCK)

        def signal_to_pipe(signumber, _):
            # Send the signal number on the pipe
            os.write(pipe_w, chr(signumber).encode("utf-8"))

        signal.signal(signal.SIGINT, signal_to_pipe)
        signal.signal(signal.SIGTERM, signal_to_pipe)
        signal.signal(signal.SIGQUIT, signal_to_pipe)

        return (pipe_r, pipe_w)


def watch_directory(directory):
    IN_MODIFY = 0x00000002
    IN_ATTRIB = 0x00000004
    IN_MOVED_FROM = 0x00000040
    IN_MOVED_TO = 0x00000080
    IN_CREATE = 0x00000100
    IN_DELETE = 0x00000200
    IN_DELETE_SELF = 0x00000400
    IN_MOVE_SELF = 0x00000800

    IN_EVENTS = (
        IN_MODIFY
        | IN_ATTRIB
        | IN_MOVED_FROM
        | IN_MOVED_TO
        | IN_CREATE
        | IN_DELETE
        | IN_DELETE_SELF
        | IN_MOVE_SELF
    )

    # watch a directory using inotify
    # return the corresponding file descriptor
    libc_name = ctypes.util.find_library("c")
    libc = ctypes.cdll.LoadLibrary(libc_name)

    # create the inotify file descriptor
    inotify_fd = libc.inotify_init()
    # watch the "test" directory
    ret = libc.inotify_add_watch(inotify_fd, directory.encode("utf-8"), IN_EVENTS)
    return None if ret == -1 else inotify_fd
