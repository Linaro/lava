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

import json
import yaml
import logging
import os
import pexpect
import shutil
import stat
import subprocess
import tempfile

import lava_dispatcher.lava_test_shell as lava_test_shell
import lava_dispatcher.utils as utils

from lava_dispatcher.actions import BaseAction
from lava_dispatcher.device.target import Target
from lava_dispatcher.downloader import download_image

LAVA_TEST_DIR = '%s/../../lava_test_shell' % os.path.dirname(__file__)
LAVA_TEST_ANDROID = '%s/lava-test-runner-android' % LAVA_TEST_DIR
LAVA_TEST_UBUNTU = '%s/lava-test-runner-ubuntu' % LAVA_TEST_DIR
LAVA_TEST_UPSTART = '%s/lava-test-runner.conf' % LAVA_TEST_DIR
LAVA_TEST_INITD = '%s/lava-test-runner.init.d' % LAVA_TEST_DIR
LAVA_TEST_SHELL = '%s/lava-test-shell' % LAVA_TEST_DIR

Target.android_deployment_data['lava_test_runner'] = LAVA_TEST_ANDROID
Target.android_deployment_data['lava_test_shell'] = LAVA_TEST_SHELL
Target.android_deployment_data['lava_test_sh_cmd'] = '/system/bin/mksh'
Target.android_deployment_data['lava_test_dir'] = '/data/lava'
Target.android_deployment_data['lava_test_results_part_attr'] = 'data_part_android_org'

Target.ubuntu_deployment_data['lava_test_runner'] = LAVA_TEST_UBUNTU
Target.ubuntu_deployment_data['lava_test_shell'] = LAVA_TEST_SHELL
Target.ubuntu_deployment_data['lava_test_sh_cmd'] = '/bin/sh'
Target.ubuntu_deployment_data['lava_test_dir'] = '/lava'
Target.ubuntu_deployment_data['lava_test_results_part_attr'] = 'root_part'

Target.oe_deployment_data['lava_test_runner'] = LAVA_TEST_UBUNTU
Target.oe_deployment_data['lava_test_shell'] = LAVA_TEST_SHELL
Target.oe_deployment_data['lava_test_sh_cmd'] = '/bin/sh'
Target.oe_deployment_data['lava_test_dir'] = '/lava'
Target.oe_deployment_data['lava_test_results_part_attr'] = 'root_part'

# 755 file permissions
XMOD = stat.S_IRWXU | stat.S_IXGRP | stat.S_IRGRP | stat.S_IXOTH | stat.S_IROTH


def _configure_ubuntu_startup(etcdir):
    logging.info('adding ubuntu upstart job')
    shutil.copy(LAVA_TEST_UPSTART, '%s/init/' % etcdir)

Target.ubuntu_deployment_data['lava_test_configure_startup'] = \
        _configure_ubuntu_startup


def _configure_oe_startup(etcdir):
    logging.info('adding init.d script')
    initd_file = '%s/init.d/lava-test-runner' % etcdir
    shutil.copy(LAVA_TEST_INITD, initd_file)
    os.chmod(initd_file, XMOD)
    shutil.copy(initd_file, '%s/rc5.d/S50lava-test-runner' % etcdir)
    shutil.copy(initd_file, '%s/rc6.d/K50lava-test-runner' % etcdir)

Target.oe_deployment_data['lava_test_configure_startup'] = \
        _configure_oe_startup


def _configure_android_startup(etcdir):
    logging.info('hacking android start up job')
    with open('%s/mkshrc' % etcdir, 'a') as f:
        f.write('\n/data/lava/bin/lava-test-runner\n')

Target.android_deployment_data['lava_test_configure_startup'] = \
        _configure_android_startup


class cmd_lava_test_shell(BaseAction):

    parameters_schema = {
        'type': 'object',
        'properties': {
            'testdef_urls': {'type': 'array', 'items': {'type': 'string'}},
            'timeout': {'type': 'integer', 'optional': True},
            },
        'additionalProperties': False,
        }

    def run(self, testdef_urls, timeout=-1):
        target = self.client.target_device
        self._assert_target(target)

        self._configure_target(target, testdef_urls)

        with target.runner() as runner:
            patterns = [
                '<LAVA_TEST_RUNNER>: exiting',
                pexpect.EOF,
                pexpect.TIMEOUT,
                ]
            idx = runner._connection.expect(patterns, timeout=timeout)
            if idx == 0:
                logging.info('lava_test_shell seems to have completed')
            elif idx == 1:
                logging.warn('lava_test_shell connection dropped')
            elif idx == 2:
                logging.warn('lava_test_shell has timed out')

        self._bundle_results(target)

    def _get_test_definition(self, testdef_url, tmpdir):
        testdef_file = download_image(testdef_url, self.context, tmpdir)
        with open(testdef_file, 'r') as f:
            logging.info('loading test definition')
            return yaml.load(f)

    def _copy_runner(self, mntdir, target):
        runner = target.deployment_data['lava_test_runner']
        shell = target.deployment_data['lava_test_shell']
        shutil.copy(runner, '%s/bin/lava-test-runner' % mntdir)
        os.chmod('%s/bin/lava-test-runner' % mntdir, XMOD)
        with open(shell, 'r') as fin:
            with open('%s/bin/lava-test-shell' % mntdir, 'w') as fout:
                shcmd = target.deployment_data['lava_test_sh_cmd']
                fout.write("#!%s\n\n" % shcmd)
                fout.write(fin.read())
                os.fchmod(fout.fileno(), XMOD)

    def _bzr_info(self, url, bzrdir):
        cwd = os.getcwd()
        try:
            os.chdir('%s' % bzrdir)
            revno = subprocess.check_output(['bzr', 'revno']).strip()
            return {
                'project_name': bzrdir,
                'branch_vcs': 'bzr',
                'branch_revision': revno,
                'branch_url': url,
                }
        finally:
            os.chdir(cwd)

    def _git_info(self, url, gitdir):
        cwd = os.getcwd()
        try:
            os.chdir('%s' % gitdir)
            commit_id = subprocess.check_output(
                ['git', 'log', '-1', '--pretty=%H']).strip()
            return {
                'project_name': url.rsplit('/')[-1],
                'branch_vcs': 'git',
                'branch_revision': commit_id,
                'branch_url': url,
                }
        finally:
            os.chdir(cwd)

    def _create_repos(self, testdef, testdir):
        cwd = os.getcwd()
        try:
            os.chdir(testdir)
            for repo in testdef['install'].get('bzr-repos', []):
                logging.info("bzr branch %s" % repo)
                # Pass non-existent BZR_HOME value, or otherwise bzr may
                # have non-reproducible behavior because it may rely on
                # bzr whoami value, presence of ssh keys, etc.
                subprocess.check_call(['bzr', 'branch', repo],
                    env={'BZR_HOME': '/dev/null', 'BZR_LOG': '/dev/null'})
                name = repo.replace('lp:', '').split('/')[-1]
                self._sw_sources.append(self._bzr_info(repo, name))
            for repo in testdef['install'].get('git-repos', []):
                logging.info("git clone %s" % repo)
                subprocess.check_call(['git', 'clone', repo])
                name = os.path.splitext(os.path.basename(repo))[0]
                self._sw_sources.append(self._git_info(repo, name))
        finally:
            os.chdir(cwd)

    def _create_target_install(self, testdef, hostdir, targetdir):
        with open('%s/install.sh' % hostdir, 'w') as f:
            f.write('set -ex\n')
            f.write('cd %s\n' % targetdir)

            # TODO how should we handle this for Android?
            if 'deps' in testdef['install'] and \
                    testdef['install']['deps'] is not None:
                f.write('sudo apt-get update\n')
                f.write('sudo apt-get install -y ')
                for dep in testdef['install']['deps']:
                    f.write('%s ' % dep)
                f.write('\n')

            if 'steps' in testdef['install'] and \
                    testdef['install']['steps'] is not None:
                for cmd in testdef['install']['steps']:
                    f.write('%s\n' % cmd)

    def _copy_test(self, hostdir, targetdir, testdef):
        self._sw_sources = []
        utils.ensure_directory(hostdir)
        with open('%s/testdef.yaml' % hostdir, 'w') as f:
            f.write(yaml.dump(testdef))

        if 'install' in testdef:
            self._create_repos(testdef, hostdir)
            self._create_target_install(testdef, hostdir, targetdir)

        with open('%s/run.sh' % hostdir, 'w') as f:
            f.write('set -e\n')
            f.write('cd %s\n' % targetdir)
            if 'steps' in testdef['run'] \
                    and testdef['run']['steps'] is not None:
                for cmd in testdef['run']['steps']:
                    f.write('%s\n' % cmd)

    def _mk_runner_dirs(self, mntdir):
        utils.ensure_directory('%s/bin' % mntdir)
        utils.ensure_directory_empty('%s/tests' % mntdir)

    def _configure_target(self, target, testdef_urls):
        ldir = target.deployment_data['lava_test_dir']

        results_part = target.deployment_data['lava_test_results_part_attr']
        results_part = getattr(target.config, results_part)

        with target.file_system(results_part, 'lava') as d:
            self._mk_runner_dirs(d)
            self._copy_runner(d, target)
            testdirs = []
            for i, url in enumerate(testdef_urls):
                testdef = self._get_test_definition(url, target.scratch_dir)
                # android mount the partition under /system, while ubuntu
                # mounts under /, so we have hdir for where it is on the host
                # and tdir for how the target will see the path
                hdir = '%s/tests/%d_%s' % (d, i, testdef.get('metadata').get('name'))
                tdir = '%s/tests/%d_%s' % (ldir, i, testdef.get('metadata').get('name'))
                self._copy_test(hdir, tdir, testdef)
                testdirs.append(tdir)

            with open('%s/lava-test-runner.conf' % d, 'w') as f:
                for testdir in testdirs:
                    f.write('%s\n' % testdir)

        with target.file_system(target.config.root_part, 'etc') as d:
            target.deployment_data['lava_test_configure_startup'](d)

    def _bundle_results(self, target):
        """ Pulls the results from the target device and builds a bundle
        """
        results_part = target.deployment_data['lava_test_results_part_attr']
        results_part = getattr(target.config, results_part)
        rdir = self.context.host_result_dir

        with target.file_system(results_part, 'lava/results') as d:
            bundle = lava_test_shell.get_bundle(d, self._sw_sources)
            utils.ensure_directory_empty(d)

            (fd, name) = tempfile.mkstemp(
                prefix='lava-test-shell', suffix='.bundle', dir=rdir)
            with os.fdopen(fd, 'w') as f:
                json.dump(bundle, f)

    def _assert_target(self, target):
        """ Ensure the target has the proper deployment data required by this
        action. This allows us to exit the action early rather than going 75%
        through the steps before discovering something required is missing
        """
        if not target.deployment_data:
            raise RuntimeError('Target includes no deployment_data')

        keys = ['lava_test_runner', 'lava_test_shell', 'lava_test_dir',
                'lava_test_configure_startup', 'lava_test_sh_cmd']
        for k in keys:
            if k not in target.deployment_data:
                raise RuntimeError('Target deployment_data missing %s' % k)
