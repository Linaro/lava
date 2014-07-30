# Copyright (C) 2014 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
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

import os
from lava_dispatcher.pipeline.action import Pipeline, Action, JobError
from lava_dispatcher.pipeline.job_actions.test import TestAction

# TODO: convert subprocess calls to _run_command
# TODO: move inject defines into overlay objects.


def _get_testdef_bzr_repo(testdef_repo, tmpdir, revision, proxy_env):
    bzrdir = os.path.join(tmpdir, 'bzrtestrepo')
    try:
        # As per bzr revisionspec, '-1' is "The last revision in a
        # branch".
        if revision is None:
            revision = '-1'

        proxy_env.update({'BZR_HOME': '/dev/null', 'BZR_LOG': '/dev/null'})
        subprocess.check_call(
            ['bzr', 'branch', '-r', revision, testdef_repo, bzrdir],
            env=proxy_env)
        return bzrdir
    except Exception as e:
        logging.error("Unable to get test definition from bzr (%s)" % (testdef_repo))
        raise RuntimeError("Unable to get test definition from bzr (%s)" % (testdef_repo))


def _get_testdef_tar_repo(testdef_repo, tmpdir):
    """Extracts the provided encoded tar archive into tmpdir."""
    tardir = os.path.join(tmpdir, 'tartestrepo')
    temp_tar = os.path.join(tmpdir, "tar-repo.tar")

    try:
        if not os.path.isdir(tardir):
            logging.info("Creating directory to extract the tar archive into.")
            os.makedirs(tardir)

        encoded_in = StringIO.StringIO(testdef_repo)
        decoded_out = StringIO.StringIO()
        base64.decode(encoded_in, decoded_out)

        # The following two operations can also be done in memory
        # using cStringIO.
        # At the moment the tar file sent is not big, but that can change.
        with open(temp_tar, "w") as write_tar:
            write_tar.write(decoded_out.getvalue())

        with tarfile.open(temp_tar) as tar:
            tar.extractall(path=tardir)
    except (OSError, tarfile.TarError) as ex:
        logging.error("Error extracting the tar archive.\n" + str(ex))
    finally:
        # Remove the temporary created tar file after it has been extracted.
        if os.path.isfile(temp_tar):
            os.unlink(temp_tar)
    return tardir


def _get_testdef_url_repo(testdef_repo, context, tmpdir):
    """Download the provided test definition file into tmpdir."""
    urldir = os.path.join(tmpdir, 'urltestrepo')

    try:
        if not os.path.isdir(urldir):
            logging.info("Creating directory to download the url file into.")
            os.makedirs(urldir)
        # we will not use 'testdef_file' here, we can get this info from URL
        testdef_file = download_image(testdef_repo, context, urldir)

    except Exception as e:
        logging.error('Unable to get test definition from url\n' + str(e))
        return None
    finally:
        logging.info("Downloaded test definition file to %s." % urldir)

    return urldir


def _get_testdef_info(testdef):
    metadata = {'os': '', 'devices': '', 'environment': ''}
    metadata['description'] = testdef['metadata'].get('description')
    metadata['format'] = testdef['metadata'].get('format')
    version = testdef['metadata'].get('version')
    metadata['version'] = version and str(version) or version

    # Convert list to comma separated string.
    if testdef['metadata'].get('os'):
        metadata['os'] = ','.join(testdef['metadata'].get('os'))

    if testdef['metadata'].get('devices'):
        metadata['devices'] = ','.join(testdef['metadata'].get('devices'))

    if testdef['metadata'].get('environment'):
        metadata['environment'] = ','.join(
            testdef['metadata'].get('environment'))

    return metadata


class GitRepoAction(Action):
    """
    Each repo action is for a single repository,
    tests using multiple repositories get multiple
    actions.
    """

    def __init__(self):
        super(GitRepoAction, self).__init__()
        self.name = "git-repo-action"
        self.description = "apply git repository of tests to the test image"
        self.summary = "clone git test repo"

    def run(self, connection, args=None):
        cwd = os.getcwd()
        gitdir = os.path.join(tmpdir, 'gittestrepo')
        # FIXME: adapt run_command for proxy support
        self._run_command(['git', 'clone', self.parameters['repository'], gitdir])
        if 'revision' in self.parameters:
            os.chdir(gitdir)
            self._run_command(['git', 'checkout', self.parameters['revision']])
        self.job.context.pipeline_data[self.name]['commit_id'] = self._run_command(
            ['git', 'log', '-1', '--pretty=%H']).strip()
        os.chdir(cwd)
        if self.errors:
                    raise RuntimeError("Unable to get test definition from git (%s)" % self.parameters)
        return connection


class BzrRepoAction(Action):
    """
    Each repo action is for a single repository,
    tests using multiple repositories get multiple
    actions.
    """

    def __init__(self):
        super(BzrRepoAction, self).__init__()
        self.name = "bzr-repo-action"
        self.description = "apply bazaar repository of tests to the test image"
        self.summary = "branch a bzr test repo"


class TarRepoAction(Action):

    def __init__(self):
        super(TarRepoAction, self).__init__()
        self.name = "tar-repo-action"
        self.description = "apply a tarball of tests to the test image"
        self.summary = "unpack tar test repo"


class UrlRepoAction(Action):

    def __init__(self):
        super(UrlRepoAction, self).__init__()
        self.name = "url-repo-action"
        self.description = "apply a single test file to the test image"
        self.summary = "download file test"


class TestDefinitionAction(TestAction):

    def __init__(self):
        super(TestDefinitionAction, self).__init__()
        self.name = "test-definition"
        self.description = "load test definitions into image"
        self.summary = "loading test definitions"
        self.testdefs = {}

    def populate(self):
        """
        validate allows this to be a lot simpler, no need
        to check if the key exists each time.
        """
        testdef_repos = []
        self.internal_pipeline = Pipeline(parent=self, job=self.job)
        for testdef in self.parameters['test']['definitions']:
            if testdef['from'] == 'git':
                handler = GitRepoAction()
            elif testdef['from'] == 'bzr':
                handler = BzrRepoAction()
            elif testdef['from'] == 'tar':
                handler = TarRepoAction()
            elif testdef['from'] == 'url':
                handler = UrlRepoAction()
            else:
                self.errors = "unsupported handler"
                raise JobError("unsupported testdef handler: %s %s" % (testdef, testdef['from']))
            handler.parameters = testdef
            self.internal_pipeline.add_action(handler)
            # FIXME: the outer pipeline may add unwatned data to the parameters['test']

    def validate(self):
        if not self.job:
            self.errors = "missing job object"
        if 'test' not in self.parameters:
            self.errors = "testaction without test parameters"
            # runtimeerror?
        if 'definitions' not in self.parameters['test']:
            self.errors = "test action without definition"
        for testdef in self.parameters['test']['definitions']:
            if 'from' not in testdef:
                self.errors = "missing 'from' field in test definition %s" % testdef
            if testdef['from'] is 'git':
                repository = str(testdef['repository'])
                if not repository.endswith('.git'):
                    self.errors = "git specified but repository does not look like git"

        self.internal_pipeline.validate_actions()
        if self.errors:  # FIXME: call from the base class
            self._log("Validation failed")
            raise JobError("Invalid job data: %s\n" % '\n'.join(self.errors))

    def run(self, connection, args=None):
        self._log("Loading test definitions")
        print self.testdefs
        return connection
