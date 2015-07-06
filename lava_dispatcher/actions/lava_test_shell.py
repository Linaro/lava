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
# On Ubuntu and OpenEmbedded, the hierarchy is rooted at
# /lava-$(DEVICE_HOSTNAME). / is mounted read-only on Android, so there we root
# the hierarchy at /data/lava-$(DEVICE_HOSTNAME). These directories can be
# configured with the value of the lava_test_dir configuration variable, and
# the values mentioned above are just their defaults.  See
# lava_dispatcher/deployment_data.py and lava_dispatcher/device/target.py for
# details.
#
# I'll assume Ubuntu paths from here for simplicity.
#
# The directory tree that is created during installation looks like this:
#
# /lava-$(DEVICE_HOSTNAME)/
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
# names of the directories in /lava-$(DEVICE_HOSTNAME)/tests/ to execute.
#
# During execution, the following files are created:
#
# /lava-$(DEVICE_HOSTNAME)/
#    results/
#       ${IDX}_${TEST_ID}-${TIMESTAMP}/
#          testdef.yml
#          testdef_metadata
#          stdout.log
#          install_return_code             The exit code of install.sh.
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
#           hwcontext/                 Each test_run in the bundle has the same
#                                  hw & sw context info attached to it.
#               cpuinfo.txt             Hardware info.
#               meminfo.txt             Ditto.
#           swcontext/
#               build.txt               Software info.
#               pkgs.txt                Ditto
#
# After the test run has completed, the /lava-$(DEVICE_HOSTNAME)/results
# directory is pulled over to the host and turned into a bundle for submission
# to the dashboard.

import re
from datetime import datetime
from glob import glob
import ast
import base64
import logging
import os
import pexpect
import pkg_resources
import shutil
import stat
import StringIO
import subprocess
import tarfile
import tempfile
import time
import sys
from uuid import uuid4

import yaml

from linaro_dashboard_bundle.io import DocumentIO

from lava_dispatcher.bundle import PrettyPrinter
import lava_dispatcher.lava_test_shell as lava_test_shell
from lava_dispatcher.lava_test_shell import parse_testcase_result
from lava_dispatcher.signals import SignalDirector
from lava_dispatcher import utils

from lava_dispatcher.actions import BaseAction
from lava_dispatcher.downloader import download_image
from lava_dispatcher.errors import GeneralError, CriticalError

LAVA_TEST_DIR = '%s/../lava_test_shell' % os.path.dirname(__file__)
LAVA_MULTI_NODE_TEST_DIR = '%s/../lava_test_shell/multi_node' % os.path.dirname(__file__)
LAVA_LMP_TEST_DIR = '%s/../lava_test_shell/lmp' % os.path.dirname(__file__)

LAVA_GROUP_FILE = 'lava-group'
LAVA_ROLE_FILE = 'lava-role'
LAVA_SELF_FILE = 'lava-self'
LAVA_SEND_FILE = 'lava-send'
LAVA_SYNC_FILE = 'lava-sync'
LAVA_WAIT_FILE = 'lava-wait'
LAVA_WAIT_ALL_FILE = 'lava-wait-all'
LAVA_MULTI_NODE_CACHE_FILE = '/tmp/lava_multi_node_cache.txt'
LAVA_LMP_CACHE_FILE = '/tmp/lava_lmp_cache.txt'

# 755 file permissions
XMOD = stat.S_IRWXU | stat.S_IXGRP | stat.S_IRGRP | stat.S_IXOTH | stat.S_IROTH

INVALID_CHARS = " $&()\"'<>/\\|;`"

repeat_cnt = 0


# Make the open function accept encodings in python < 3.x
if sys.version_info[0] < 3:
    import codecs
    open = codecs.open


def _validate_invalid_chars(parameter):
    i = []
    for e in INVALID_CHARS:
        i.extend(utils.indices(parameter, e))
    if i:
        msg = "Parameter '%s' contains invalid symbol(s) at position(s): %s" % \
              (parameter, ", ".join(map(str, i)))
        raise GeneralError(msg)


def _get_lava_proxy(context):
    return {'http_proxy': context.config.lava_proxy,
            'https_proxy': context.config.lava_proxy,
            'no_proxy': context.config.lava_no_proxy}


def _get_testdef_git_repo(testdef_repo, tmpdir, revision, proxy_env):
    cwd = os.getcwd()
    gitdir = os.path.join(tmpdir, 'gittestrepo')
    try:
        subprocess.check_output(['git', 'clone', testdef_repo, gitdir],
                                env=proxy_env, stderr=subprocess.STDOUT)
        if revision:
            os.chdir(gitdir)
            subprocess.check_output(['git', 'checkout', revision],
                                    stderr=subprocess.STDOUT)
        return gitdir
    except subprocess.CalledProcessError as e:
        logging.error("Test Shell Error: Unable to get test definition from git (%s)", (testdef_repo))
        for line in e.output.split('\n'):
            if line:
                logging.debug("  | %s", line)
        raise RuntimeError("Unable to get test definition from git (%s)" % (testdef_repo))
    except Exception:
        logging.error("Test Shell Error: Unable to get test definition from git (%s)", (testdef_repo))
        raise RuntimeError("Unable to get test definition from git (%s)" % (testdef_repo))
    finally:
        os.chdir(cwd)


def _get_testdef_bzr_repo(testdef_repo, tmpdir, revision, proxy_env):
    bzrdir = os.path.join(tmpdir, 'bzrtestrepo')
    try:
        # As per bzr revisionspec, '-1' is "The last revision in a
        # branch".
        if revision is None:
            revision = '-1'

        proxy_env.update({'BZR_HOME': '/dev/null', 'BZR_LOG': '/dev/null'})
        subprocess.check_output(['bzr', 'branch', '-r', revision, testdef_repo,
                                 bzrdir], env=proxy_env)
        return bzrdir
    except subprocess.CalledProcessError as e:
        logging.error("Test Error: Unable to get test definition from bzr (%s)", (testdef_repo))
        for line in e.output.split('\n'):
            if line:
                logging.debug("  | %s", line)
        raise RuntimeError("Unable to get test definition from bzr (%s)", (testdef_repo))

    except Exception as e:
        logging.error("Test Error: Unable to get test definition from bzr (%s)", (testdef_repo))
        raise RuntimeError("Unable to get test definition from bzr (%s)", (testdef_repo))


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
        logging.error("Test Shell Error: Error extracting the tar archive.\n" + str(ex))
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
        logging.error('Test Shell Error: Unable to get test definition from url\n' + str(e))
        return None
    finally:
        logging.info("Downloaded test definition file to %s." % urldir)

    return urldir


def _get_testdef_info(testdef):

    # before populating metadata, validate the testdef name.
    _validate_invalid_chars(testdef['metadata']['name'])

    metadata = {'os': '', 'devices': '', 'environment': ''}
    metadata['name'] = testdef['metadata']['name']
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


class TestDefinitionLoader(object):
    """
    A TestDefinitionLoader knows how to load test definitions from the data
    provided in the job file.
    """

    def __init__(self, context, tmpbase):
        self.testdefs = []
        self.context = context
        self.tmpbase = tmpbase

    def _append_testdef(self, testdef_obj):
        testdef_obj.load_signal_handler()
        self.testdefs.append(testdef_obj)

    def _get_dependent_test_cases(self, testdef):
        """If test-case-deps is defined in the YAML file, check if the
        dependent testcases are coming from a URL or REPO and call the
        appropriate function.
        """
        for testcase in testdef.get('test-case-deps', None):
            if set(testcase.keys()).isdisjoint(self.context.repo_keys):
                if 'url' in testcase:
                    self.load_from_url(testcase['url'])
            else:
                self.load_from_repo(testcase)

    def load_from_url(self, url):
        tmpdir = utils.mkdtemp(self.tmpbase)
        testdef_file = download_image(url, self.context, tmpdir)
        with open(testdef_file, 'r') as f:
            logging.debug('loading test definition ...')
            testdef = yaml.safe_load(f)

        if 'test-case-deps' in testdef:
            self._get_dependent_test_cases(testdef)

        idx = len(self.testdefs)

        testdef_metadata = {'url': url, 'location': 'URL'}
        testdef_metadata.update(_get_testdef_info(testdef))
        self._append_testdef(URLTestDefinition(self.context, idx, testdef,
                                               testdef_metadata))

    def load_from_repo(self, testdef_repo):
        tmpdir = utils.mkdtemp(self.tmpbase)
        repo = None
        info = None
        if 'git-repo' in testdef_repo:
            repo = _get_testdef_git_repo(testdef_repo['git-repo'], tmpdir,
                                         testdef_repo.get('revision'),
                                         _get_lava_proxy(self.context))
            name = os.path.splitext(os.path.basename(testdef_repo['git-repo']))[0]
            info = _git_info(testdef_repo['git-repo'], repo, name)

        if 'bzr-repo' in testdef_repo:
            repo = _get_testdef_bzr_repo(testdef_repo['bzr-repo'], tmpdir,
                                         testdef_repo.get('revision'),
                                         _get_lava_proxy(self.context))
            name = testdef_repo['bzr-repo'].replace('lp:', '').split('/')[-1]
            info = _bzr_info(testdef_repo['bzr-repo'], repo, name)

        if 'tar-repo' in testdef_repo:
            repo = _get_testdef_tar_repo(testdef_repo['tar-repo'], tmpdir)
            # Default info structure, since we need something, but we have
            # a tar file in this case.
            info = {
                "project_name": "Tar archived repository",
                "branch_vcs": "tar",
                "branch_revision": "0",
                "branch_url": repo
            }

        if 'url' in testdef_repo:
            repo = _get_testdef_url_repo(testdef_repo['url'], self.context, tmpdir)
            testdef_repo['testdef'] = os.path.basename(testdef_repo['url'])
            # Default info structure. Due to branch_vcs is enum type,
            # we use tar temporarily. For Dashboard Bundle Format 1.6,
            # "enum": ["bzr", "git", "svn", "tar"]
            info = {
                "project_name": "URL repository",
                "branch_vcs": "url",
                "branch_revision": "0",
                "branch_url": repo
            }

        if not repo or not info:
            logging.warning("Unable to identify specified repository. %s" %
                            testdef_repo)
        else:
            if 'parameters' in testdef_repo:
                # get the parameters for test.
                logging.debug('Get test parameters : %s' % testdef_repo['parameters'])
                info['test_params'] = str(testdef_repo['parameters'])
            else:
                info['test_params'] = ''

            test = testdef_repo.get('testdef', 'lavatest.yaml')
            try:
                with open(os.path.join(repo, test), 'r') as f:
                    logging.debug('loading test definition ...')
                    testdef = yaml.safe_load(f)
            except IOError as e:
                msg = "Test Shell Error: Unable to load test definition '%s/%s': %s" % (os.path.basename(repo), test, e)
                logging.error(msg)
                raise RuntimeError(msg)

            if 'test-case-deps' in testdef:
                self._get_dependent_test_cases(testdef)

            # for test parameters
            if 'params' in testdef:
                logging.debug('Get default parameters : %s' % testdef['params'])
                info['default_params'] = str(testdef['params'])
            else:
                info['default_params'] = ''

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
        self.uuid = str(uuid4())
        self.test_id = self.testdef_metadata['name']
        self.dirname = '%s_%s' % (idx, self.uuid)
        self._sw_sources = []
        self.handler = None
        self.__pattern__ = None
        self.__fixupdict__ = None
        self.skip_install = None
        self.all_params = {}

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
                logging.error("Test Shell Error: No handler named %s found", handler_name)
                return
            elif len(handler_eps) > 1:
                logging.warning(
                    "Multiple handlers named %s found.  Picking one arbitrarily.",
                    handler_name)
            handler_ep = handler_eps[0]
            logging.info("Loading handler from %s" % handler_ep.dist)
            handler_cls = handler_ep.load()
            self.handler = handler_cls(self, **hook_data.get('params', {}))
        except KeyboardInterrupt:
            raise KeyboardInterrupt
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
                env_dict = _get_lava_proxy(self.context)
                env_dict.update({'BZR_HOME': '/dev/null', 'BZR_LOG': '/dev/null'})

                subprocess.check_output(['bzr', 'branch', repo],
                                        env=env_dict,
                                        stderr=subprocess.STDOUT)
                name = repo.replace('lp:', '').split('/')[-1]
                self._sw_sources.append(_bzr_info(repo, name, name))

            for repo in self.testdef['install'].get('git-repos', []):
                if isinstance(repo, str):
                    logging.info("git clone %s" % repo)
                    subprocess.check_output(['git', 'clone', repo],
                                            env=_get_lava_proxy(self.context),
                                            stderr=subprocess.STDOUT)
                    name = gitdir = os.path.splitext(os.path.basename(repo))[0]
                    self._sw_sources.append(_git_info(repo, gitdir, name))
                if isinstance(repo, dict):
                    cmd = ['git', 'clone']
                    # Check if this repository should be skipped.
                    skip_by_default = repo.get('skip_by_default', False)
                    if skip_by_default in self.all_params:
                        if ast.literal_eval(self.all_params[skip_by_default]):
                            continue

                    url = repo.get('url', None)
                    branch = repo.get('branch', None)
                    if branch in self.all_params:
                        branch = self.all_params[branch]
                    destination = repo.get('destination', None)
                    if destination in self.all_params:
                        destination = self.all_params[destination]

                    # Form the command list
                    cmd = ['git', 'clone']
                    if branch:
                        cmd.append('-b')
                        cmd.append(branch)
                    if url:
                        cmd.append(url)
                    if destination:
                        cmd.append(destination)

                    logging.info("git clone %s" % url)
                    subprocess.check_output(cmd,
                                            env=_get_lava_proxy(self.context),
                                            stderr=subprocess.STDOUT)
                    name = os.path.splitext(os.path.basename(url))[0]
                    gitdir = destination if destination else name
                    self._sw_sources.append(_git_info(url, gitdir, name))
        finally:
            os.chdir(cwd)

    def _fetch_all_parameters(self):
        # default parameters that was defined in yaml
        if 'params' in self.testdef:
            self.all_params.update(self.testdef['params'])

        # parameters that was set in json
        if self._sw_sources and 'test_params' in self._sw_sources[0] and self._sw_sources[0]['test_params'] != '':
            _test_params_temp = eval(self._sw_sources[0]['test_params'])
            self.all_params.update(_test_params_temp)

    def _inject_testdef_parameters(self, fout):
        global repeat_cnt
        # inject default parameters that was defined in yaml first
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
        # inject other parameters
        target_type = self.context.client.target_device.deployment_data.get(
            'distro')
        fout.write('###other parameters###\n')
        fout.write('%s=\'%s\'\n' % ('LAVA_SERVER_IP',
                                    self.context.config.lava_server_ip))
        fout.write('%s=\'%s\'\n' % ('TARGET_TYPE', target_type))
        if repeat_cnt > 0:
            fout.write('%s=\'%s\'\n' % ('REPEAT_COUNT', repeat_cnt))
            fout.write('###save REPEAT_COUNT as named attribute###\n')
            fout.write('echo %s > $LAVA_RESULT_DIR/attributes/repeat_count\n' % repeat_cnt)
        fout.write('######\n')

    def _create_target_install(self, hostdir, targetdir):
        with open('%s/install.sh' % hostdir, 'w', encoding='utf-8') as f:
            self._inject_testdef_parameters(f)
            f.write('set -ex\n')
            f.write('cd %s\n' % targetdir)

            if self.skip_install != 'keys':
                distro = self.context.client.target_device.deployment_data[
                    'distro']
                sources = self.testdef['install'].get('keys', [])
                for src in sources:
                    f.write('lava-add-keys %s' % src)
                    f.write('\n')

            if self.skip_install != 'sources':
                distro = self.context.client.target_device.deployment_data[
                    'distro']
                sources = self.testdef['install'].get('sources', [])
                for src in sources:
                    f.write('lava-add-sources %s' % src)
                    f.write('\n')

            if self.skip_install != 'deps':
                distro = self.context.client.target_device.deployment_data['distro']

                # generic dependencies - must be named the same across all distros
                # supported by the testdef
                deps = self.testdef['install'].get('deps', [])

                # distro-specific dependencies
                deps = deps + self.testdef['install'].get('deps-' + distro, [])

                if deps:
                    f.write('lava-install-packages ')
                    for dep in deps:
                        f.write('%s ' % dep)
                    f.write('\n')

            if self.skip_install != 'steps':
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
        self._fetch_all_parameters()
        with open('%s/testdef.yaml' % hostdir, 'w') as f:
            f.write(yaml.dump(self.testdef, encoding='utf-8', allow_unicode=True))

        with open('%s/uuid' % hostdir, 'w', encoding='utf-8') as f:
            f.write(self.uuid)

        with open('%s/testdef_metadata' % hostdir, 'w', encoding='utf-8') as f:
            f.write(yaml.safe_dump(self.testdef_metadata))

        if self.skip_install != "all":
            if 'install' in self.testdef:
                if self.skip_install != 'repos':
                    self._create_repos(hostdir)
                self._create_target_install(hostdir, targetdir)

        with open('%s/run.sh' % hostdir, 'w', encoding='utf-8') as f:
            self._inject_testdef_parameters(f)
            f.write('set -e\n')
            f.write('export TESTRUN_ID=%s\n' % self.test_id)
            f.write('cd %s\n' % targetdir)
            f.write('UUID=`cat uuid`\n')
            f.write('echo "<LAVA_SIGNAL_STARTRUN $TESTRUN_ID $UUID>"\n')
            f.write('#wait for an ack from the dispatcher\n')
            f.write('read\n')
            steps = self.testdef['run'].get('steps', [])
            if steps:
                for cmd in steps:
                    if '--cmd' in cmd or '--shell' in cmd:
                        cmd = re.sub(r'\$(\d+)\b', r'\\$\1', cmd)
                    f.write('%s\n' % cmd)
            f.write('echo "<LAVA_SIGNAL_ENDRUN $TESTRUN_ID $UUID>"\n')
            f.write('#wait for an ack from the dispatcher\n')
            f.write('read\n')

    default_pattern = "(?P<test_case_id>.*-*)\\s+:\\s+(?P<result>(PASS|pass|FAIL|fail|SKIP|skip|UNKNOWN|unknown))"
    default_fixupdict = {'PASS': 'pass', 'FAIL': 'fail', 'SKIP': 'skip',
                         'UNKNOWN': 'unknown'}

    @property
    def fixupdict(self):
        if self.__fixupdict__ is None:
            testdef = self.testdef
            if 'parse' in testdef and 'fixupdict' in testdef['parse']:
                self.__fixupdict__ = testdef['parse']['fixupdict']
            else:
                self.__fixupdict__ = self.default_fixupdict

        return self.__fixupdict__

    @property
    def pattern(self):
        if self.__pattern__ is None:
            if 'parse' in self.testdef and \
               'pattern' in self.testdef['parse']:
                input_pattern = self.testdef['parse']['pattern']
            else:
                logging.warning(
                    """Using a default pattern to parse the test result. """
                    """This may lead to empty test results in certain cases.""")
                input_pattern = self.default_pattern

            try:
                self.__pattern__ = re.compile(input_pattern, re.M)
            except re.error as e:
                logging.warning("Error parsing regular expression %r: %s" %
                                (input_pattern, e.message))
                self.__pattern__ = re.compile(self.default_pattern, re.M)

        return self.__pattern__


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
        testdef_metadata.update(_get_testdef_info(testdef))
        testdef_metadata.update({'version': info['branch_revision']})

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
                                         'tar-repo': {'type': 'string',
                                                      'optional': True},
                                         'url': {'type': 'string',
                                                 'optional': True},
                                         'revision': {'type': 'string',
                                                      'optional': True},
                                         'testdef': {'type': 'string',
                                                     'optional': True},
                                         'parameters': {'type': 'object',
                                                        'optional': True}
                                         },
                                        'additionalProperties': False},
                              'optional': True
                              },
            'timeout': {'type': 'integer', 'optional': True},
            'role': {'type': 'string', 'optional': True},
            'skip_install': {'type': 'string', 'optional': True},
            'lava_test_dir': {'type': 'string', 'optional': True},
            'lava_test_results_dir': {'type': 'string', 'optional': True},
            'repeat': {'type': 'integer', 'optional': True},
            'repeat_count': {'type': 'integer', 'optional': True},
        },
        'additionalProperties': False,
    }

    def __init__(self, context):
        super(cmd_lava_test_shell, self).__init__(context)
        self._current_test_run = None
        self._current_testdef = None
        self._testdefs_by_name = None
        self._test_runs = []
        self._backup_bundle = {
            'test_runs': self._test_runs,
            'format': 'Dashboard Bundle Format 1.7.1',
        }

    def run(self, testdef_urls=None, testdef_repos=None, timeout=-1, skip_install=None,
            lava_test_dir=None, lava_test_results_dir=None, repeat_count=0):
        target = self.client.target_device
        global repeat_cnt
        repeat_cnt = repeat_count

        delay = target.config.test_shell_serial_delay_ms

        self._amend_test_execution_paths(target, lava_test_dir, lava_test_results_dir)

        testdef_objs = self._configure_target(target, testdef_urls,
                                              testdef_repos, skip_install)

        self._testdefs_by_name = {}
        for testdef in testdef_objs:
            self._testdefs_by_name[testdef.test_id] = testdef

        signal_director = SignalDirector(self.client, testdef_objs,
                                         self.context)

        with self.client.runner() as runner:
            if self.context.config.lava_proxy:
                runner._connection.sendline(
                    "export http_proxy=%s" % self.context.config.lava_proxy, delay)
            if self.context.config.lava_no_proxy:
                runner._connection.sendline(
                    "export no_proxy=%s" % self.context.config.lava_no_proxy, delay)
            runner._connection.sendline(
                "%s/bin/lava-test-runner %s" % (
                    target.lava_test_dir,
                    target.lava_test_dir),
                delay)
            start = time.time()
            if timeout == -1:
                timeout = runner._connection.timeout
            initial_timeout = timeout
            signal_director.set_connection(runner._connection)
            while self._keep_running(runner, target, timeout, signal_director):
                elapsed = time.time() - start
                timeout = int(initial_timeout - elapsed)

        self._bundle_results(target, signal_director, testdef_objs)

    def _keep_running(self, runner, target, timeout, signal_director):
        if self._current_testdef:
            test_case_result = self._current_testdef.pattern
        else:
            # no-op (the existing timeout would match first)
            test_case_result = pexpect.TIMEOUT

        patterns = [
            '<LAVA_TEST_RUNNER>: exiting',
            pexpect.EOF,
            pexpect.TIMEOUT,
            '<LAVA_SIGNAL_(\S+) ([^>]+)>',
            '<LAVA_MULTI_NODE> <LAVA_(\S+) ([^>]+)>',
            '<LAVA_LMP> <LAVA_(\S+) ([^>]+)>',
            test_case_result,
        ]

        # these are names for the indexes in the array above
        EXIT = 0
        EOF = 1
        TIMEOUT = 2
        SIGNAL = 3
        MULTINODE = 4
        LMP = 5
        TEST_CASE_RESULT = 6

        event = runner._connection.expect(patterns, timeout=timeout)

        if event == EXIT:
            logging.info('lava_test_shell seems to have completed')

        elif event == EOF:
            logging.warning('lava_test_shell connection dropped')

        elif event == TIMEOUT:
            if target.is_booted():
                target.reset_boot()
            logging.warning('lava_test_shell has timed out')
            raise pexpect.TIMEOUT('Timeout')

        elif event == SIGNAL:
            name, params = runner._connection.match.groups()
            logging.debug("Received signal <%s>" % name)
            params = params.split()
            if name == 'STARTRUN':
                self._handle_testrun(params)
            if name == 'TESTCASE':
                self._handle_testcase(params)
            try:
                signal_director.signal(name, params)
            except KeyboardInterrupt:
                raise KeyboardInterrupt
            except:
                logging.exception("on_signal failed")
            runner._connection.sendline('echo LAVA_ACK')
            return True

        elif event == MULTINODE:
            name, params = runner._connection.match.groups()
            logging.debug("Received Multi_Node API <LAVA_%s>" % name)
            params = params.split()
            ret = False
            try:
                ret = signal_director.signal(name, params)
            except KeyboardInterrupt:
                raise KeyboardInterrupt
            except:
                logging.exception("on_signal(Multi_Node) failed")
            return ret

        elif event == LMP:
            name, params = runner._connection.match.groups()
            logging.debug("Received LMP <LAVA_%s>" % name)
            params = params.split()
            ret = False
            try:
                ret = signal_director.signal(name, params)
            except KeyboardInterrupt:
                raise KeyboardInterrupt
            except:
                logging.exception("on_signal(LMP) failed")
            return ret

        elif event == TEST_CASE_RESULT:
            match = runner._connection.match
            if match is pexpect.TIMEOUT:
                if target.is_booted():
                    target.reset_boot()
                logging.warning('lava_test_shell has timed out')
            else:
                self._handle_parsed_testcase(match.groupdict())
                return True

        return False

    def _copy_runner(self, mntdir, target):
        shell = target.deployment_data['lava_test_sh_cmd']

        # Generic scripts
        scripts_to_copy = glob(os.path.join(LAVA_TEST_DIR, 'lava-*'))

        # Distro-specific scripts override the generic ones
        distro = target.deployment_data['distro']
        distro_support_dir = '%s/distro/%s' % (LAVA_TEST_DIR, distro)
        for script in glob(os.path.join(distro_support_dir, 'lava-*')):
            scripts_to_copy.append(script)

        for fname in scripts_to_copy:
            with open(fname, 'r') as fin:
                foutname = os.path.basename(fname)
                with open('%s/bin/%s' % (mntdir, foutname), 'w',
                          encoding='utf-8') as fout:
                    fout.write("#!%s\n\n" % shell)
                    fout.write(fin.read())
                    os.fchmod(fout.fileno(), XMOD)

    def _inject_multi_node_api(self, mntdir, target):
        shell = target.deployment_data['lava_test_sh_cmd']

        # Generic scripts
        scripts_to_copy = glob(os.path.join(LAVA_MULTI_NODE_TEST_DIR, 'lava-*'))

        for fname in scripts_to_copy:
            with open(fname, 'r') as fin:
                foutname = os.path.basename(fname)
                with open('%s/bin/%s' % (mntdir, foutname), 'w',
                          encoding='utf-8') as fout:
                    fout.write("#!%s\n\n" % shell)
                    # Target-specific scripts (add ENV to the generic ones)
                    if foutname == LAVA_GROUP_FILE:
                        fout.write('LAVA_GROUP="\n')
                        if 'roles' in self.context.group_data:
                            for client_name in self.context.group_data['roles']:
                                fout.write(r"\t%s\t%s\n" % (client_name, self.context.group_data['roles'][client_name]))
                        else:
                            logging.debug("group data MISSING")
                        fout.write('"\n')
                    elif foutname == LAVA_ROLE_FILE:
                        fout.write("TARGET_ROLE='%s'\n" % self.context.test_data.metadata['role'])
                    elif foutname == LAVA_SELF_FILE:
                        fout.write("LAVA_HOSTNAME='%s'\n" % self.context.test_data.metadata['target.hostname'])
                    else:
                        fout.write("LAVA_TEST_BIN='%s/bin'\n" %
                                   target.lava_test_dir)
                        fout.write("LAVA_MULTI_NODE_CACHE='%s'\n" % LAVA_MULTI_NODE_CACHE_FILE)
                        logging_level = self.context.test_data.metadata.get(
                            'logging_level', None)
                        if logging_level and logging_level == 'DEBUG':
                            fout.write("LAVA_MULTI_NODE_DEBUG='yes'\n")
                    fout.write(fin.read())
                    os.fchmod(fout.fileno(), XMOD)

    def _inject_lmp_api(self, mntdir, target):
        """
        This code is essentially unmaintained and may be dropped from the dispatcher in future.
        """
        shell = target.deployment_data['lava_test_sh_cmd']

        # Generic scripts
        scripts_to_copy = glob(os.path.join(LAVA_LMP_TEST_DIR, 'lava-lmp*'))

        for fname in scripts_to_copy:
            with open(fname, 'r') as fin:
                foutname = os.path.basename(fname)
                with open('%s/bin/%s' % (mntdir, foutname), 'w',
                          encoding='utf-8') as fout:
                    fout.write("#!%s\n\n" % shell)
                    # Target-specific scripts (add ENV to the generic ones)
                    fout.write("LAVA_TEST_BIN='%s/bin'\n" %
                               target.lava_test_dir)
                    fout.write("LAVA_LMP_CACHE='%s'\n" % LAVA_LMP_CACHE_FILE)
                    if self.context.test_data.metadata['logging_level'] == 'DEBUG':
                        fout.write("LAVA_LMP_DEBUG='yes'\n")
                    fout.write(fin.read())
                    os.fchmod(fout.fileno(), XMOD)

    def _mk_runner_dirs(self, mntdir):
        utils.ensure_directory('%s/bin' % mntdir)
        utils.ensure_directory_empty('%s/tests' % mntdir)
        utils.ensure_directory_empty('%s/results' % mntdir)

    def _configure_target(self, target, testdef_urls, testdef_repos, skip_install):
        results_part = target.deployment_data['lava_test_results_part_attr']
        results_part = getattr(target.config, results_part)

        with target.file_system(results_part, target.lava_test_results_dir) as d:
            self._mk_runner_dirs(d)
            self._copy_runner(d, target)
            if 'target_group' in self.context.test_data.metadata:
                self._inject_multi_node_api(d, target)
            if 'lmp_module' in self.context.test_data.metadata:
                self._inject_lmp_api(d, target)

            testdef_loader = TestDefinitionLoader(self.context, target.scratch_dir)

            if testdef_urls:
                for url in testdef_urls:
                    testdef_loader.load_from_url(url)

            if testdef_repos:
                for repo in testdef_repos:
                    testdef_loader.load_from_repo(repo)

            tdirs = []
            for testdef in testdef_loader.testdefs:
                testdef.skip_install = skip_install
                # android mount the partition under /system, while ubuntu
                # mounts under /, so we have hdir for where it is on the
                # host and tdir for how the target will see the path
                hdir = '%s/tests/%s' % (d, testdef.dirname)
                tdir = '%s/tests/%s' % (target.lava_test_dir,
                                        testdef.dirname)
                testdef.copy_test(hdir, tdir)
                tdirs.append(tdir)

            with open('%s/lava-test-runner.conf' % d, 'w',
                      encoding='utf-8') as f:
                for testdir in tdirs:
                    f.write('%s\n' % testdir)

        return testdef_loader.testdefs

    def _bundle_results(self, target, signal_director, testdef_objs):
        """ Pulls the results from the target device and builds a bundle
        """
        results_part = target.deployment_data['lava_test_results_part_attr']
        results_part = getattr(target.config, results_part)
        rdir = self.context.host_result_dir
        parse_err_msg = None

        filesystem_access_failure = True

        try:
            with target.file_system(results_part, target.lava_test_results_dir) as d:
                filesystem_access_failure = False
                err_log = os.path.join(d, 'parse_err.log')
                results_dir = os.path.join(d, 'results')
                bundle = lava_test_shell.get_bundle(results_dir, testdef_objs, err_log)
                parse_err_msg = utils.read_content(err_log, ignore_missing=True)
                if os.path.isfile(err_log):
                    os.unlink(err_log)
                # lava/results must be empty, but we keep a copy named
                # lava/results-XXXXXXXXXX for post-mortem analysis
                timestamp = datetime.now().strftime("%s")
                os.rename(results_dir, results_dir + '-' + timestamp)
                utils.ensure_directory(results_dir)
        except Exception as e:
            if filesystem_access_failure:
                # a failure when accessing the filesystem means the device
                # probably crashed. We use the backup bundle then.
                bundle = self._backup_bundle
                logging.warning(
                    """Error extracting test results from device: %s""" % e)
                logging.warning(
                    """This may mean that the device under test crashed. """
                    """We will use test results parsed from the serial """
                    """output as a backup, but note that some test """
                    """artifacts (such as attachments and """
                    """hardware/software contexts) will not be available""")
            else:
                raise e

        signal_director.postprocess_bundle(bundle)

        (fd, name) = tempfile.mkstemp(
            prefix='lava-test-shell', suffix='.bundle', dir=rdir)
        with os.fdopen(fd, 'w') as f:
            DocumentIO.dump(f, bundle)

        printer = PrettyPrinter(self.context)
        printer.print_results(bundle)

        if parse_err_msg:
            raise GeneralError(parse_err_msg)

    def _handle_testrun(self, params):
        test_id = params[0].decode('utf-8')
        testdef = self._testdefs_by_name[test_id]

        now = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
        test_run = {
            'test_id': testdef.test_id,
            'analyzer_assigned_date': now,
            'analyzer_assigned_uuid': testdef.uuid,
            'time_check_performed': False,
            'testdef_metadata': testdef.testdef_metadata,
            'test_results': []
        }

        self._current_testdef = testdef
        self._test_runs.append(test_run)
        self._current_test_run = test_run

    def _handle_testcase(self, params):
        data = {}
        for param in params:
            parts = param.split('=')
            if len(parts) == 2:
                key, value = parts
                key = key.lower()
                data[key] = value
            else:
                logging.warning(
                    "Ignoring malformed parameter for signal: \"%s\". " % param)

        test_result = parse_testcase_result(data)
        self._current_test_run['test_results'].append(test_result)

    def _handle_parsed_testcase(self, data):
        test_result = parse_testcase_result(data,
                                            self._current_testdef.fixupdict)
        self._current_test_run['test_results'].append(test_result)

    def _amend_test_execution_paths(self, target, lava_test_dir, lava_test_results_dir):
        if lava_test_dir is not None:
            # Preserve the default configuration value
            if target.config.lava_test_dir_backup is None:
                target.config.lava_test_dir_backup = target.lava_test_dir
                logging.info("Preserving default test directory: %s" % target.config.lava_test_dir_backup)
            # Set the user specified value
            logging.info("Using user specified test directory: %s" % lava_test_dir)
            target.config.lava_test_dir = lava_test_dir
        else:
            if target.config.lava_test_dir_backup is not None:
                # Restore the default configuration value
                target.config.lava_test_dir = target.config.lava_test_dir_backup
                logging.info("Restoring default test directory: %s" % target.config.lava_test_dir_backup)
                target.config.lava_test_dir_backup = None

        if lava_test_results_dir is not None:
            # Preserve the default configuration value
            if target.config.lava_test_results_dir_backup is None:
                target.config.lava_test_results_dir_backup = target.lava_test_results_dir
                logging.info("Preserving default test results directory: %s" % target.config.lava_test_results_dir_backup)
            # Set the user specified value
            logging.info("Using user specified test results directory: %s" % lava_test_results_dir)
            target.config.lava_test_results_dir = lava_test_results_dir
        else:
            if target.config.lava_test_results_dir_backup is not None:
                # Reset the default configuration value
                target.config.lava_test_results_dir = target.config.lava_test_results_dir_backup
                logging.info("Restoring default test results directory: %s" % target.config.lava_test_results_dir_backup)
                target.config.lava_test_results_dir_backup = None
