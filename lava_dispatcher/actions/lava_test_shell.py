#!/usr/bin/python

# Copyright (C) 2012 Linaro Limited
#
# Author: Andy Doan <andy.doan@linaro.org>
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

# LAVA Test Shell implementation details
# ======================================
#
# The idea of lava-test-shell is a YAML test definition is "compiled" into a
# job that is run when the device under test boots and then the output of this
# job is retrieved and analyzed and turned into a bundle of results.
#
# In practice, this means a hierarchy of directories and files is created
# during test installation, a sub-hierarchy is created during execution to
# hold the results and these latter sub-hierarchy whole lot is poked at on the
# host during analysis.
#
# On Ubuntu and OpenEmbedded, the hierarchy is rooted at /lava.  / is mounted
# read-only on Android, so there we root the hierarchy at /data/lava.  I'll
# assume Ubuntu paths from here for simplicity.
#
# The directory tree that is created during installation looks like this:
#
# /lava/
#    bin/                          This directory is put on the path when the
#                                  test code is running -- these binaries can
#                                  be viewed as a sort of device-side "API"
#                                  for test authors.
#       lava-test-runner           The job that runs the tests on boot.
#       lava-test-shell            A helper to run a test suite.
#       lava-test-case             A helper to record information about a test
#                                  result.
#       lava-test-case-attach      A helper to attach a file to a test result.
#    tests/
#       ${IDX}_${TEST_ID}/         One directory per test to be executed.
#          uuid                    The "analyzer_assigned_uuid" of the
#                                  test_run that is being generated.
#          testdef.yml             The test definition.
#          testdef_metadata        Metadata extracted from test definition.
#          install.sh              The install steps.
#          run.sh                  The run steps.
#          [repos]                 The test definition can specify bzr or git
#                                  repositories to clone into this directory.
#
# In addition, a file /etc/lava-test-runner.conf is created containing the
# names of the directories in /lava/tests/ to execute.
#
# During execution, the following files are created:
#
# /lava/
#    results/
#       hwcontext/                 Each test_run in the bundle has the same
#                                  hw & sw context info attached to it.
#          cpuinfo.txt             Hardware info.
#          meminfo.txt             Ditto.
#       swcontext/
#          build.txt               Software info.
#          pkgs.txt                Ditto
#       ${IDX}_${TEST_ID}-${TIMESTAMP}/
#          testdef.yml
#          testdef_metadata
#          stdout.log
#          return_code             The exit code of run.sh.
#          analyzer_assigned_uuid
#          attachments/
#             install.sh
#             run.sh
#             ${FILENAME}          The attached data.
#             ${FILENAME}.mimetype  The mime type of the attachment.
#           attributes/
#              ${ATTRNAME}         Content is value of attribute
#          tags/
#             ${TAGNAME}           Content of file is ignored.
#          results/
#             ${TEST_CASE_ID}/     Names the test result.
#                result            (Optional)
#                measurement
#                units
#                message
#                timestamp
#                duration
#                attributes/
#                   ${ATTRNAME}    Content is value of attribute
#                attachments/      Contains attachments for test results.
#                   ${FILENAME}           The attached data.
#                   ${FILENAME}.mimetype  The mime type of the attachment.
#
# After the test run has completed, the /lava/results directory is pulled over
# to the host and turned into a bundle for submission to the dashboard.

from datetime import datetime
import glob
import logging
import os
import pexpect
import pkg_resources
import shutil
import stat
import subprocess
import tempfile
import time
from uuid import uuid4

import yaml

from linaro_dashboard_bundle.io import DocumentIO

import lava_dispatcher.lava_test_shell as lava_test_shell
from lava_dispatcher.signals import SignalDirector
from lava_dispatcher import utils

from lava_dispatcher.actions import BaseAction
from lava_dispatcher.client.base import wait_for_prompt
from lava_dispatcher.device.target import Target
from lava_dispatcher.downloader import download_image

LAVA_TEST_DIR = '%s/../../lava_test_shell' % os.path.dirname(__file__)
LAVA_TEST_ANDROID = '%s/lava-test-runner-android' % LAVA_TEST_DIR
LAVA_TEST_UBUNTU = '%s/lava-test-runner-ubuntu' % LAVA_TEST_DIR
LAVA_TEST_UPSTART = '%s/lava-test-runner.conf' % LAVA_TEST_DIR
LAVA_TEST_INITD = '%s/lava-test-runner.init.d' % LAVA_TEST_DIR
LAVA_TEST_SHELL = '%s/lava-test-shell' % LAVA_TEST_DIR
LAVA_TEST_CASE = '%s/lava-test-case' % LAVA_TEST_DIR
LAVA_TEST_CASE_ATTACH = '%s/lava-test-case-attach' % LAVA_TEST_DIR
LAVA_TEST_RUN_ATTACH = '%s/lava-test-run-attach' % LAVA_TEST_DIR

Target.android_deployment_data['lava_test_runner'] = LAVA_TEST_ANDROID
Target.android_deployment_data['lava_test_shell'] = LAVA_TEST_SHELL
Target.android_deployment_data['lava_test_case'] = LAVA_TEST_CASE
Target.android_deployment_data['lava_test_case_attach'] = LAVA_TEST_CASE_ATTACH
Target.android_deployment_data['lava_test_run_attach'] = LAVA_TEST_RUN_ATTACH
Target.android_deployment_data['lava_test_sh_cmd'] = '/system/bin/mksh'
Target.android_deployment_data['lava_test_dir'] = '/data/lava'
Target.android_deployment_data['lava_test_results_part_attr'] = 'data_part_android_org'

Target.ubuntu_deployment_data['lava_test_runner'] = LAVA_TEST_UBUNTU
Target.ubuntu_deployment_data['lava_test_shell'] = LAVA_TEST_SHELL
Target.ubuntu_deployment_data['lava_test_case'] = LAVA_TEST_CASE
Target.ubuntu_deployment_data['lava_test_case_attach'] = LAVA_TEST_CASE_ATTACH
Target.ubuntu_deployment_data['lava_test_run_attach'] = LAVA_TEST_RUN_ATTACH
Target.ubuntu_deployment_data['lava_test_sh_cmd'] = '/bin/bash'
Target.ubuntu_deployment_data['lava_test_dir'] = '/lava'
Target.ubuntu_deployment_data['lava_test_results_part_attr'] = 'root_part'

Target.oe_deployment_data['lava_test_runner'] = LAVA_TEST_UBUNTU
Target.oe_deployment_data['lava_test_shell'] = LAVA_TEST_SHELL
Target.oe_deployment_data['lava_test_case'] = LAVA_TEST_CASE
Target.oe_deployment_data['lava_test_case_attach'] = LAVA_TEST_CASE_ATTACH
Target.oe_deployment_data['lava_test_run_attach'] = LAVA_TEST_RUN_ATTACH
Target.oe_deployment_data['lava_test_sh_cmd'] = '/bin/sh'
Target.oe_deployment_data['lava_test_dir'] = '/lava'
Target.oe_deployment_data['lava_test_results_part_attr'] = 'root_part'

# 755 file permissions
XMOD = stat.S_IRWXU | stat.S_IXGRP | stat.S_IRGRP | stat.S_IXOTH | stat.S_IROTH

def _get_testdef_git_repo(testdef_repo, tmpdir, revision):
    cwd = os.getcwd()
    gitdir = os.path.join(tmpdir, 'gittestrepo')
    try:
        subprocess.check_call(['git', 'clone', testdef_repo, gitdir])
        if revision:
            os.chdir(gitdir)
            subprocess.check_call(['git', 'checkout', revision])
        return gitdir
    except Exception as e:
        logging.error('Unable to get test definition from git\n' + str(e))
    finally:
        os.chdir(cwd)


def _get_testdef_bzr_repo(testdef_repo, tmpdir, revision):
    bzrdir = os.path.join(tmpdir, 'bzrtestrepo')
    try:
        # As per bzr revisionspec, '-1' is "The last revision in a
        # branch".
        if revision is None:
            revision = '-1'

        subprocess.check_call(
            ['bzr', 'branch', '-r', revision, testdef_repo, bzrdir],
            env={'BZR_HOME': '/dev/null', 'BZR_LOG': '/dev/null'})
        return bzrdir
    except Exception as e:
        logging.error('Unable to get test definition from bzr\n' + str(e))


def _get_testdef_info(testdef, location):
    default = "None"
    metadata = {'os': default, 'devices': default, 'environment': default}
    metadata['description'] = str(testdef['metadata'].get('description',
                                                          default))
    metadata['format'] = str(testdef['metadata'].get('format', default))

    if location == 'URL':
        metadata['version'] = str(testdef['metadata'].get('version', default))

    # Convert list to comma separated string.
    if testdef['metadata'].get('os'):
        metadata['os'] = ','.join(testdef['metadata'].get('os', default))

    if testdef['metadata'].get('devices'):
        metadata['devices'] = ','.join(testdef['metadata'].get('devices',
                                                               default))

    if testdef['metadata'].get('environment'):
        metadata['environment'] = ','.join(
            testdef['metadata'].get('environment'))

    return metadata


class TestDefinitionLoader(object):
    """
    A TestDefinitionLoader knows how to load test definitions from the data
    provided in the job file.
    """

    def __init__(self, context, tmpbase):
        self.testdefs = []
        self.context = context
        self.tmpbase = tmpbase
        self.testdefs_by_uuid = {}

    def _append_testdef(self, testdef_obj):
        testdef_obj.load_signal_handler()
        self.testdefs.append(testdef_obj)
        self.testdefs_by_uuid[testdef_obj.uuid] = testdef_obj

    def load_from_url(self, url):
        tmpdir = utils.mkdtemp(self.tmpbase)
        testdef_file = download_image(url, self.context, tmpdir)
        with open(testdef_file, 'r') as f:
            logging.info('loading test definition')
            testdef = yaml.safe_load(f)

        idx = len(self.testdefs)

        testdef_metadata = {'url': url, 'location': 'URL'}
        testdef_metadata.update(_get_testdef_info(testdef, 'URL'))
        self._append_testdef(URLTestDefinition(self.context, idx, testdef,
                                               testdef_metadata))

    def load_from_repo(self, testdef_repo):
        tmpdir = utils.mkdtemp(self.tmpbase)
        if 'git-repo' in testdef_repo:
            repo = _get_testdef_git_repo(
                testdef_repo['git-repo'], tmpdir, testdef_repo.get('revision'))
            name = os.path.splitext(os.path.basename(testdef_repo['git-repo']))[0]
            info = _git_info(testdef_repo['git-repo'], repo, name)

        if 'bzr-repo' in testdef_repo:
            repo = _get_testdef_bzr_repo(
                testdef_repo['bzr-repo'], tmpdir, testdef_repo.get('revision'))
            name = testdef_repo['bzr-repo'].replace('lp:', '').split('/')[-1]
            info = _bzr_info(testdef_repo['bzr-repo'], repo, name)

        test = testdef_repo.get('testdef', 'lavatest.yaml')
        with open(os.path.join(repo, test), 'r') as f:
            logging.info('loading test definition ...')
            testdef = yaml.safe_load(f)

        idx = len(self.testdefs)
        self._append_testdef(
            RepoTestDefinition(self.context, idx, testdef, repo, info))


def _bzr_info(url, bzrdir, name):
    cwd = os.getcwd()
    try:
        os.chdir('%s' % bzrdir)
        revno = subprocess.check_output(['bzr', 'revno']).strip()
        return {
            'project_name': name,
            'branch_vcs': 'bzr',
            'branch_revision': revno,
            'branch_url': url,
            }
    finally:
        os.chdir(cwd)


def _git_info(url, gitdir, name):
    cwd = os.getcwd()
    try:
        os.chdir('%s' % gitdir)
        commit_id = subprocess.check_output(
            ['git', 'log', '-1', '--pretty=%H']).strip()
        return {
            'project_name': name,
            'branch_vcs': 'git',
            'branch_revision': commit_id,
            'branch_url': url,
            }
    finally:
        os.chdir(cwd)


class URLTestDefinition(object):
    """
    A test definition that was loaded from a URL.
    """

    def __init__(self, context, idx, testdef, testdef_metadata):
        self.context = context
        self.testdef = testdef
        self.testdef_metadata = testdef_metadata
        self.idx = idx
        self.test_run_id = '%s_%s' % (idx, self.testdef['metadata']['name'])
        self.uuid = str(uuid4())
        self._sw_sources = []
        self.handler = None

    def load_signal_handler(self):
        hook_data = self.testdef.get('handler')
        if not hook_data:
            return
        try:
            handler_name = hook_data['handler-name']
            logging.info("Loading handler named %s", handler_name)
            handler_eps = list(
                pkg_resources.iter_entry_points(
                    'lava.signal_handlers', handler_name))
            if len(handler_eps) == 0:
                logging.error("No handler named %s found", handler_name)
                return
            elif len(handler_eps) > 1:
                logging.warning(
                    "Multiple handlers named %s found.  Picking one arbitrarily.",
                    handler_name)
            handler_ep = handler_eps[0]
            logging.info("Loading handler from %s" % handler_ep.dist)
            handler_cls = handler_ep.load()
            self.handler = handler_cls(self, **hook_data.get('params', {}))
        except Exception:
            logging.exception("loading handler failed")

    def _create_repos(self, testdir):
        cwd = os.getcwd()
        try:
            os.chdir(testdir)

            for repo in self.testdef['install'].get('bzr-repos', []):
                logging.info("bzr branch %s" % repo)
                # Pass non-existent BZR_HOME value, or otherwise bzr may
                # have non-reproducible behavior because it may rely on
                # bzr whoami value, presence of ssh keys, etc.
                subprocess.check_call(['bzr', 'branch', repo],
                    env={'BZR_HOME': '/dev/null', 'BZR_LOG': '/dev/null'})
                name = repo.replace('lp:', '').split('/')[-1]
                self._sw_sources.append(_bzr_info(repo, name, name))

            for repo in self.testdef['install'].get('git-repos', []):
                logging.info("git clone %s" % repo)
                subprocess.check_call(['git', 'clone', repo])
                name = os.path.splitext(os.path.basename(repo))[0]
                self._sw_sources.append(_git_info(repo, name, name))
        finally:
            os.chdir(cwd)

    def _create_target_install(self, hostdir, targetdir):
        with open('%s/install.sh' % hostdir, 'w') as f:
            f.write('set -ex\n')
            f.write('cd %s\n' % targetdir)

            # TODO how should we handle this for Android?
            deps = self.testdef['install'].get('deps', [])
            if deps:
                f.write('sudo apt-get update\n')
                f.write('sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -q ')
                for dep in deps:
                    f.write('%s ' % dep)
                f.write('\n')

            steps = self.testdef['install'].get('steps', [])
            if steps:
                for cmd in steps:
                    f.write('%s\n' % cmd)

    def copy_test(self, hostdir, targetdir):
        """Copy the files needed to run this test to the device.

        :param hostdir: The location on the device filesystem to copy too.
        :param targetdir: The location `hostdir` will have when the device
            boots.
        """
        utils.ensure_directory(hostdir)
        with open('%s/testdef.yaml' % hostdir, 'w') as f:
            f.write(yaml.dump(self.testdef))

        with open('%s/uuid' % hostdir, 'w') as f:
            f.write(self.uuid)

        with open('%s/testdef_metadata' % hostdir, 'w') as f:
            f.write(yaml.safe_dump(self.testdef_metadata))

        if 'install' in self.testdef:
            self._create_repos(hostdir)
            self._create_target_install(hostdir, targetdir)

        with open('%s/run.sh' % hostdir, 'w') as f:
            f.write('set -e\n')
            f.write('export TESTRUN_ID=%s\n' % self.test_run_id)
            f.write('cd %s\n' % targetdir)
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


class RepoTestDefinition(URLTestDefinition):
    """
    A test definition that was loaded from a VCS repository.

    The difference is that the files from the repository are also copied to
    the device.
    """

    def __init__(self, context, idx, testdef, repo, info):
        testdef_metadata = {}
        testdef_metadata.update({'url': info['branch_url']})
        testdef_metadata.update({'location': info['branch_vcs'].upper()})
        testdef_metadata.update({'version': info['branch_revision']})
        testdef_metadata.update(_get_testdef_info(testdef, 'REPO'))

        URLTestDefinition.__init__(self, context, idx, testdef,
                                   testdef_metadata)
        self.repo = repo
        self._sw_sources.append(info)

    def copy_test(self, hostdir, targetdir):
        shutil.copytree(self.repo, hostdir, symlinks=True)
        URLTestDefinition.copy_test(self, hostdir, targetdir)
        logging.info('copied all test files')


class cmd_lava_test_shell(BaseAction):

    parameters_schema = {
        'type': 'object',
        'properties': {
            'testdef_urls': {'type': 'array',
                             'items': {'type': 'string'},
                             'optional': True},
            'testdef_repos': {'type': 'array',
                              'items': {'type': 'object',
                                        'properties':
                                            {'git-repo': {'type': 'string',
                                                          'optional': True},
                                             'bzr-repo': {'type': 'string',
                                                          'optional': True},
                                             'revision': {'type': 'string',
                                                          'optional': True},
                                             'testdef': {'type': 'string',
                                                         'optional': True}
                                             },
                                        'additionalProperties': False},
                              'optional': True
                              },
            'timeout': {'type': 'integer', 'optional': True},
            },
        'additionalProperties': False,
        }

    def run(self, testdef_urls=None, testdef_repos=None, timeout=-1):
        target = self.client.target_device
        self._assert_target(target)

        testdefs_by_uuid = self._configure_target(target, testdef_urls, testdef_repos)

        signal_director = SignalDirector(self.client, testdefs_by_uuid)

        with target.runner() as runner:
            runner.wait_for_prompt(timeout)
            runner._connection.sendline(
                "%s/bin/lava-test-runner" % target.deployment_data['lava_test_dir'])
            start = time.time()
            if timeout == -1:
                timeout = runner._connection.timeout
            initial_timeout = timeout
            while self._keep_running(runner, timeout, signal_director):
                elapsed = time.time() - start
                timeout = int(initial_timeout - elapsed)

        self._bundle_results(target, signal_director, testdefs_by_uuid)

    def _keep_running(self, runner, timeout, signal_director):
        patterns = [
                '<LAVA_TEST_RUNNER>: exiting',
                pexpect.EOF,
                pexpect.TIMEOUT,
                '<LAVA_SIGNAL_(\S+) ([^>]+)>',
                ]

        idx = runner._connection.expect(patterns, timeout=timeout)
        if idx == 0:
            logging.info('lava_test_shell seems to have completed')
        elif idx == 1:
            logging.warn('lava_test_shell connection dropped')
        elif idx == 2:
            logging.warn('lava_test_shell has timed out')
        elif idx == 3:
            name, params = runner._connection.match.groups()
            logging.debug("Received signal <%s>" % name)
            params = params.split()
            try:
                signal_director.signal(name, params)
            except:
                logging.exception("on_signal failed")
            runner._connection.sendline('echo LAVA_ACK')
            return True

        return False

    def _copy_runner(self, mntdir, target):
        runner = target.deployment_data['lava_test_runner']
        shutil.copy(runner, '%s/bin/lava-test-runner' % mntdir)
        os.chmod('%s/bin/lava-test-runner' % mntdir, XMOD)

        shcmd = target.deployment_data['lava_test_sh_cmd']

        for key in ['lava_test_shell', 'lava_test_case_attach', 'lava_test_run_attach']:
            fname = target.deployment_data[key]
            with open(fname, 'r') as fin:
                with open('%s/bin/%s' % (mntdir, os.path.basename(fname)), 'w') as fout:
                    fout.write("#!%s\n\n" % shcmd)
                    fout.write(fin.read())
                    os.fchmod(fout.fileno(), XMOD)

        tc = target.deployment_data['lava_test_case']
        with open(tc, 'r') as fin:
            with open('%s/bin/lava-test-case' % mntdir, 'w') as fout:
                fout.write('#!%s\n\n' % shcmd)
                fout.write(fin.read())
                os.fchmod(fout.fileno(), XMOD)

    def _mk_runner_dirs(self, mntdir):
        utils.ensure_directory('%s/bin' % mntdir)
        utils.ensure_directory_empty('%s/tests' % mntdir)
        utils.ensure_directory_empty('%s/results' % mntdir)

    def _configure_target(self, target, testdef_urls, testdef_repos):
        ldir = target.deployment_data['lava_test_dir']

        results_part = target.deployment_data['lava_test_results_part_attr']
        results_part = getattr(target.config, results_part)

        with target.file_system(results_part, 'lava') as d:
            self._mk_runner_dirs(d)
            self._copy_runner(d, target)

            testdef_loader = TestDefinitionLoader(self.context, target.scratch_dir)

            if testdef_urls:
                for url in testdef_urls:
                    testdef_loader.load_from_url(url)

            if testdef_repos:
                for repo in testdef_repos:
                    testdef_loader.load_from_repo(repo)

            tdirs = []
            for testdef in testdef_loader.testdefs:
                # android mount the partition under /system, while ubuntu
                # mounts under /, so we have hdir for where it is on the
                # host and tdir for how the target will see the path
                hdir = '%s/tests/%s' % (d, testdef.test_run_id)
                tdir = '%s/tests/%s' % (ldir, testdef.test_run_id)
                testdef.copy_test(hdir, tdir)
                tdirs.append(tdir)

            with open('%s/lava-test-runner.conf' % d, 'w') as f:
                for testdir in tdirs:
                    f.write('%s\n' % testdir)

        return testdef_loader.testdefs_by_uuid

    def _bundle_results(self, target, signal_director, testdefs_by_uuid):
        """ Pulls the results from the target device and builds a bundle
        """
        results_part = target.deployment_data['lava_test_results_part_attr']
        results_part = getattr(target.config, results_part)
        rdir = self.context.host_result_dir

        with target.file_system(results_part, 'lava') as d:
            results_dir = os.path.join(d, 'results')
            bundle = lava_test_shell.get_bundle(results_dir, testdefs_by_uuid)
            # lava/results must be empty, but we keep a copy named
            # lava/results-XXXXXXXXXX for post-mortem analysis
            timestamp = datetime.now().strftime("%s")
            os.rename(results_dir, results_dir + '-' + timestamp)
            os.mkdir(results_dir)

        signal_director.postprocess_bundle(bundle)

        (fd, name) = tempfile.mkstemp(
            prefix='lava-test-shell', suffix='.bundle', dir=rdir)
        with os.fdopen(fd, 'w') as f:
            DocumentIO.dump(f, bundle)

    def _assert_target(self, target):
        """ Ensure the target has the proper deployment data required by this
        action. This allows us to exit the action early rather than going 75%
        through the steps before discovering something required is missing
        """
        if not target.deployment_data:
            raise RuntimeError('Target includes no deployment_data')

        keys = ['lava_test_runner', 'lava_test_shell', 'lava_test_dir',
                'lava_test_sh_cmd']
        for k in keys:
            if k not in target.deployment_data:
                raise RuntimeError('Target deployment_data missing %s' % k)
