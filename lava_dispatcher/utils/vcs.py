# Copyright (C) 2014 Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import logging
import os
import shutil
import subprocess  # nosec - internal use.

from lava_common.exceptions import InfrastructureError
from lava_dispatcher.utils.network import retry


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

    @retry(retries=6, delay=5)
    def clone(self, dest_path, shallow=False, revision=None, branch=None, history=True):
        logger = logging.getLogger("dispatcher")

        # Clear the data
        if os.path.exists(dest_path):
            shutil.rmtree(dest_path)

        try:
            cmd_args = [self.binary, "clone"]
            if branch is not None:
                cmd_args.extend(["-b", branch])
            if shallow:
                cmd_args.append("--depth=1")
            cmd_args.extend([self.url, dest_path])

            logger.debug("Running '%s'", " ".join(cmd_args))
            # Replace shell variables by the corresponding environment variable
            cmd_args[-2] = os.path.expandvars(cmd_args[-2])

            try:
                subprocess.check_output(  # nosec - internal use.
                    cmd_args, stderr=subprocess.STDOUT
                )
            except subprocess.CalledProcessError as exc:
                if (
                    exc.stdout
                    and "does not support shallow capabilities"
                    in exc.stdout.decode("utf-8", errors="replace")
                ):
                    logger.warning(
                        "Tried shallow clone, but server doesn't support it. Retrying without..."
                    )
                    cmd_args.remove("--depth=1")
                    subprocess.check_output(  # nosec - internal use.
                        cmd_args, stderr=subprocess.STDOUT
                    )
                else:
                    raise

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
