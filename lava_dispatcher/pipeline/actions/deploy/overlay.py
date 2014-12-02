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
import tarfile
from lava_dispatcher.pipeline.actions.deploy import DeployAction
from lava_dispatcher.pipeline.action import Action, Pipeline
from lava_dispatcher.pipeline.actions.deploy.testdef import TestDefinitionAction
from lava_dispatcher.pipeline.utils.filesystem import mkdtemp


class CustomisationAction(DeployAction):

    def __init__(self):
        super(CustomisationAction, self).__init__()
        self.name = "customise"
        self.description = "customise image during deployment"
        self.summary = "customise image"

    def run(self, connection, args=None):
        self.logger.debug("Customising image...")
        # FIXME: implement
        return connection


class OverlayAction(DeployAction):
    """
    Creates a temporary location into which the lava test shell scripts are installed.
    The location remains available for the testdef actions to populate
    Multinode and LMP actions also populate the one location.
    CreateOverlay then creates a tarball of that location in the output directory
    of the job and removes the temporary location.
    ApplyOverlay extracts that tarball onto the image.

    Deployments which are for a job containing a 'test' action will have
    a TestDefinitionAction added to the job pipeline by this Action.

    The resulting overlay needs to be applied separately and custom classes
    exist for particular deployments, so that the overlay can be applied
    whilst the image is still mounted etc.

    This class handles parts of the overlay which are independent
    of the content of the test definitions themselves. Other
    overlays are handled by TestDefinitionAction.
    """

    def __init__(self):
        super(OverlayAction, self).__init__()
        self.name = "lava-overlay"
        self.description = "add lava scripts during deployment for test shell use"
        self.summary = "overlay the lava support scripts"
        self.lava_test_dir = os.path.realpath(
            '%s/../../../lava_test_shell' % os.path.dirname(__file__))
        self.scripts_to_copy = []
        # 755 file permissions
        self.xmod = stat.S_IRWXU | stat.S_IXGRP | stat.S_IRGRP | stat.S_IXOTH | stat.S_IROTH

    def validate(self):
        super(OverlayAction, self).validate()
        self.scripts_to_copy = glob.glob(os.path.join(self.lava_test_dir, 'lava-*'))
        # Distro-specific scripts override the generic ones
        distro = self.parameters['deployment_data']['distro']
        distro_support_dir = '%s/distro/%s' % (self.lava_test_dir, distro)
        for script in glob.glob(os.path.join(distro_support_dir, 'lava-*')):
            self.scripts_to_copy.append(script)
        if not self.scripts_to_copy:
            self.errors = "Unable to locate lava_test_shell support scripts."

    def populate(self, parameters):
        self.internal_pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        self.internal_pipeline.add_action(MultinodeOverlayAction())
        self.internal_pipeline.add_action(LMPOverlayAction())
        self.internal_pipeline.add_action(TestDefinitionAction())
        self.internal_pipeline.add_action(CompressOverlay())

    def run(self, connection, args=None):
        """
        Check if a lava-test-shell has been requested, implement the overlay
        * create test runner directories beneath the temporary location
        * copy runners into test runner directories
        """
        self.data[self.name].setdefault('location', mkdtemp())
        self.validate()
        lava_path = os.path.abspath("%s/%s" % (self.data[self.name]['location'], self.data['lava_test_results_dir']))
        self.logger.debug("lava_path:%s scripts:%s" % (lava_path, self.scripts_to_copy))
        for runner_dir in ['bin', 'tests', 'results']:
            # avoid os.path.join as lava_test_results_dir startswith / so location is *dropped* by join.
            path = os.path.abspath("%s/%s" % (lava_path, runner_dir))
            self.logger.debug(path)
            if not os.path.exists(path):
                os.makedirs(path)
        for fname in self.scripts_to_copy:
            with open(fname, 'r') as fin:
                foutname = os.path.basename(fname)
                with open('%s/bin/%s' % (lava_path, foutname), 'w') as fout:
                    fout.write("#!%s\n\n" % self.parameters['deployment_data']['lava_test_sh_cmd'])
                    fout.write(fin.read())
                    os.fchmod(fout.fileno(), self.xmod)
        connection = super(OverlayAction, self).run(connection, args)
        return connection


class MultinodeOverlayAction(OverlayAction):

    def __init__(self):
        super(MultinodeOverlayAction, self).__init__()
        self.name = "lava-multinode-overlay"
        self.description = "add lava scripts during deployment for multinode test shell use"
        self.summary = "overlay the lava multinode scripts"

        # Multinode-only
        self.lava_multi_node_test_dir = os.path.realpath(
            '%s/../../../lava_test_shell/multi_node' % os.path.dirname(__file__))
        self.lava_multi_node_cache_file = '/tmp/lava_multi_node_cache.txt'

    def populate(self, parameters):
        pass

    def validate(self):
        super(MultinodeOverlayAction, self).validate()
        # idempotency
        if 'actions' not in self.job.parameters:
            return
        if 'target_group' not in self.job.parameters:
            return

    def run(self, connection, args=None):
        if 'target_group' not in self.job.parameters:
            self.logger.debug("skipped %s - no target group" % self.name)
            return connection
        if 'location' not in self.data['lava-overlay']:
            raise RuntimeError("Missing lava overlay location")
        if not os.path.exists(self.data['lava-overlay']['location']):
            raise RuntimeError("Unable to find overlay location")
        location = self.data['lava-overlay']['location']
        shell = self.parameters['deployment_data']['lava_test_sh_cmd']

        # Generic scripts
        scripts_to_copy = glob.glob(os.path.join(self.lava_multi_node_test_dir, 'lava-*'))

        for fname in scripts_to_copy:
            with open(fname, 'r') as fin:
                foutname = os.path.basename(fname)
                with open('%s/bin/%s' % (location, foutname), 'w') as fout:
                    fout.write("#!%s\n\n" % shell)
                    # Target-specific scripts (add ENV to the generic ones)
                    if foutname == 'lava-group':
                        fout.write('LAVA_GROUP="\n')
                        if 'roles' in self.job.parameters:
                            for client_name in self.job.parameters['roles']:
                                fout.write(r"\t%s\t%s\n" % (client_name, self.job.parameters['roles'][client_name]))
                        else:
                            self.logger.debug("group data MISSING")
                        fout.write('"\n')
                    elif foutname == 'lava-role':
                        fout.write("TARGET_ROLE='%s'\n" % self.job.parameters['role'])
                    elif foutname == 'lava-self':
                        fout.write("LAVA_HOSTNAME='%s'\n" % self.job.device.config.hostname)
                    else:
                        fout.write("LAVA_TEST_BIN='%s/bin'\n" % self.lava_test_dir)
                        fout.write("LAVA_MULTI_NODE_CACHE='%s'\n" % self.lava_multi_node_cache_file)
                        # always write out full debug logs
                        fout.write("LAVA_MULTI_NODE_DEBUG='yes'\n")
                    fout.write(fin.read())
                    os.fchmod(fout.fileno(), self.xmod)
        return connection


class LMPOverlayAction(OverlayAction):

    def __init__(self):
        super(LMPOverlayAction, self).__init__()
        self.name = "lava-lmp-overlay"
        self.description = "add lava LMP during deployment for multinode test shell use"
        self.summary = "overlay the LMP multinode scripts"

        # LMP-only
        self.lava_lmp_cache_file = '/tmp/lava_lmp_cache.txt'
        self.lava_lmp_test_dir = os.path.realpath(
            '%s/../../../lava_test_shell/lmp' % os.path.dirname(__file__))

    def populate(self, parameters):
        pass

    def validate(self):
        super(LMPOverlayAction, self).validate()
        # idempotency
        if self.job.parameters.get('overlay'):
            return
        if 'lmp_module' not in self.job.parameters:
            return
        # if there is nothing else to do, omit function.

    def run(self, connection, args=None):
        self.logger.debug("job parameters %s" % self.job.parameters)
        if 'lmp_module' not in self.job.parameters:
            self.logger.debug("Skipped %s - no lmp_module setting" % self.name)
            return connection
        if 'location' not in self.data['lava-overlay']:
            raise RuntimeError("Missing lava overlay location")
        if not os.path.exists(self.data['lava-overlay']['location']):
            raise RuntimeError("Unable to find overlay location")
        location = self.data['lava-overlay']['location']

        shell = self.parameters['deployment_data']['lava_test_sh_cmd']

        # Generic scripts
        scripts_to_copy = glob.glob(os.path.join(self.lava_lmp_test_dir, 'lava-lmp*'))

        for fname in scripts_to_copy:
            with open(fname, 'r') as fin:
                foutname = os.path.basename(fname)
                with open('%s/bin/%s' % (location, foutname), 'w') as fout:
                    fout.write("#!%s\n\n" % shell)
                    # Target-specific scripts (add ENV to the generic ones)
                    fout.write("LAVA_TEST_BIN='%s/bin'\n" %
                               self.lava_test_dir)
                    fout.write("LAVA_LMP_CACHE='%s'\n" % self.lava_lmp_cache_file)
                    # always write out full debug logs
                    fout.write("LAVA_LMP_DEBUG='yes'\n")
                    fout.write(fin.read())
                    os.fchmod(fout.fileno(), self.xmod)
        return connection


class CompressOverlay(Action):
    """
    Makes a tarball of the finished overlay and declares filename of the tarball
    """
    def __init__(self):
        super(CompressOverlay, self).__init__()
        self.name = "compress-overlay"
        self.summary = "Compress the lava overlay files"
        self.description = "Create a lava overlay tarball and store alongside the job"

    def run(self, connection, args=None):
        if 'location' not in self.data['lava-overlay']:
            raise RuntimeError("Missing lava overlay location")
        if not os.path.exists(self.data['lava-overlay']['location']):
            raise RuntimeError("Unable to find overlay location")
        if not self.valid:
            self.logger.debug(self.errors)
            return connection
        location = self.data['lava-overlay']['location']
        output = os.path.join(self.job.parameters['output_dir'], 'overlay.tar.gz')
        cur_dir = os.getcwd()
        try:
            with tarfile.open(output, "w:gz") as tar:
                os.chdir(location)
                tar.add(".%s" % self.data['lava_test_results_dir'])
        except tarfile.TarError as exc:
            self.errors = "Unable to create lava overlay tarball: %s" % exc
            raise RuntimeError("Unable to create lava overlay tarball: %s" % exc)
        os.chdir(cur_dir)
        self.data[self.name]['output'] = output
        return connection
