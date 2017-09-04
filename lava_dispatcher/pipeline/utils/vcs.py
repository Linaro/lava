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

import sys
import logging
import os
import subprocess
import yaml
from lava_dispatcher.pipeline.action import InfrastructureError


# pylint: disable=too-few-public-methods


class VCSHelper(object):

    def __init__(self, url):
        self.url = url

    def clone(self, dest_path, revision=None, branch=None):
        raise NotImplementedError


class BzrHelper(VCSHelper):

    def __init__(self, url):
        super(BzrHelper, self).__init__(url)
        self.binary = '/usr/bin/bzr'

    def clone(self, dest_path, revision=None, branch=None):
        cwd = os.getcwd()
        logger = logging.getLogger('dispatcher')
        env = dict(os.environ)
        env.update({'BZR_HOME': '/dev/null', 'BZR_LOG': '/dev/null'})

        try:
            if revision is not None:
                logger.debug("Running '%s branch -r %s %s'", self.binary, str(revision), self.url)
                subprocess.check_output([self.binary, 'branch', '-r',
                                         str(revision), self.url,
                                         dest_path],
                                        stderr=subprocess.STDOUT, env=env)
                commit_id = revision
            else:
                logger.debug("Running '%s branch %s'", self.binary, self.url)
                subprocess.check_output([self.binary, 'branch', self.url,
                                         dest_path],
                                        stderr=subprocess.STDOUT, env=env)
                os.chdir(dest_path)
                commit_id = subprocess.check_output(['bzr', 'revno'],
                                                    env=env).strip().decode('utf-8')

        except subprocess.CalledProcessError as exc:
            exc_command = [i.strip() for i in exc.cmd]
            if sys.version > '3':
                exc_message = str(exc)  # pylint: disable=redefined-variable-type
                exc_output = str(exc).split('\n')
            else:
                exc_message = [i.strip() for i in exc.message],  # pylint: disable=redefined-variable-type
                exc_output = exc.output.split('\n')
            logger.exception(yaml.dump({
                'command': exc_command,
                'message': exc_message,
                'output': exc_output}))
            raise InfrastructureError("Unable to fetch bzr repository '%s'"
                                      % (self.url))
        finally:
            os.chdir(cwd)

        return commit_id


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
        super(GitHelper, self).__init__(url)
        self.binary = '/usr/bin/git'

    def clone(self, dest_path, shallow=False, revision=None, branch=None):
        logger = logging.getLogger('dispatcher')
        try:
            if branch is not None:
                cmd_args = [self.binary, 'clone', '-b', branch, self.url,
                            dest_path]
            else:
                cmd_args = [self.binary, 'clone', self.url, dest_path]

            if shallow:
                cmd_args.append("--depth=1")

            logger.debug("Running '%s'", " ".join(cmd_args))
            subprocess.check_output(cmd_args, stderr=subprocess.STDOUT)

            if revision is not None:
                logger.debug("Running '%s checkout %s", self.binary,
                             str(revision))
                subprocess.check_output([self.binary, '-C', dest_path,
                                         'checkout', str(revision)],
                                        stderr=subprocess.STDOUT)

            commit_id = subprocess.check_output([self.binary, '-C', dest_path,
                                                 'log', '-1', '--pretty=%H'],
                                                stderr=subprocess.STDOUT).strip()
        except subprocess.CalledProcessError as exc:
            if sys.version > '3':
                logger.error(str(exc))
            else:
                logger.error(exc.output)
            raise InfrastructureError("Unable to fetch git repository '%s'"
                                      % (self.url))

        return commit_id.decode('utf-8')


class TarHelper(VCSHelper):
    # TODO: implement TarHelper

    def __init__(self, url):
        super(TarHelper, self).__init__(url)
        self.binary = None

    def clone(self, dest_path, revision=None, branch=None):
        super(TarHelper, self).clone(dest_path, revision, branch)


class URLHelper(VCSHelper):
    # TODO: implement URLHelper

    def __init__(self, url):
        super(URLHelper, self).__init__(url)
        self.binary = None

    def clone(self, dest_path, revision=None, branch=None):
        super(URLHelper, self).clone(dest_path, revision, branch)
