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
import io
import ast
import yaml
import base64
import tarfile
from uuid import uuid4
from lava_dispatcher.pipeline.action import (
    Pipeline,
    Action,
    JobError,
)
from lava_dispatcher.pipeline.actions.test import TestAction


class RepoAction(Action):

    def __init__(self):
        super(RepoAction, self).__init__()
        self.name = "repo-action"
        self.description = "apply tests to the test image"
        self.summary = "repo base class"
        self.vcs_binary = None
        self.runner = None
        self.default_pattern = "(?P<test_case_id>.*-*)\\s+:\\s+(?P<result>(PASS|pass|FAIL|fail|SKIP|skip|UNKNOWN|unknown))"
        self.default_fixupdict = {'PASS': 'pass', 'FAIL': 'fail', 'SKIP': 'skip', 'UNKNOWN': 'unknown'}
        # FIXME: sort out a genuinely unique ID based on the *database* JobID and pipeline level for reproducibility
        # {DB-JobID}-{PipelineLevel}, e.g. 15432.0-3.5.4
        # delay until jobs can be scheduled from the UI.
        # allows individual testcase results to be at a predictable URL
        self.uuid = str(uuid4())

    @classmethod
    def select(cls, repo_type):

        candidates = cls.__subclasses__()
        willing = [c for c in candidates if c.accepts(repo_type)]

        if len(willing) == 0:
            raise NotImplementedError(
                "No testdef_repo hander is available for the given repository type"
                " '%s'." % repo_type)

        # higher priority first
        compare = lambda x, y: cmp(y.priority, x.priority)
        prioritized = sorted(willing, compare)

        return prioritized[0]

    def validate(self):
        # FIXME: this should work but test_basic.py needs to be migrated to the new Device configuration first
        # if 'hostname' not in self.job.device.parameters:
        #     raise InfrastructureError("Invalid device configuration")
        if 'test_name' not in self.parameters:
            raise JobError("Unable to determine test_name")
        if self.vcs_binary and not os.path.exists(self.vcs_binary):
            raise JobError("%s is not installed on the dispatcher." % self.vcs_binary)
        super(RepoAction, self).validate()

    def run(self, connection, args=None):
        """
        The base class run() currently needs to run after the mount operation, i.e. as part of run() so that
        the path can be correctly set when writing the overlay.
        Better approach will be to create the entire overlay without mounting and then
        unpack an overlay.tgz after mounting.
        """
        if 'test' not in self.data:
            self.data['test'] = {}
        if self.uuid not in self.data['test']:
            self.data['test'][self.uuid] = {}
        if 'runner_path' not in self.data['test'][self.uuid]:
            self.data['test'][self.uuid]['runner_path'] = {}
        if 'overlay_path' not in self.data['test'][self.uuid]:
            self.data['test'][self.uuid]['overlay_path'] = {}

        if not args or 'test_name' not in args:
            raise RuntimeError("RepoAction run called via super without parameters as arguments")

        # runner_path is the path to read and execute from to run the tests after boot
        self.data['test'][self.uuid]['runner_path'][args['test_name']] = os.path.join(
            args['deployment_data']['lava_test_results_dir'] % self.job.device.parameters['hostname'],
            'tests',
            args['test_name']
        )
        # the location written into the lava-test-runner.conf (needs a line ending)
        self.runner = "%s\n" % self.data['test'][self.uuid]['runner_path'][args['test_name']]

        # overlay_path is the location of the files before boot
        self.data['test'][self.uuid]['overlay_path'][args['test_name']] = os.path.join(
            self.data['mount_action']['mntdir'],
            'tests',
            args['test_name']
        )

        # FIXME - is this needed? - the issue here is that the new model does not use fs.tgz
        # therefore, there may not be the same need to collate the dependent testdefs, all of the
        # YAML in the repo will still exist - this may change behaviour.
        # if 'test-case-deps' in testdef:
        #    self._get_dependent_test_cases(testdef)

        return connection

    def store_testdef(self, testdef, commit_id=None):
        """
        Allows subclasses to pass in the parsed testdef after the repository has been obtained
        and the specified YAML file can be read.
        The Connection uses the data in the test dict to retrieve the supplied parse pattern
        and the fixup dictionary, if specified.
        The Connection stores raw results in the same test dict.
        The main TestAction can then process the results.
        """
        self.data['test'][self.uuid].update({
            'testdef_metadata': {
                'os': testdef['metadata'].get('os', ''),
                'devices': testdef['metadata'].get('devices', ''),
                'environment': testdef['metadata'].get('environment', ''),
                'branch_vcs': 'git',
                'project_name': testdef['metadata']['name'],
            }
        })

        if commit_id:
            self.data['test'][self.uuid]['testdef_metadata'].update({
                'commit_id': commit_id,
            })

        if 'parse' in testdef:
            pattern = testdef['parse'].get('pattern', '')
        else:
            pattern = self.default_pattern
        self.data['test'][self.uuid].update({
            'testdef_pattern': {
                'pattern': pattern,
            }
        })


def indices(string, char):
    # FIXME: move to utils
    return [i for i, c in enumerate(string) if c == char]


class GitRepoAction(RepoAction):
    """
    Each repo action is for a single repository,
    tests using multiple repositories get multiple
    actions.
    """

    priority = 1

    def __init__(self):
        super(GitRepoAction, self).__init__()
        self.name = "git-repo-action"
        self.description = "apply git repository of tests to the test image"
        self.summary = "clone git test repo"
        self.vcs_binary = "/usr/bin/git"

    def validate(self):
        if 'repository' not in self.parameters:
            raise JobError("Git repository not specified in job definition")
        if 'path' not in self.parameters:
            raise JobError("Path to YAML file not specified in the job definition")
        super(GitRepoAction, self).validate()

    @classmethod
    def accepts(cls, repo_type):
        if repo_type == 'git':
            return True
        return False

    def run(self, connection, args=None):
        """
        Clones the git repo into a directory name constructed from the mount_path,
        lava-$hostname prefix, tests, $index_$test_name elements. e.g.
        /tmp/tmp.234Ga213/lava-kvm01/tests/3_smoke-tests-basic
        Also updates some basic metadata about the test definition.
        """

        # use the base class to populate the runner_path and overlay_path data into the context
        connection = super(GitRepoAction, self).run(connection, self.parameters)

        cwd = os.getcwd()
        # NOTE: the runner_path dir must remain empty until after the VCS clone, so let the VCS clone create the final dir
        runner_path = self.data['test'][self.uuid]['overlay_path'][self.parameters['test_name']]
        self._run_command([self.vcs_binary, 'clone', self.parameters['repository'], runner_path])
        if 'revision' in self.parameters:
            os.chdir(runner_path)
            self._run_command([self.vcs_binary, 'checkout', self.parameters['revision']])
        commit_id = self._run_command([self.vcs_binary, 'log', '-1', '--pretty=%H']).strip()
        self.results = {'success': commit_id}

        # now read the YAML to create a testdef dict to retrieve metadata
        yaml_file = os.path.join(runner_path, self.parameters['path'])
        if not os.path.exists(yaml_file):
            raise JobError("Unable to find test definition YAML: %s" % yaml_file)
        with open(yaml_file, 'r') as test_file:
            testdef = yaml.safe_load(test_file)

        # set testdef metadata in base class
        self.store_testdef(testdef, commit_id)

        os.chdir(cwd)
        if not self.valid:
            raise RuntimeError("Unable to get test definition from %s (%s)" % (self.vcs_binary, self.parameters))

        self.results = {'success': commit_id}
        return connection


class BzrRepoAction(RepoAction):
    """
    Each repo action is for a single repository,
    tests using multiple repositories get multiple
    actions.
    """

    priority = 0  # FIXME: increase priority once this is working

    def __init__(self):
        super(BzrRepoAction, self).__init__()
        self.name = "bzr-repo-action"
        self.description = "apply bazaar repository of tests to the test image"
        self.summary = "branch a bzr test repo"
        self.vcs_binary = "/usr/bin/bzr"
        self.testdef = None

    @classmethod
    def accepts(cls, repo_type):
        if repo_type == 'bzr':
            return True
        return False

    def run(self, connection, args=None):
        super(BzrRepoAction, self).run(connection, args)
        runner_path = os.path.join(self.data['mount_action']['mntdir'], 'tests', self.parameters['test_name'])
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
        with open(yaml_file, 'r') as test_file:
            self.testdef = yaml.safe_load(test_file)

        # set testdef metadata in base class
        self.store_testdef(self.testdef, revision)

        return connection


class TarRepoAction(RepoAction):

    priority = 0  # FIXME: increase priority once this is working

    def __init__(self):
        super(TarRepoAction, self).__init__()
        self.name = "tar-repo-action"
        self.description = "apply a tarball of tests to the test image"
        self.summary = "unpack tar test repo"
        self.vcs_binary = "/bin/tar"

    @classmethod
    def accepts(cls, repo_type):
        if repo_type == 'tar':
            return True
        return False

    def run(self, connection, args=None):
        """
        Extracts the provided encoded tar archive into tmpdir.
        """
        super(TarRepoAction, self).run(connection, args)
        runner_path = os.path.join(self.data['mount_action']['mntdir'], 'tests', self.parameters['test_name'])
        temp_tar = os.path.join(self.data['mount_action']['mntdir'], "tar-repo.tar")

        try:
            if not os.path.isdir(runner_path):
                self._log("Creating directory to extract the tar archive into.")
                os.makedirs(runner_path)

            encoded_in = io.StringIO(self.parameters['repository'])
            decoded_out = io.StringIO()
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


class UrlRepoAction(RepoAction):

    priority = 0  # FIXME: increase priority once this is working

    def __init__(self):
        super(UrlRepoAction, self).__init__()
        self.name = "url-repo-action"
        self.description = "apply a single test file to the test image"
        self.summary = "download file test"
        self.tmpdir = None  # FIXME: needs to be a /mntpoint/lava-%hostname/ directory.
        self.testdef = None

    @classmethod
    def accepts(cls, repo_type):
        if repo_type == 'url':
            return True
        return False

    def run(self, connection, args=None):
        """Download the provided test definition file into tmpdir."""
        super(UrlRepoAction, self).run(connection, args)
        runner_path = os.path.join(self.data['mount_action']['mntdir'], 'tests', self.parameters['test_name'])

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
        for elem in " $&()\"'<>/\\|;`":
            i.extend(indices(self.testdef["metadata"]["name"], elem))
        if i:
            msg = "Test name contains invalid symbol(s) at position(s): %s" % ", ".join(str(x) for x in i)
            raise JobError(msg)

        try:
            self.testdef["metadata"]["name"].encode()
        except UnicodeEncodeError as encode:
            msg = "Test name contains non-ascii symbols: %s" % encode
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
        Each time a test definition is processed by a handler, a new set of
        overlay files are needed, based on that test definition. Basic overlay
        files are created by TestOverlayAction. More complex scripts like the
        install:deps script and the main run script have custom Actions.
        """
        index = {}
        self.internal_pipeline = Pipeline(parent=self, job=self.job)
        for testdef in self.parameters['test']['definitions']:
            handler = RepoAction.select(testdef['from'])()

            # set the full set of job YAML parameters for this handler as handler parameters.
            handler.parameters = testdef
            # store the correct test_name before incrementing the local index dict
            handler.parameters['test_name'] = "%s_%s" % (len(list(index.keys())), handler.parameters['name'])

            # copy details into the overlay, one per handler but the same class each time.
            overlay = TestOverlayAction()
            overlay.parameters = testdef
            overlay.parameters['test_name'] = handler.parameters['test_name']
            overlay.test_uuid = handler.uuid

            # add install handler
            installer = TestInstallAction()
            installer.parameters = testdef
            installer.parameters['test_name'] = handler.parameters['test_name']
            installer.test_uuid = handler.uuid

            # add runsh handler
            runsh = TestRunnerAction()
            runsh.parameters = testdef
            runsh.parameters['test_name'] = handler.parameters['test_name']
            runsh.test_uuid = handler.uuid

            index[len(list(index.keys()))] = handler.parameters['name']
            self.internal_pipeline.add_action(handler)

            # add overlay handlers to the pipeline
            self.internal_pipeline.add_action(overlay)
            self.internal_pipeline.add_action(installer)
            self.internal_pipeline.add_action(runsh)

            # FIXME: the outer pipeline may add unwanted data to the parameters['test']

    def validate(self):
        super(TestDefinitionAction, self).validate()
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

    def run(self, connection, args=None):
        """
        Creates the list of test definitions for this Test

        :param connection: Connection object, if any.
        :param args: Not used.
        :return: the received Connection.
        """
        self._log("Loading test definitions")

        connection = self.internal_pipeline.run_actions(connection)

        self._log("lava-test-runner.conf")
        with open('%s/lava-test-runner.conf' % self.data['mount_action']['mntdir'], 'a') as runner_conf:
            for handler in self.internal_pipeline.actions:
                if isinstance(handler, RepoAction):
                    runner_conf.write(handler.runner)

        return connection


class TestOverlayAction(TestAction):

    def __init__(self):
        """
        TestOverlayAction is a simple helper to do the same routine boilerplate
        for every RepoAction, tweaking the data for the specific parameters of
        the RepoAction. It also defines the handle_parameters call which other
        custom overlay actions may require.

        Each test definition handler has a separate overlay added to the pipeline,
        so the overlay has access to the same parameters as the handler and is
        always executed immediately after the relevant handler.
        """
        super(TestOverlayAction, self).__init__()
        self.name = "test-overlay"
        self.description = "overlay test support files onto image"
        self.summary = "applying LAVA test overlay"
        self.test_uuid = None  # Match the overlay to the handler

    def validate(self):
        if 'path' not in self.parameters:
            self.errors = "Missing path in parameters"

    # FIXME: still needs porting. LAVA-1583
    def handle_parameters(self, filename, testdef):

        with open(filename, 'w') as runsh:

            # inject default parameters that was defined in yaml first
            runsh.write('###default parameters from yaml###\n')
            if 'params' in testdef:
                for def_param_name, def_param_value in list(testdef['params'].items()):
                    runsh.write('%s=\'%s\'\n' % (def_param_name, def_param_value))
            runsh.write('######\n')

            # inject the parameters that were set in job submission.
            runsh.write('###test parameters from json###\n')
            if 'test_params' in self.parameters and self.parameters['test_params'] != '':
                # FIXME: <security> use ast.literal_eval and check support - test_params is tainted user-input.
                # _test_params_temp = eval(self._sw_sources[0]['test_params'])
                _test_params_temp = ast.literal_eval(self.parameters['test_params'])
                for param_name, param_value in list(_test_params_temp.items()):
                    runsh.write('%s=\'%s\'\n' % (param_name, param_value))
            runsh.write('######\n')

    def run(self, connection, args=None):
        runner_path = self.data['test'][self.test_uuid]['overlay_path'][self.parameters['test_name']]
        # now read the YAML to create a testdef dict to retrieve metadata
        yaml_file = os.path.join(runner_path, self.parameters['path'])
        # FIXME: check the existence at the same time as the open.
        if not os.path.exists(yaml_file):
            raise JobError("Unable to find test definition YAML: %s" % yaml_file)

        with open(yaml_file, 'r') as test_file:
            testdef = yaml.safe_load(test_file)

        # FIXME: change lava-test-runner to accept a variable instead of duplicating the YAML?
        with open("%s/testdef.yaml" % runner_path, 'w') as run_file:
            yaml.safe_dump(testdef, run_file)

        # write out the UUID of each test definition.
        # FIXME: is this necessary any longer?
        with open('%s/uuid' % runner_path, 'w') as uuid:
            uuid.write(self.test_uuid)

        # FIXME: does this match old-world test-shell & is it needed?
        with open('%s/testdef_metadata' % runner_path, 'w') as metadata:
            metadata.write(yaml.safe_dump(self.data['test'][self.test_uuid]['testdef_metadata']))

        # Need actions for the run.sh script (calling parameter support in base class)
        # and install script (also calling parameter support here.)
        # this run then only does the incidental files.

        self.results = {'success': self.test_uuid}
        return connection


class TestInstallAction(TestOverlayAction):

    def __init__(self):
        """
        This Action will need a run check that the file does not exist
        and then it will create it.
        The parameter action will need a run check that the file does
        exist and then it will append to it.
        RuntimeError if either fail.
        TestOverlayAction will then add TestInstallAction to an
        internal pipeline followed by TestParameterAction then
        run the internal_pipeline at the start of the TestOverlayAction
        run step.
        """
        super(TestInstallAction, self).__init__()
        self.test_uuid = None  # Match the overlay to the handler
        self.name = "test-install-overlay"
        self.description = "overlay dependency installation support files onto image"
        self.summary = "applying LAVA test install scripts"

    def run(self, connection, args=None):

        runner_path = self.data['test'][self.test_uuid]['overlay_path'][self.parameters['test_name']]
        # now read the YAML to create a testdef dict to retrieve metadata
        yaml_file = os.path.join(runner_path, self.parameters['path'])
        if not os.path.exists(yaml_file):
            raise JobError("Unable to find test definition YAML: %s" % yaml_file)

        with open(yaml_file, 'r') as test_file:
            testdef = yaml.safe_load(test_file)

        if 'install' not in testdef:
            self.results = {'skipped': self.test_uuid}
            return

        if 'skip_install' not in testdef:
            testdef['skip_install'] = ''

        # hostdir = self.data['test'][self.test_uuid]['overlay_path'][self.parameters['test_name']]
        filename = '%s/install.sh' % runner_path
        self.handle_parameters(filename, testdef)

        with open(filename, 'w') as install_file:
            if testdef['skip_install'] != 'keys':
                sources = testdef['install'].get('keys', [])
                for src in sources:
                    install_file.write('lava-add-keys %s' % src)
                    install_file.write('\n')

            if testdef['skip_install'] != 'sources':
                sources = testdef['install'].get('sources', [])
                for src in sources:
                    install_file.write('lava-add-sources %s' % src)
                    install_file.write('\n')

            if testdef['skip_install'] != 'deps':
                # generic dependencies - must be named the same across all distros
                # supported by the testdef
                deps = testdef['install'].get('deps', [])

                # distro-specific dependencies
                deps = deps + testdef['install'].get('deps-' + self.parameters['deployment_data']['distro'], [])

                if deps:
                    install_file.write('lava-install-packages ')
                    for dep in deps:
                        install_file.write('%s ' % dep)
                    install_file.write('\n')

            if testdef['skip_install'] != 'steps':
                steps = testdef['install'].get('steps', [])
                if steps:
                    for cmd in steps:
                        install_file.write('%s\n' % cmd)
        self.results = {'success': self.test_uuid}
        return connection


class TestRunnerAction(TestOverlayAction):

    def __init__(self):
        super(TestRunnerAction, self).__init__()
        self.name = "test-runscript-overlay"
        self.description = "overlay run script onto image"
        self.summary = "applying LAVA test run script"

    def run(self, connection, args=None):

        runner_path = self.data['test'][self.test_uuid]['overlay_path'][self.parameters['test_name']]
        # now read the YAML to create a testdef dict to retrieve metadata
        yaml_file = os.path.join(runner_path, self.parameters['path'])
        if not os.path.exists(yaml_file):
            raise JobError("Unable to find test definition YAML: %s" % yaml_file)

        with open(yaml_file, 'r') as test_file:
            testdef = yaml.safe_load(test_file)

        filename = '%s/run.sh' % runner_path
        self.handle_parameters(filename, testdef)

        with open(filename, 'a') as runsh:

            runsh.write('set -e\n')
            runsh.write('export TESTRUN_ID=%s\n' % testdef['metadata']['name'])
            runsh.write('cd %s\n' % self.data['test'][self.test_uuid]['runner_path'][self.parameters['test_name']])
            runsh.write('UUID=`cat uuid`\n')
            runsh.write('echo "<LAVA_SIGNAL_STARTRUN $TESTRUN_ID $UUID>"\n')
            runsh.write('#wait for an ack from the dispatcher\n')
            runsh.write('read\n')
            steps = testdef['run'].get('steps', [])
            if steps:
                for cmd in steps:
                    runsh.write('%s\n' % cmd)
            runsh.write('echo "<LAVA_SIGNAL_ENDRUN $TESTRUN_ID $UUID>"\n')
            runsh.write('#wait for an ack from the dispatcher\n')
            runsh.write('read\n')

        self.results = {'success': self.test_uuid, "filename": filename}
        return connection
