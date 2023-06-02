# Copyright (C) 2017-2019 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
#         Remi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import grp
import logging
import logging.handlers
import os
import pwd

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
            self.logger.error("[INIT] Unable to lookup the user or the group")
            return False
        self.logger.debug(
            "[INIT] Switching to (%s(%d), %s(%d))", user, user_id, group, group_id
        )

        try:
            os.setgid(group_id)
            os.setuid(user_id)
        except OSError:
            self.logger.error(
                "[INIT] Unable to the set (user, group)=(%s, %s)", user, group
            )
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
