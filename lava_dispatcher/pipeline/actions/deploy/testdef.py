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
import yaml
import base64
import tarfile
import StringIO
from uuid import uuid4
from lava_dispatcher.pipeline.action import (
    Pipeline,
    RetryAction,
    JobError
)
from lava_dispatcher.pipeline.actions.deploy.download import DownloaderAction
from lava_dispatcher.pipeline.actions.test import TestAction


class RepoAction(RetryAction):

    def __init__(self):
        super(RepoAction, self).__init__()
        self.name = "repo-action"
        self.description = "apply tests to the test image"
        self.summary = "repo base class"
        self.tmpdir = None
        self.vcs_binary = None
        self.runner = None
        self.uuid = str(uuid4())
        self.testdef = None

    def validate(self):
        if self.vcs_binary and not os.path.exists(self.vcs_binary):
            raise JobError("%s is not installed on the dispatcher." % self.vcs_binary)

    def run(self, connection, args=None):
        # FIXME: determine why deployment_data is not available at validation stage
        lava_test_results_dir = self.parameters['deployment_data']['lava_test_results_dir']
        prefix = lava_test_results_dir % self.job.device.parameters['hostname']
        self.runner = ('%s/tests/%s\n' % (prefix, self.parameters['test_name']))
        # mntdir is a temporary directory, not available at validate stage.
        self.tmpdir = self.data['mount_action']['mntdir']
        # NOTE: the eventual runner_path must remain empty until after the VCS clone, so let the VCS clone create the final dir

        # if 'test-case-deps' in testdef:  # FIXME - is this needed?
        #    self._get_dependent_test_cases(testdef)

        # install is done from the main overlay
        # TODO: implement
        # if self.skip_install != "all":
        #    if 'install' in self.testdef:
        #        if self.skip_install != 'repos':
        #            self._create_repos(hostdir)
        #        self._create_target_install(hostdir, targetdir)

        return connection


def indices(string, char):

    return [i for i, c in enumerate(string) if c == char]


class GitRepoAction(RepoAction):
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
        self.vcs_binary = "/usr/bin/git"

    def run(self, connection, args=None):
        super(GitRepoAction, self).run(connection, args)
        if self.name not in self.data:
            self.data[self.name] = {}
        cwd = os.getcwd()
        # tmpdir is the mount_path/lava-hostname/ directory
        # testdefs to go into tmpdir/tests/0_name
        runner_path = os.path.join(self.tmpdir, 'tests', self.parameters['test_name'])
        self._run_command([self.vcs_binary, 'clone', self.parameters['repository'], runner_path])
        if 'revision' in self.parameters:
            os.chdir(runner_path)
            self._run_command([self.vcs_binary, 'checkout', self.parameters['revision']])
        commit_id = self._run_command([self.vcs_binary, 'log', '-1', '--pretty=%H']).strip()

        # now read the YAML to create a testdef dict to retrieve metadata
        yaml_file = os.path.join(runner_path, self.parameters['path'])
        if not os.path.exists(yaml_file):
            raise JobError("Unable to find test definition YAML: %s" % yaml_file)
        with open(yaml_file, 'r') as f:
            self.testdef = yaml.safe_load(f)

        with open("%s/testdef.yaml" % runner_path, 'w') as f:
            yaml.safe_dump(self.testdef, f)

        # TODO: check if this copy dict is needed or if other routines
        # can use the fields directly. Needs to be per handler as it reads the YAML & parameters.
        self.data.update({
            self.name: {
                'os': self.testdef['metadata'].get('os', ''),
                'devices': self.testdef['metadata'].get('devices', ''),
                'environment': self.testdef['metadata'].get('environment', ''),
                'branch_vcs': 'git',
                'project_name': self.parameters['test_name'],  # FIXME: do we need this duplicate?
                'commit_id': commit_id,  # FIXME: do we need this?
            }
        })

        # write out the UUID of each test definition.
        with open('%s/uuid' % runner_path, 'w') as f:
            f.write(self.uuid)

        # FIXME: does this match old-world test-shell?
        with open('%s/testdef_metadata' % runner_path, 'w') as f:
            f.write(yaml.safe_dump(self.data[self.name]))

        with open('%s/run.sh' % runner_path, 'w') as f:
            # self._inject_testdef_parameters(f)
            f.write('set -ex\n')
            f.write('export TESTRUN_ID=%s\n' % self.testdef['metadata']['name'])
            f.write('cd %s\n' % self.runner)
            f.write('UUID=`cat uuid`\n')
            f.write('echo "<LAVA_SIGNAL_STARTRUN $TESTRUN_ID $UUID>"\n')
            f.write('#wait for an ack from the dispatcher\n')
            f.write('read\n')
            steps = self.testdef['run'].get('steps', [])
            if steps:
                for cmd in steps:
                    f.write('%s\n' % cmd)
            f.write('echo "<LAVA_SIGNAL_ENDRUN $TESTRUN_ID $UUID>"\n')
            f.write('#wait for an ack from the dispatcher\n')
            f.write('read\n')

        os.chdir(cwd)
        if not self.valid:
            raise RuntimeError("Unable to get test definition from %s (%s)" % (self.vcs_binary, self.parameters))
        return connection


class BzrRepoAction(RepoAction):
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
        self.vcs_binary = "/usr/bin/bzr"

    def run(self, connection, args=None):
        super(BzrRepoAction, self).run(connection, args)
        runner_path = os.path.join(self.tmpdir, 'tests', self.parameters['test_name'])
        # As per bzr revisionspec, '-1' is "The last revision in a branch".
        revision = '-1'
        if 'revision' in self.parameters:
            revision = self.parameters['revision']
        self.env.update({'BZR_HOME': '/dev/null', 'BZR_LOG': '/dev/null'})
        self._run_command([
            [self.vcs_binary, 'branch', '-r', revision, self.parameters['repository'], runner_path],
        ])
        if self.errors:
            raise RuntimeError("Unable to get test definition from %s (%s)" % (self.vcs_binary, self.parameters))

        # now read the YAML to create a testdef dict to retrieve metadata
        yaml_file = os.path.join(runner_path, self.parameters['path'])
        if not os.path.exists(yaml_file):
            raise JobError("Unable to find test definition YAML: %s" % yaml_file)
        with open(yaml_file, 'r') as f:
            self.testdef = yaml.safe_load(f)

        # FIXME: do this once and set the branch_vcs per handler?
        self.data.update({
            self.name: {
                'os': self.testdef['metadata'].get('os', ''),
                'devices': self.testdef['metadata'].get('devices', ''),
                'environment': self.testdef['metadata'].get('environment', ''),
                'branch_vcs': 'bzr',
                'project_name': self.parameters['test_name'],  # FIXME: do we need this duplicate?
                'commit_id': commit_id,  # FIXME: do we need this?
            }
        })

        return connection


class TarRepoAction(RepoAction):

    def __init__(self):
        super(TarRepoAction, self).__init__()
        self.name = "tar-repo-action"
        self.description = "apply a tarball of tests to the test image"
        self.summary = "unpack tar test repo"
        self.vcs_binary = "/bin/tar"

    def run(self, connection, args=None):
        """
        Extracts the provided encoded tar archive into tmpdir.
        """
        super(TarRepoAction, self).run(connection, args)
        runner_path = os.path.join(self.tmpdir, 'tests', self.parameters['test_name'])
        temp_tar = os.path.join(self.tmpdir, "tar-repo.tar")

        try:
            if not os.path.isdir(runner_path):
                self._log("Creating directory to extract the tar archive into.")
                os.makedirs(runner_path)

            encoded_in = StringIO.StringIO(self.parameters['repository'])
            decoded_out = StringIO.StringIO()
            base64.decode(encoded_in, decoded_out)

            # The following two operations can also be done in memory
            # using cStringIO.
            # At the moment the tar file sent is not big, but that can change.
            with open(temp_tar, "w") as write_tar:
                write_tar.write(decoded_out.getvalue())

            with tarfile.open(temp_tar) as tar:
                tar.extractall(path=runner_path)
        except (OSError, tarfile.TarError) as ex:
            raise JobError("Error extracting the tar archive.\n" + str(ex))
        finally:
            # Remove the temporary created tar file after it has been extracted.
            if os.path.isfile(temp_tar):
                os.unlink(temp_tar)
        return connection


class UrlRepoAction(DownloaderAction):

    def __init__(self):
        super(UrlRepoAction, self).__init__()
        self.name = "url-repo-action"
        self.description = "apply a single test file to the test image"
        self.summary = "download file test"
        self.tmpdir = None  # FIXME: needs to be a /mntpoint/lava-%hostname/ directory.

    def run(self, connection, args=None):
        """Download the provided test definition file into tmpdir."""
        super(UrlRepoAction, self).run(connection, args)
        runner_path = os.path.join(self.tmpdir, 'tests', self.parameters['test_name'])

        try:
            if not os.path.isdir(runner_path):
                self._log("Creating directory to download the url file into.")
                os.makedirs(runner_path)
            # we will not use 'testdef_file' here, we can get this info from URL
            # testdef_file = download_image(testdef_repo, context, urldir)
            # FIXME: this handler uses DownloaderAction.run()

        except OSError as exc:
            raise JobError('Unable to get test definition from url\n' + str(exc))
        finally:
            self._log("Downloaded test definition file to %s." % runner_path)

        i = []
        for e in " $&()\"'<>/\\|;`":
            i.extend(indices(self.testdef["metadata"]["name"], e))
        if i:
            msg = "Test name contains invalid symbol(s) at position(s): %s" % ", ".join(map(str, i))
            raise JobError(msg)

        try:
            self.testdef["metadata"]["name"].encode()
        except UnicodeEncodeError as e:
            msg = "Test name contains non-ascii symbols: %s" % e
            raise JobError(msg)

        return connection


class TestDefinitionAction(TestAction):

    def __init__(self):
        """
        The TestDefinitionAction installs each test definition into
        the overlay. It does not execute the scripts in the test
        definition, that is the job of the TestAction class.
        One TestDefinitionAction handles all test definitions for
        the current job.
        In addition, a TestOverlayAction is added to the pipeline
        to handle parts of the overlay which are test definition dependent.
        """
        super(TestDefinitionAction, self).__init__()
        self.name = "test-definition"
        self.description = "load test definitions into image"
        self.summary = "loading test definitions"

    def populate(self):
        """
        validate allows this to be a lot simpler, no need
        to check if the key exists each time.
        """
        index = {}
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
            # set the full set of job YAML parameters for this handler as handler parameters.
            handler.parameters = testdef
            # store the correct test_name before incrementing the local index dict
            handler.parameters['test_name'] = "%s_%s" % (len(index.keys()), handler.parameters['name'])
            index[len(index.keys())] = handler.parameters['name']
            self.internal_pipeline.add_action(handler)
            # FIXME: the outer pipeline may add unwanted data to the parameters['test']
        self.internal_pipeline.add_action(TestOverlayAction())

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

    def _inject_testdef_parameters(self, fout):  # FIXME: needs a separate action
        # inject default parameters that were defined in yaml first
        fout.write('###default parameters from yaml###\n')
        if 'params' in self.testdef:
            for def_param_name, def_param_value in self.testdef['params'].items():
                fout.write('%s=\'%s\'\n' % (def_param_name, def_param_value))
        fout.write('######\n')
        # inject the parameters that was set in json
        fout.write('###test parameters from json###\n')
        if self._sw_sources and 'test_params' in self._sw_sources[0] and self._sw_sources[0]['test_params'] != '':
            _test_params_temp = eval(self._sw_sources[0]['test_params'])
            for param_name, param_value in _test_params_temp.items():
                fout.write('%s=\'%s\'\n' % (param_name, param_value))
        fout.write('######\n')

    def copy_test(self, hostdir, targetdir):  # FIXME: needs porting to the new classes
        """Copy the files needed to run this test to the device.

        :param hostdir: The location on the device filesystem to copy too.
        :param targetdir: The location `hostdir` will have when the device
            boots.
        """

        with open('%s/testdef_metadata' % hostdir, 'w') as f:
            f.write(yaml.safe_dump(self.testdef_metadata))

        if self.skip_install != "all":
            if 'install' in self.testdef:
                if self.skip_install != 'repos':
                    self._create_repos(hostdir)
                self._create_target_install(hostdir, targetdir)

    def run(self, connection, args=None):
        """
        Puts the requested test definition files into the overlay

        :param connection: Connection object, if any.
        :param args: Not used.
        :return: the received Connection.
        """
        self._log("Loading test definitions")
        # developer hack - if the image hasn't been downloaded this time, it may already contain old files
        # should really be an rmtree but it is only here to save developer time on downloads...
        if os.path.exists(self.data['mount_action']['mntdir']):
            os.unlink('%s/lava-test-runner.conf' % self.data['mount_action']['mntdir'])
        connection = self.internal_pipeline.run_actions(connection)
        with open('%s/lava-test-runner.conf' % self.data['mount_action']['mntdir'], 'a') as runner_conf:
            for handler in self.internal_pipeline.actions:
                if isinstance(handler, RepoAction) or isinstance(handler, UrlRepoAction):
                    runner_conf.write(handler.runner)
                if isinstance(handler, TestAction):  # FIXME: separate actions for copy & inject
                    # run copy_test
                    hostdir = self.data['mount_action']['mntdir']
                    targetdir = ''
        return connection


class TestOverlayAction(TestAction):

    def __init__(self):
        """
        When a job requires a TestAction, some files need to be added to
        the existing Overlay as part of Test.
        This class adds the necessary scripts to support test definitions
        but which are test definition dependent, like the install handler.
        """
        super(TestOverlayAction, self).__init__()
        self.name = "test-overlay"
        self.description = "overlay test support files onto image"
        self.summary = "applying LAVA test overlay"

    def validate(self):
        pass

    def run(self, connection, args=None):
        return connection
