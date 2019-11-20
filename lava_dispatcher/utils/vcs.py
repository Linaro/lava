# Copyright (C) 2014 Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
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
# along
# with this program; if not, see <http://www.gnu.org/licenses>.

import logging
import os
import shutil
import subprocess  # nosec - internal use.

from lava_common.exceptions import InfrastructureError


class VCSHelper:
    def __init__(self, url):
        self.url = url

    def clone(self, dest_path, shallow=None, revision=None, branch=None, history=None):
        raise NotImplementedError


class GitHelper(VCSHelper):
    """
    Helper to clone a git repository.

    Usage:
      git = GitHelper('url_to.git')
      commit_id = git.clone('destination')
      commit_id = git.clone('destination2, 'hash')

    This helper will raise a InfrastructureError for any error encountered.
    """

    def __init__(self, url):
        super().__init__(url)
        self.binary = "/usr/bin/git"

    def clone(self, dest_path, shallow=False, revision=None, branch=None, history=True):
        logger = logging.getLogger("dispatcher")
        try:
            if branch is not None:
                cmd_args = [self.binary, "clone", "-b", branch, self.url, dest_path]
            else:
                cmd_args = [self.binary, "clone", self.url, dest_path]

            if shallow:
                cmd_args.append("--depth=1")

            logger.debug("Running '%s'", " ".join(cmd_args))
            subprocess.check_output(  # nosec - internal use.
                cmd_args, stderr=subprocess.STDOUT
            )

            if revision is not None:
                logger.debug("Running '%s checkout %s", self.binary, str(revision))
                subprocess.check_output(  # nosec - internal use.
                    [self.binary, "-C", dest_path, "checkout", str(revision)],
                    stderr=subprocess.STDOUT,
                )

            commit_id = subprocess.check_output(  # nosec - internal use.
                [self.binary, "-C", dest_path, "log", "-1", "--pretty=%H"],
                stderr=subprocess.STDOUT,
            ).strip()

            if not history:
                logger.debug("Removing '.git' directory in %s", dest_path)
                shutil.rmtree(os.path.join(dest_path, ".git"))

        except subprocess.CalledProcessError as exc:
            if exc.stdout:
                logger.warning(exc.stdout.decode("utf-8", errors="replace"))
            if exc.stderr:
                logger.error(exc.stderr.decode("utf-8", errors="replace"))
            raise InfrastructureError(
                "Unable to fetch git repository '%s'" % (self.url)
            )

        return commit_id.decode("utf-8", errors="replace")


class TarHelper(VCSHelper):
    # TODO: implement TarHelper

    def __init__(self, url):
        super().__init__(url)
        self.binary = None


class URLHelper(VCSHelper):
    # TODO: implement URLHelper

    def __init__(self, url):
        super().__init__(url)
        self.binary = None

    def clone(self, dest_path, shallow=None, revision=None, branch=None, history=None):
        raise NotImplementedError
