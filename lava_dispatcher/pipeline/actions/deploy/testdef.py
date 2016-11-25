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
import re
import yaml
import base64
import hashlib
import tarfile
import shutil
from collections import OrderedDict
from nose.tools import nottest
from lava_dispatcher.pipeline.action import (
    Action,
    InfrastructureError,
    JobError,
    Pipeline,
    TestError,
)
from lava_dispatcher.pipeline.actions.test import TestAction
from lava_dispatcher.pipeline.utils.strings import indices
from lava_dispatcher.pipeline.utils.vcs import BzrHelper, GitHelper
from lava_dispatcher.pipeline.utils.constants import (
    DEFAULT_V1_FIXUP,
    DEFAULT_V1_PATTERN,
    DEFAULT_TESTDEF_NAME_CLASS,
    DISPATCHER_DOWNLOAD_DIR,
)


def identify_test_definitions(parameters, namespace=None):
    """
    Iterates through the job parameters to identify all the test definitions,
    including those involved in repeat actions.
    """
    # All test definitions are deployed in each deployment - TestDefinitionAction needs to only run relevant ones.
    if namespace:
        test_actions = [action for action in parameters['actions'] if 'test' in action]
        namespace_tests = [action['test']['definitions'] for action in test_actions if 'namespace' in action['test'] and action['test']['namespace'] == namespace]
        return namespace_tests
    test_list = [action['test']['definitions'] for action in parameters['actions'] if 'test' in action]
    repeat_list = [action['repeat'] for action in parameters['actions'] if 'repeat' in action]
    if repeat_list:
        test_list.extend([testdef['test']['definitions'] for testdef in repeat_list[0]['actions'] if 'test' in testdef])
    return test_list


@nottest
def get_deployment_testdefs(parameters=None):
    """
    Identify the test definitions for each deployment within the job.
    """
    test_dict = OrderedDict()
    if parameters is None:
        return test_dict
    deploy_list = []
    for action in parameters['actions']:
        yaml_line = None
        namespace = None
        if 'deploy' in action:
            yaml_line = action['deploy']['yaml_line']
            namespace = action['deploy'].get('namespace', None)
            test_dict[yaml_line] = []
            deploy_list = get_deployment_tests(parameters, yaml_line)
        for deploy_action in deploy_list:
            if 'test' in deploy_action:
                if namespace and namespace == deploy_action['test'].get(
                        'namespace', None):
                    test_dict[yaml_line].append(deploy_action['test']['definitions'])
        deploy_list = []
    return test_dict


def get_deployment_tests(parameters, yaml_line):
    """
    Get the test YAML blocks according to which deployment precedes that test
    This allows multiple deployments to use distinct test definitions.
    """
    deploy = []
    seen = False
    for action in parameters['actions']:
        if 'deploy' in action:
            seen = False
        if 'deploy' in action and action['deploy']['yaml_line'] == yaml_line:
            seen = True
            continue
        if 'repeat' in action and seen:
            for repeat_action in action['repeat']['actions']:
                if 'test' in repeat_action:
                    deploy.append(repeat_action)
        if 'test' in action and seen:
            deploy.append(action)
    return deploy


def get_test_action_namespaces(parameters=None):
    """Iterates through the job parameters to identify all the test action
    namespaces."""
    test_namespaces = []
    for action in parameters['actions']:
        if 'test' in action:
            if action['test'].get('namespace', None):
                test_namespaces.append(action['test']['namespace'])
    repeat_list = [action['repeat']
                   for action in parameters['actions']
                   if 'repeat' in action]
    if repeat_list:
        test_namespaces.extend(
            [action['test']['namespace']
             for action in repeat_list[0]['actions']
             if 'test' in action and action['test'].get('namespace', None)])
    return test_namespaces


# pylint:disable=too-many-public-methods,too-many-instance-attributes,too-many-locals,too-many-branches


class RepoAction(Action):

    def __init__(self):
        super(RepoAction, self).__init__()
        self.name = "repo-action"
        self.description = "apply tests to the test image"
        self.summary = "repo base class"
        self.vcs = None
        self.runner = None
        self.default_pattern = DEFAULT_V1_PATTERN
        self.default_fixupdict = DEFAULT_V1_FIXUP
        self.uuid = None

    @classmethod
    def select(cls, repo_type):

        candidates = cls.__subclasses__()  # pylint: disable=no-member
        willing = [c for c in candidates if c.accepts(repo_type)]

        if len(willing) == 0:
            raise NotImplementedError(
                "No testdef_repo hander is available for the given repository type"
                " '%s'." % repo_type)

        # higher priority first
        willing.sort(key=lambda x: x.priority, reverse=True)
        return willing[0]

    def validate(self):
        if 'hostname' not in self.job.device:
            raise InfrastructureError("Invalid device configuration")
        if 'test_name' not in self.parameters:
            self.errors = "Unable to determine test_name"
            return
        if not isinstance(self, InlineRepoAction):
            if self.vcs is None:
                raise RuntimeError("RepoAction validate called super without setting the vcs")
            if not os.path.exists(self.vcs.binary):
                self.errors = "%s is not installed on the dispatcher." % self.vcs.binary
        super(RepoAction, self).validate()
        # FIXME: unused
        # list of levels involved in the repo actions for this overlay
        uuid_list = self.get_common_data('repo-action', 'uuid-list')
        if uuid_list:
            if self.uuid not in uuid_list:
                uuid_list.append(self.uuid)
        else:
            uuid_list = [self.uuid]
        self.set_common_data('repo-action', 'uuid-list', uuid_list)

    def run(self, connection, args=None):
        """
        The base class run() currently needs to run after the mount operation, i.e. as part of run() so that
        the path can be correctly set when writing the overlay.
        Better approach will be to create the entire overlay without mounting and then
        unpack an overlay.tgz after mounting.
        """
        connection = super(RepoAction, self).run(connection, args)
        # FIXME: standardise on set_common_data and get_common_data
        self.data.setdefault('test', {})
        self.data['test'].setdefault(self.uuid, {})
        self.data['test'][self.uuid].setdefault('runner_path', {})
        self.data['test'][self.uuid].setdefault('overlay_path', {})

        if args is None or 'test_name' not in args:
            raise RuntimeError("RepoAction run called via super without parameters as arguments")
        if 'namespace' in self.parameters:
            namespace = self.parameters['namespace']
            location = self.get_common_data(namespace, 'location')
            lava_test_results_dir = self.get_common_data(namespace,
                                                         'lava_test_results_dir')
            self.logger.debug("[%s namespace] Using %s at stage %s", namespace, lava_test_results_dir, self.stage)
        elif 'location' not in self.data['lava-overlay']:
            raise RuntimeError("Missing lava overlay location")
        else:
            location = self.data['lava-overlay']['location']
            lava_test_results_dir = self.data['lava_test_results_dir']
            self.logger.debug("Using %s", lava_test_results_dir)
        if not os.path.exists(location):
            raise RuntimeError("Overlay location does not exist")

        # runner_path is the path to read and execute from to run the tests after boot
        self.data['test'][self.uuid]['runner_path'][args['test_name']] = os.path.join(
            args['deployment_data']['lava_test_results_dir'] % self.job.job_id,
            str(self.stage),
            'tests',
            args['test_name']
        )
        # the location written into the lava-test-runner.conf (needs a line ending)
        self.runner = "%s\n" % self.data['test'][self.uuid]['runner_path'][args['test_name']]

        self.data['test'][self.uuid]['overlay_path'][args['test_name']] = os.path.join(
            self.data['test-definition']['overlay_dir'],
            str(self.stage),
            'tests',
            args['test_name']
        )

        # FIXME - is this needed? - the issue here is that the new model does not use fs.tgz
        # therefore, there may not be the same need to collate the dependent testdefs, all of the
        # YAML in the repo will still exist - this may change behaviour.
        # if 'test-case-deps' in testdef:
        #    self._get_dependent_test_cases(testdef)

        return connection

    def store_testdef(self, testdef, vcs_name, commit_id=None):
        """
        Allows subclasses to pass in the parsed testdef after the repository has been obtained
        and the specified YAML file can be read.
        The Connection uses the data in the test dict to retrieve the supplied parse pattern
        and the fixup dictionary, if specified.
        The Connection stores raw results in the same test dict.
        The main TestAction can then process the results.
        """
        self.data['test'][self.uuid]['testdef_metadata'] = \
            {'os': testdef['metadata'].get('os', ''),
             'devices': testdef['metadata'].get('devices', ''),
             'environment': testdef['metadata'].get('environment', ''),
             'branch_vcs': vcs_name,
             'project_name': testdef['metadata']['name']}

        if commit_id is not None:
            self.data['test'][self.uuid]['testdef_metadata']['commit_id'] = commit_id

        if 'parse' in testdef:
            pattern = testdef['parse'].get('pattern', '')
            fixup = testdef['parse'].get('fixupdict', '')
        else:
            pattern = self.default_pattern
            fixup = self.default_fixupdict
        self.data['test'][self.uuid].setdefault('testdef_pattern', {})
        self.data['test'][self.uuid]['testdef_pattern'].update({'pattern': pattern})
        self.data['test'][self.uuid]['testdef_pattern'].update({'fixupdict': fixup})
        self.logger.debug("uuid=%s testdef=%s",
                          self.uuid,
                          self.data['test'][self.uuid]['testdef_pattern'])


class GitRepoAction(RepoAction):  # pylint: disable=too-many-public-methods
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

    def validate(self):
        if 'repository' not in self.parameters:
            self.errors = "Git repository not specified in job definition"
        if 'path' not in self.parameters:
            self.errors = "Path to YAML file not specified in the job definition"
        if not self.valid:
            return
        self.vcs = GitHelper(self.parameters['repository'])
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

        # NOTE: the runner_path dir must remain empty until after the VCS clone, so let the VCS clone create the final dir
        runner_path = self.data['test'][self.uuid]['overlay_path'][self.parameters['test_name']]
        if os.path.exists(runner_path) and os.listdir(runner_path) == []:
            raise RuntimeError("Directory already exists and is not empty - duplicate Action?")

        # Clear the data
        if os.path.exists(runner_path):
            shutil.rmtree(runner_path)

        self.logger.info("Fetching tests from %s", self.parameters['repository'])
        commit_id = self.vcs.clone(runner_path, self.parameters.get('revision', None))
        if commit_id is None:
            raise RuntimeError("Unable to get test definition from %s (%s)" % (self.vcs.binary, self.parameters))
        self.results = {
            'success': commit_id,
            'repository': self.parameters['repository'], 'path': self.parameters['path']}

        # now read the YAML to create a testdef dict to retrieve metadata
        yaml_file = os.path.join(runner_path, self.parameters['path'])
        self.logger.debug("Tests stored (tmp) in %s", yaml_file)
        if not os.path.exists(yaml_file):
            raise JobError("Unable to find test definition YAML: %s" % yaml_file)
        with open(yaml_file, 'r') as test_file:
            testdef = yaml.safe_load(test_file)

        # set testdef metadata in base class
        self.store_testdef(testdef, 'git', commit_id)

        return connection


class BzrRepoAction(RepoAction):  # pylint: disable=too-many-public-methods
    """
    Each repo action is for a single repository,
    tests using multiple repositories get multiple
    actions.
    """

    priority = 1

    def __init__(self):
        super(BzrRepoAction, self).__init__()
        self.name = "bzr-repo-action"
        self.description = "apply bazaar repository of tests to the test image"
        self.summary = "branch a bzr test repo"
        self.testdef = None

    def validate(self):
        if 'repository' not in self.parameters:
            self.errors = "Bzr repository not specified in job definition"
        if 'path' not in self.parameters:
            self.errors = "Path to YAML file not specified in the job definition"
        if not self.valid:
            return
        self.vcs = BzrHelper(self.parameters['repository'])
        super(BzrRepoAction, self).validate()

    @classmethod
    def accepts(cls, repo_type):
        if repo_type == 'bzr':
            return True
        return False

    def run(self, connection, args=None):
        """
        Clone the bazar repository into a directory
        """

        connection = super(BzrRepoAction, self).run(connection, self.parameters)

        # NOTE: the runner_path dir must remain empty until after the VCS clone, so let the VCS clone create the final dir
        runner_path = os.path.join(self.data['test-definition']['overlay_dir'], 'tests', self.parameters['test_name'])

        commit_id = self.vcs.clone(runner_path, self.parameters.get('revision', None))
        if commit_id is None:
            raise RuntimeError("Unable to get test definition from %s (%s)" % (self.vcs.binary, self.parameters))
        self.results = {
            'success': commit_id,
            'repository': self.parameters['repository'],
            'path': self.parameters['path']
        }

        # now read the YAML to create a testdef dict to retrieve metadata
        yaml_file = os.path.join(runner_path, self.parameters['path'])
        if not os.path.exists(yaml_file):
            raise JobError("Unable to find test definition YAML: %s" % yaml_file)
        with open(yaml_file, 'r') as test_file:
            self.testdef = yaml.safe_load(test_file)

        # set testdef metadata in base class
        self.store_testdef(self.testdef, 'bzr', commit_id)

        return connection


class InlineRepoAction(RepoAction):  # pylint: disable=too-many-public-methods

    priority = 1

    def __init__(self):
        super(InlineRepoAction, self).__init__()
        self.name = "inline-repo-action"
        self.description = "apply inline test defintion to the test image"
        self.summary = "exctract inline test definition"

    def validate(self):
        if 'repository' not in self.parameters:
            self.errors = "Inline definition not specified in job definition"
        if not isinstance(self.parameters['repository'], dict):
            self.errors = "Invalid inline definition in job definition"
        if not self.valid:
            return
        super(InlineRepoAction, self).validate()

    @classmethod
    def accepts(cls, repo_type):
        if repo_type == 'inline':
            return True
        return False

    def run(self, connection, args=None):
        """
        Extract the inlined test definition and dump it onto the target image
        """

        # use the base class to populate the runner_path and overlay_path data into the context
        connection = super(InlineRepoAction, self).run(connection, self.parameters)

        # NOTE: the runner_path dir must remain empty until after the VCS clone, so let the VCS clone create the final dir
        runner_path = self.data['test'][self.uuid]['overlay_path'][self.parameters['test_name']]

        # Grab the inline test definition
        testdef = self.parameters['repository']
        sha1 = hashlib.sha1()

        # Dump the test definition and compute the sha1
        yaml_file = os.path.join(runner_path, self.parameters['path'])
        yaml_dirname = os.path.dirname(yaml_file)
        if yaml_dirname != '':
            os.makedirs(os.path.join(runner_path, yaml_dirname))
        with open(yaml_file, 'w') as test_file:
            data = yaml.safe_dump(testdef)
            sha1.update(data.encode('utf-8'))
            test_file.write(data)

        # set testdef metadata in base class
        self.store_testdef(self.parameters['repository'], 'inline',
                           self.parameters.get('revision',
                                               sha1.hexdigest()))
        return connection


class TarRepoAction(RepoAction):  # pylint: disable=too-many-public-methods

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
        connection = super(TarRepoAction, self).run(connection, args)
        runner_path = os.path.join(self.data['test-definition']['overlay_dir'], 'tests', self.parameters['test_name'])
        temp_tar = os.path.join(self.data['test-definition']['overlay_dir'], "tar-repo.tar")

        try:
            if not os.path.isdir(runner_path):
                self.logger.debug("Creating directory to extract the tar archive into.")
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


class UrlRepoAction(RepoAction):  # pylint: disable=too-many-public-methods

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
        runner_path = os.path.join(self.data['test-definition']['overlay_dir'], 'tests', self.parameters['test_name'])

        try:
            if not os.path.isdir(runner_path):
                self.logger.debug("Creating directory to download the url file into.")
                os.makedirs(runner_path)
            # we will not use 'testdef_file' here, we can get this info from URL
            # testdef_file = download_image(testdef_repo, context, urldir)
            # FIXME: this handler uses DownloaderAction.run()

        except OSError as exc:
            raise JobError('Unable to get test definition from url\n' + str(exc))
        finally:
            self.logger.info("Downloaded test definition file to %s.", runner_path)

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
        self.test_list = None
        self.stages = 0
        self.run_levels = {}

    def populate(self, parameters):
        """
        Each time a test definition is processed by a handler, a new set of
        overlay files are needed, based on that test definition. Basic overlay
        files are created by TestOverlayAction. More complex scripts like the
        install:deps script and the main run script have custom Actions.
        """
        index = []
        self.internal_pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        namespace = parameters.get('namespace', None)
        self.test_list = identify_test_definitions(self.job.parameters, namespace)
        if self.test_list:
            if namespace:
                self.set_common_data(namespace, 'test_list', self.test_list[0])
            else:
                self.set_common_data(self.name, 'test_list', self.test_list[0])
        for testdefs in self.test_list:
            for testdef in testdefs:
                # namespace support allows only running the install steps for the relevant
                # deployment as the next deployment could be a different OS.
                handler = RepoAction.select(testdef['from'])()

                # set the full set of job YAML parameters for this handler as handler parameters.
                handler.job = self.job
                handler.parameters = testdef
                # store the correct test_name before appending to the local index
                handler.parameters['test_name'] = "%s_%s" % (len(index), handler.parameters['name'])
                self.internal_pipeline.add_action(handler)
                # a genuinely unique ID based on the *database* JobID and
                # pipeline level for reproducibility and tracking -
                # {DB-JobID}_{PipelineLevel}, e.g. 15432.0_3.5.4
                handler.uuid = "%s_%s" % (self.job.job_id, handler.level)
                handler.stage = self.stages
                self.run_levels[testdef['name']] = self.stages
                if namespace:
                    self.set_common_data(namespace, 'stages', self.stages)
                else:
                    self.set_common_data('lava-test-shell', 'stages', self.stages)

                # copy details into the overlay, one per handler but the same class each time.
                overlay = TestOverlayAction()
                overlay.job = self.job
                overlay.parameters = testdef
                overlay.parameters['test_name'] = handler.parameters['test_name']
                overlay.test_uuid = handler.uuid

                # add install handler - uses job parameters
                installer = TestInstallAction()
                installer.job = self.job
                installer.parameters = testdef
                installer.parameters['test_name'] = handler.parameters['test_name']
                installer.test_uuid = handler.uuid

                # add runsh handler - uses job parameters
                runsh = TestRunnerAction()
                runsh.job = self.job
                runsh.parameters = testdef
                runsh.parameters['test_name'] = handler.parameters['test_name']
                runsh.test_uuid = handler.uuid

                index.append(handler.parameters['name'])

                # add overlay handlers to the pipeline
                self.internal_pipeline.add_action(overlay)
                self.internal_pipeline.add_action(installer)
                self.internal_pipeline.add_action(runsh)
                if namespace:
                    self.set_common_data(namespace, 'testdef_index', index)
                else:
                    self.set_common_data(self.name, 'testdef_index', index)
                self.stages += 1

    def validate(self):
        """
        TestDefinitionAction is part of the overlay and therefore part of the deployment -
        the internal pipeline then looks inside the job definition for details of the tests to deploy.
        Jobs with no test actions defined (empty test_list) are explicitly allowed.
        """
        super(TestDefinitionAction, self).validate()
        if not self.job:
            self.errors = "missing job object"
            return
        if 'actions' not in self.job.parameters:
            self.errors = "No actions defined in job parameters"
            return
        if not self.test_list:
            return

        exp = re.compile(DEFAULT_TESTDEF_NAME_CLASS)
        for testdefs in self.test_list:
            for testdef in testdefs:
                if 'parameters' in testdef:  # optional
                    if not isinstance(testdef['parameters'], dict):
                        self.errors = "Invalid test definition parameters"
                if 'from' not in testdef:
                    self.errors = "missing 'from' field in test definition %s" % testdef
                if 'name' not in testdef:
                    self.errors = "missing 'name' field in test definition %s" % testdef
                else:
                    res = exp.match(testdef['name'])
                    if not res:
                        self.errors = "Invalid characters found in test definition name: %s" % testdef['name']
        self.internal_pipeline.validate_actions()

    def run(self, connection, args=None):
        """
        Creates the list of test definitions for this Test

        :param connection: Connection object, if any.
        :param args: Not used.
        :return: the received Connection.
        """
        if 'namespace' in self.parameters:
            namespace = self.parameters['namespace']
            location = self.get_common_data(namespace, 'location')
            lava_test_results_dir = self.get_common_data(namespace,
                                                         'lava_test_results_dir')
        elif 'location' not in self.data['lava-overlay']:
            raise RuntimeError("Missing lava overlay location")
        else:
            location = self.data['lava-overlay']['location']
            lava_test_results_dir = self.data['lava_test_results_dir']
        if not os.path.exists(location):
            raise RuntimeError("Unable to find overlay location")
        self.logger.info("Loading test definitions")

        # overlay_path is the location of the files before boot
        self.data[self.name]['overlay_dir'] = os.path.abspath(
            "%s/%s" % (location, lava_test_results_dir))

        connection = super(TestDefinitionAction, self).run(connection, args)

        for name, stage in self.run_levels.items():
            self.logger.debug("lava-test-runner.conf name %s stage %s", name, stage)
            path = '%s/%s' % (self.data[self.name]['overlay_dir'], stage)
            self.logger.debug("Using lava-test-runner path: %s", path)
            with open('%s/%s/lava-test-runner.conf' % (self.data[self.name]['overlay_dir'], stage), 'a') as runner_conf:
                for handler in self.internal_pipeline.actions:
                    if isinstance(handler, RepoAction) and handler.stage == stage:
                        self.logger.debug("Writing to runner_conf %s %s" % (self.name, stage))
                        runner_conf.write(handler.runner)

        return connection


class TestOverlayAction(TestAction):  # pylint: disable=too-many-instance-attributes

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

    def handle_parameters(self, testdef):

        ret_val = ['###default parameters from test definition###\n']
        if 'params' in testdef:
            for def_param_name, def_param_value in list(testdef['params'].items()):
                if def_param_name is 'yaml_line':
                    continue
                ret_val.append('%s=\'%s\'\n' % (def_param_name, def_param_value))
        if 'parameters' in testdef:
            for def_param_name, def_param_value in list(testdef['parameters'].items()):
                if def_param_name is 'yaml_line':
                    continue
                ret_val.append('%s=\'%s\'\n' % (def_param_name, def_param_value))
        ret_val.append('######\n')
        # inject the parameters that were set in job submission.
        ret_val.append('###test parameters from job submission###\n')
        if 'parameters' in self.parameters and self.parameters['parameters'] != '':
            # turn a string into a local variable.
            for param_name, param_value in list(self.parameters['parameters'].items()):
                if param_name is 'yaml_line':
                    continue
                ret_val.append('%s=\'%s\'\n' % (param_name, param_value))
                self.logger.debug("%s='%s'", param_name, param_value)
        if 'params' in self.parameters and self.parameters['params'] != '':
            # turn a string into a local variable.
            for param_name, param_value in list(self.parameters['params'].items()):
                if param_name is 'yaml_line':
                    continue
                ret_val.append('%s=\'%s\'\n' % (param_name, param_value))
                self.logger.debug("%s='%s'", param_name, param_value)
        ret_val.append('######\n')
        return ret_val

    def run(self, connection, args=None):
        connection = super(TestOverlayAction, self).run(connection, args)
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

        self.results = {
            'success': self.test_uuid,
            'name': self.parameters['name'],
            'path': self.parameters['path'],
            'from': self.parameters['from'],
        }
        if self.parameters['from'] != 'inline':
            self.results['repository'] = self.parameters['repository']
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
        self.skip_list = ['keys', 'sources', 'deps', 'steps', 'git-repos',
                          'all']  # keep 'all' as the last item
        self.skip_options = []

    def validate(self):
        if 'skip_install' in self.parameters:
            if set(self.parameters['skip_install']) - set(self.skip_list):
                self.errors = "Unrecognised skip_install value"
            if 'all' in self.parameters['skip_install']:
                self.skip_options = self.skip_list[:-1]  # without last item
            else:
                self.skip_options = self.parameters['skip_install']
        super(TestInstallAction, self).validate()

    def run(self, connection, args=None):
        connection = super(TestInstallAction, self).run(connection, args)
        runner_path = self.data['test'][self.test_uuid]['overlay_path'][self.parameters['test_name']]
        # now read the YAML to create a testdef dict to retrieve metadata
        yaml_file = os.path.join(runner_path, self.parameters['path'])
        if not os.path.exists(yaml_file):
            raise JobError("Unable to find test definition YAML: %s" % yaml_file)

        with open(yaml_file, 'r') as test_file:
            testdef = yaml.safe_load(test_file)

        if 'install' not in testdef:
            self.results = {'skipped %s' % self.name: self.test_uuid}
            return

        filename = '%s/install.sh' % runner_path
        content = self.handle_parameters(testdef)

        # TODO: once the migration is complete, design a better way to do skip_install support.
        with open(filename, 'w') as install_file:
            for line in content:
                install_file.write(line)
            if 'keys' not in self.skip_options:
                sources = testdef['install'].get('keys', [])
                for src in sources:
                    install_file.write('lava-add-keys %s' % src)
                    install_file.write('\n')

            if 'sources' not in self.skip_options:
                sources = testdef['install'].get('sources', [])
                for src in sources:
                    install_file.write('lava-add-sources %s' % src)
                    install_file.write('\n')

            if 'deps' not in self.skip_options:
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

            if 'steps' not in self.skip_options:
                steps = testdef['install'].get('steps', [])
                if steps:
                    # Allow install steps to use the git-repo directly
                    # fake up the directory as it will be after the overlay is applied
                    # os.path.join refuses if the directory does not exist on the dispatcher
                    base = len(DISPATCHER_DOWNLOAD_DIR.split('/')) + 2
                    # skip job_id/action-tmpdir/ as well
                    install_dir = '/' + '/'.join(runner_path.split('/')[base:])
                    install_file.write("cd %s\n" % install_dir)
                    install_file.write("pwd\n")
                    for cmd in steps:
                        install_file.write('%s\n' % cmd)

            if 'git-repos' not in self.skip_options:
                repos = testdef['install'].get('git-repos', [])
                for repo in repos:
                    # tests should expect git clone https://path/dir/repo.git to create ./repo/
                    subdir = repo.replace('.git', '', len(repo) - 1)  # drop .git from the end, if present
                    dest_path = os.path.join(runner_path, os.path.basename(subdir))
                    commit_id = None
                    if isinstance(repo, str):
                        commit_id = GitHelper(repo).clone(dest_path)
                    if isinstance(repo, dict):
                        # TODO: We use 'skip_by_default' to check if this
                        # specific repository should be skipped. The value
                        # for 'skip_by_default' comes from job parameters.
                        url = repo.get('url', None)
                        branch = repo.get('branch', None)
                        destination = repo.get('destination', None)
                        if destination:
                            dest_path = os.path.join(runner_path, destination)
                            if os.path.abspath(runner_path) != os.path.dirname(
                                    dest_path):
                                raise RuntimeError(
                                    "Destination path is unacceptable %s" %
                                    destination)
                        commit_id = GitHelper(url).clone(dest_path,
                                                         branch=branch)
                    if commit_id is None:
                        raise RuntimeError(
                            "Unable to clone %s" % str((repo)))

        self.results = {'success': self.test_uuid}
        return connection


class TestRunnerAction(TestOverlayAction):

    def __init__(self):
        super(TestRunnerAction, self).__init__()
        # This name is used to tally the submitted definitions
        # to the definitions which actually reported results.
        # avoid changing the self.name of this class.
        self.name = "test-runscript-overlay"
        self.description = "overlay run script onto image"
        self.summary = "applying LAVA test run script"
        self.testdef_levels = {}  # allow looking up the testname from the level of this action

    def validate(self):
        namespace = self.parameters.get('namespace', None)
        if namespace:
            testdef_index = self.get_common_data(namespace, 'testdef_index')
        else:
            testdef_index = self.get_common_data('test-definition', 'testdef_index')
        if not testdef_index:
            self.errors = "Unable to identify test definition index"
        if len(testdef_index) != len(set(testdef_index)):
            self.errors = "Test definition names need to be unique."
        # convert from testdef_index {0: 'smoke-tests', 1: 'singlenode-advanced'}
        # to self.testdef_levels {'1.3.4.1': '0_smoke-tests', ...}
        for (count, name) in enumerate(testdef_index):
            if self.parameters['name'] == name:
                self.testdef_levels[self.level] = "%s_%s" % (count, name)
        if not self.testdef_levels:
            self.errors = "Unable to identify test definition names"
        current = self.get_common_data(self.name, 'testdef_levels')
        if current:
            current.update(self.testdef_levels)
        else:
            current = self.testdef_levels
        if namespace:
            self.set_common_data(namespace, 'testdef_levels', current)
        else:
            self.set_common_data(self.name, 'testdef_levels', current)

    def run(self, connection, args=None):
        connection = super(TestRunnerAction, self).run(connection, args)
        namespace = self.parameters.get('namespace', None)
        runner_path = self.data['test'][self.test_uuid]['overlay_path'][self.parameters['test_name']]
        # now read the YAML to create a testdef dict to retrieve metadata
        yaml_file = os.path.join(runner_path, self.parameters['path'])
        if not os.path.exists(yaml_file):
            raise JobError("Unable to find test definition YAML: %s" % yaml_file)
        if namespace:
            testdef_levels = self.get_common_data(namespace, 'testdef_levels')
        else:
            testdef_levels = self.get_common_data('test-runscript-overlay', 'testdef_levels')
        with open(yaml_file, 'r') as test_file:
            testdef = yaml.safe_load(test_file)

        self.logger.debug("runner path: %s test_uuid %s", runner_path, self.test_uuid)
        filename = '%s/run.sh' % runner_path
        content = self.handle_parameters(testdef)

        # the 'lava' testdef name is reserved
        if self.parameters['name'] == 'lava':
            raise TestError('The "lava" test definition name is reserved.')

        with open(filename, 'a') as runsh:
            for line in content:
                runsh.write(line)
            runsh.write('set -e\n')
            runsh.write('set -x\n')
            # use the testdef_index value for the testrun name to handle repeats at source
            runsh.write('export TESTRUN_ID=%s\n' % testdef_levels[self.level])
            runsh.write('cd %s\n' % self.data['test'][self.test_uuid]['runner_path'][self.parameters['test_name']])
            runsh.write('UUID=`cat uuid`\n')
            runsh.write('echo "<LAVA_SIGNAL_STARTRUN $TESTRUN_ID $UUID>"\n')
            steps = testdef.get('run', {}).get('steps', [])
            for cmd in steps:
                if '--cmd' in cmd or '--shell' in cmd:
                    cmd = re.sub(r'\$(\d+)\b', r'\\$\1', cmd)
                runsh.write('%s\n' % cmd)
            runsh.write('echo "<LAVA_SIGNAL_ENDRUN $TESTRUN_ID $UUID>"\n')

        self.results = {
            'success': self.test_uuid,
            "filename": filename,
            'name': self.parameters['name'],
            'path': self.parameters['path'],
            'from': self.parameters['from'],
        }
        if self.parameters['from'] != 'inline':
            self.results['repository'] = self.parameters['repository']
        return connection
