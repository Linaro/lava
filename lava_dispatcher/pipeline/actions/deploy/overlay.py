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
import stat
import glob
from lava_dispatcher.pipeline.actions.deploy import DeployAction


class CustomisationAction(DeployAction):

    def __init__(self):
        super(CustomisationAction, self).__init__()
        self.name = "customise"
        self.description = "customise image during deployment"
        self.summary = "customise image"

    def run(self, connection, args=None):
        self._log("Customising image...")
        # FIXME: implement
        return connection


class OverlayAction(DeployAction):
    """
    Applies the lava test shell scripts.
    Deployments which are for a job containing a 'test' action
    will need to insert an instance of this class into the
    Deploy pipeline, between mount and umount.
    The overlay uses the 'mntdir' set by the MountAction
    in the job data.
    This class handles parts of the overlay which are independent
    of the content of the test definitions themselves. Other
    overlays are handled by TestDefinitionAction.
    """
    # FIXME: is this ImageOverlayAction or can it work the same way for all deployments?

    def __init__(self):
        super(OverlayAction, self).__init__()
        self.name = "lava-overlay"
        self.description = "add lava scripts during deployment for test shell use"
        self.summary = "overlay the lava support scripts"
        self.lava_test_dir = os.path.realpath(
            '%s/../../../lava_test_shell' % os.path.dirname(__file__))
        # 755 file permissions
        self.xmod = stat.S_IRWXU | stat.S_IXGRP | stat.S_IRGRP | stat.S_IXOTH | stat.S_IROTH

    def _copy_runner(self, mntdir):
        self._log("copy_runner %s" % mntdir)
        shell = self.parameters['deployment_data']['lava_test_sh_cmd']

        # Generic scripts
        scripts_to_copy = glob.glob(os.path.join(self.lava_test_dir, 'lava-*'))

        # Distro-specific scripts override the generic ones
        distro = self.parameters['deployment_data']['distro']
        distro_support_dir = '%s/distro/%s' % (self.lava_test_dir, distro)
        for script in glob.glob(os.path.join(distro_support_dir, 'lava-*')):
            scripts_to_copy.append(script)

        for fname in scripts_to_copy:
            with open(fname, 'r') as fin:
                foutname = os.path.basename(fname)
                with open('%s/bin/%s' % (mntdir, foutname), 'w') as fout:
                    fout.write("#!%s\n\n" % shell)
                    fout.write(fin.read())
                    os.fchmod(fout.fileno(), self.xmod)

    def run(self, connection, args=None):
        """
        A lava-test-shell has been requested, implement the overlay
        * check that the filesystem we need is actually mounted.
        * create test runner directories
        * copy runners into test runner directories
        """
        if not os.path.ismount(self.data['loop_mount']['mntdir']):
            raise RuntimeError("Overlay requested but %s is not a mountpoint" %
                               self.data['loop_mount']['mntdir'])
        lava_path = os.path.abspath("%s/%s" % (self.data['loop_mount']['mntdir'], self.data['lava_test_results_dir']))
        self._log("lava_path=%s" % lava_path)
        for runner_dir in ['bin', 'tests', 'results']:
            # avoid os.path.join as lava_test_results_dir startswith / so mntdir is *dropped* by join.
            path = os.path.abspath("%s/%s" % (lava_path, runner_dir))
            if not os.path.exists(path):
                os.makedirs(path)
        self._copy_runner(lava_path)
        return connection


class MultinodeOverlayAction(OverlayAction):  # FIXME: inject function needs to become a run step

    def __init__(self):
        super(MultinodeOverlayAction, self).__init__()
        self.name = "lava-multinode-overlay"
        self.description = "add lava scripts during deployment for multinode test shell use"
        self.summary = "overlay the lava multinode scripts"

        # Multinode-only
        self.lava_multi_node_test_dir = os.path.realpath(
            '%s/../../../lava_test_shell/multi_node' % os.path.dirname(__file__))
        self.lava_group_file = 'lava-group'
        self.lava_role_file = 'lava-role'
        self.lava_self_file = 'lava-self'
        self.lava_multi_node_cache_file = '/tmp/lava_multi_node_cache.txt'

    def _inject_multi_node_api(self, mntdir):
        shell = self.parameters['deployment_data']['lava_test_sh_cmd']

        # Generic scripts
        scripts_to_copy = glob.glob(os.path.join(self.lava_multi_node_test_dir, 'lava-*'))

        for fname in scripts_to_copy:
            with open(fname, 'r') as fin:
                foutname = os.path.basename(fname)
                with open('%s/bin/%s' % (mntdir, foutname), 'w') as fout:
                    fout.write("#!%s\n\n" % shell)
                    # Target-specific scripts (add ENV to the generic ones)
                    if foutname == self.lava_group_file:
                        fout.write('LAVA_GROUP="\n')
                        if 'roles' in self.job.parameters:
                            for client_name in self.job.parameters['roles']:
                                fout.write(r"\t%s\t%s\n" % (client_name, self.job.parameters['roles'][client_name]))
                        else:
                            self._log("group data MISSING")
                        fout.write('"\n')
                    elif foutname == self.lava_role_file:
                        fout.write("TARGET_ROLE='%s'\n" % self.job.parameters['role'])
                    elif foutname == self.lava_self_file:
                        fout.write("LAVA_HOSTNAME='%s'\n" % self.job.device.config.hostname)
                    else:
                        fout.write("LAVA_TEST_BIN='%s/bin'\n" % self.lava_test_dir)
                        fout.write("LAVA_MULTI_NODE_CACHE='%s'\n" % self.lava_multi_node_cache_file)
                        # always write out full debug logs
                        fout.write("LAVA_MULTI_NODE_DEBUG='yes'\n")
                    fout.write(fin.read())
                    os.fchmod(fout.fileno(), self.xmod)


class LMPOverlayAction(OverlayAction):  # FIXME: inject function needs to become a run step

    def __init__(self):
        super(LMPOverlayAction, self).__init__()
        self.name = "lava-lmp-overlay"
        self.description = "add lava LMP during deployment for multinode test shell use"
        self.summary = "overlay the LMP multinode scripts"

        # LMP-only
        self.lava_lmp_cache_file = '/tmp/lava_lmp_cache.txt'
        self.lava_lmp_test_dir = os.path.realpath(
            '%s/../../../lava_test_shell/lmp' % os.path.dirname(__file__))

    def _inject_lmp_api(self, mntdir):
        shell = self.parameters['deployment_data']['lava_test_sh_cmd']

        # Generic scripts
        scripts_to_copy = glob.glob(os.path.join(self.lava_lmp_test_dir, 'lava-lmp*'))

        for fname in scripts_to_copy:
            with open(fname, 'r') as fin:
                foutname = os.path.basename(fname)
                with open('%s/bin/%s' % (mntdir, foutname), 'w') as fout:
                    fout.write("#!%s\n\n" % shell)
                    # Target-specific scripts (add ENV to the generic ones)
                    fout.write("LAVA_TEST_BIN='%s/bin'\n" %
                               self.lava_test_dir)
                    fout.write("LAVA_LMP_CACHE='%s'\n" % self.lava_lmp_cache_file)
                    # always write out full debug logs
                    fout.write("LAVA_LMP_DEBUG='yes'\n")
                    fout.write(fin.read())
                    os.fchmod(fout.fileno(), self.xmod)
