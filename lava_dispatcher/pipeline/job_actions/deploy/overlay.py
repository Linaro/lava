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

import re
import glob
from tempfile import mkdtemp
from lava_dispatcher.pipeline import *

# FIXME: overlay is getting large, move other classes into mount.py?


class OffsetAction(Action):
    """
    Uses the target.deployment_data['lava_test_results_part_attr']
    which, for example, maps to the root_part in the Device config for a kvm.
    The Device object is passed into the parser which uses the action
    parameters to determine the deployment_data parameter of the Device object.
    The calculated offset is dynamic data, stored in the context.
    """

    def __init__(self):
        super(OffsetAction, self).__init__()
        self.name = "offset_action"
        self.description = "calculate offset of the image"
        self.summary = "offset calculation"

    def validate(self):
        if 'download_action' not in self.job.context.pipeline_data:
            raise RuntimeError("missing download_action in parameters")
        if 'file' not in self.job.context.pipeline_data['download_action']:
            self.errors = "no file specified to calculate offset"

    def run(self, connection, args=None):
        if 'download_action' not in self.job.context.pipeline_data:
            raise RuntimeError("Missing download action")
        image = self.job.context.pipeline_data['download_action']['file']
        if not os.path.exists(image):
            raise RuntimeError("Not able to mount %s: file does not exist" % image)
        if 'offset' in self.job.context.pipeline_data['download_action']:
            # idempotency
            return connection
        image = self.job.context.pipeline_data['download_action']['file']
        partno = getattr(
            self.job.device.config,
            self.parameters['deployment_data']['lava_test_results_part_attr']
        )
        part_data = self._run_command([
            'parted',
            image,
            '-m',
            '-s',
            'unit',
            'b',
            'print'
        ])
        pattern = re.compile('%d:([0-9]+)B:' % partno)
        for line in part_data.splitlines():
            found = re.match(pattern, line)
            if found:
                self.job.context.pipeline_data['download_action']['offset'] = found.group(1)
        if 'offset' not in self.job.context.pipeline_data['download_action']:
            # more reliable than checking if offset exists as offset can be zero
            raise JobError(  # FIXME: JobError needs a unit test
                "Unable to determine offset for %s" % image
            )
        return connection


class LoopCheckAction(Action):

    def __init__(self):
        super(LoopCheckAction, self).__init__()
        self.name = "loop_check"
        self.description = "ensure a loop back mount operation is possible"
        self.summary = "check available loop back support"

    def validate(self):
        if len(glob.glob('/sys/block/loop*')) <= 0:
            raise InfrastructureError("Could not mount the image without loopback devices. "
                                      "Is the 'loop' kernel module activated?")

    def run(self, connection, args=None):
        available_loops = len(glob.glob('/sys/block/loop*'))
        self.job.context.pipeline_data['download_action']['available_loops'] = available_loops
        return connection


class LoopMountAction(RetryAction):
    """
    Needs to expose the final mountpoint in the context.pipeline_data
    to allow the customise action to push any test definitions in
    without doing to consecutive (identical) mounts in the Deploy and
    again in the test shell.
    """

    def __init__(self):
        super(LoopMountAction, self).__init__()
        self.name = "loop_mount"
        self.description = "Mount using a loopback device and offset"
        self.summary = "loopback mount"
        self.retries = 10
        self.sleep = 10

    def validate(self):
        if 'download_action' not in self.job.context.pipeline_data:
            raise RuntimeError("missing download_action in parameters")
        if 'file' not in self.job.context.pipeline_data['download_action']:
            self.errors = "no file specified to mount"

    def run(self, connection, args=None):
        args = ['sudo', '/sbin/losetup', '-a']  # in preparation for dispatcher not running as root
        pro = self._run_command(args)
        mounted_loops = len(pro.strip().split("\n"))
        offset = self.job.context.pipeline_data['download_action']['offset']
        image = self.job.context.pipeline_data['download_action']['file']
        self.job.context.pipeline_data[self.name] = {}
        self.job.context.pipeline_data[self.name]['mntdir'] = mkdtemp()
        mount_cmd = [
            'sudo',
            'mount',
            '-o',
            'loop,offset=%s' % offset,
            image,
            self.job.context.pipeline_data[self.name]['mntdir']
        ]
        available_loops = self.job.context.pipeline_data['download_action']['available_loops']
        if mounted_loops >= available_loops:
            raise InfrastructureError("Insufficient loopback devices?")
        self._log("available loops: %s" % available_loops)
        self._log("mounted_loops: %s" % mounted_loops)
        rc = self._run_command(mount_cmd)
        if not rc or rc is '':
            return connection
        else:
            raise JobError("Unable to mount: %s" % rc)  # FIXME: JobError needs a unit test


class MountAction(Action):
    """
    Depending on the type of deployment, this needs to perform
    an OffsetAction, LoopCheckAction, LoopMountAction
    """

    def __init__(self):
        super(MountAction, self).__init__()
        self.name = "mount_action"
        self.description = "mount with offset"
        self.summary = "mount loop"

    def validate(self):
        if not self.job:
            raise RuntimeError("No job object supplied to action")
        self.internal_pipeline.validate_actions()

    def populate(self):
        """
        Needs to take account of the deployment type / image type etc.
        to determine which actions need to be added to the internal pipeline
        as part of the deployment selection step.
        """
        if not self.job:
            raise RuntimeError("No job object supplied to action")
        # FIXME: not all mount operations will need these actions
        self.internal_pipeline = Pipeline(parent=self, job=self.job)
        self.internal_pipeline.add_action(OffsetAction())
        self.internal_pipeline.add_action(LoopCheckAction())
        self.internal_pipeline.add_action(LoopMountAction())

    def run(self, connection, args=None):
        if self.internal_pipeline:
            connection = self.internal_pipeline.run_actions(connection, args)
        else:
            raise RuntimeError("Deployment failed to generate a mount pipeline.")
        return connection


class CustomisationAction(Action):

    def __init__(self):
        super(CustomisationAction, self).__init__()
        self.name = "customise"
        self.description = "customise image during deployment"
        self.summary = "customise image"

    def run(self, connection, args=None):
        self._log("Customising image...")
        return connection


class OverlayAction(Action):
    """
    Applies the lava test shell scripts
    """

    def __init__(self):
        super(OverlayAction, self).__init__()
        self.name = "lava-overlay"
        self.description = "add lava scripts during deployment for test shell use"
        self.summary = "overlay the lava support scripts"
        self.lava_test_dir = os.path.realpath(
            '%s/../../../lava_test_shell' % os.path.dirname(__file__))
        self.lava_multi_node_test_dir = os.path.realpath(
            '%s/../../../lava_test_shell/multi_node' % os.path.dirname(__file__))
        self.lava_lmp_test_dir = os.path.realpath(
            '%s/../../../lava_test_shell/lmp' % os.path.dirname(__file__))
        self.lava_multi_node_cache_file = '/tmp/lava_multi_node_cache.txt'
        self.lava_lmp_cache_file = '/tmp/lava_lmp_cache.txt'
        self.default_pattern = "(?P<test_case_id>.*-*)\\s+:\\s+(?P<result>(PASS|pass|FAIL|fail|SKIP|skip|UNKNOWN|unknown))"
        self.default_fixupdict = {'PASS': 'pass', 'FAIL': 'fail', 'SKIP': 'skip',
                                  'UNKNOWN': 'unknown'}

    def _inject_testdef_parameters(self, fout):
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

    def _create_target_install(self, hostdir, targetdir):
        with open('%s/install.sh' % hostdir, 'w') as f:
            self._inject_testdef_parameters(f)
            f.write('set -ex\n')
            f.write('cd %s\n' % targetdir)

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
        with open('%s/testdef.yaml' % hostdir, 'w') as f:
            f.write(yaml.dump(self.testdef))

        with open('%s/uuid' % hostdir, 'w') as f:
            f.write(self.uuid)

        with open('%s/testdef_metadata' % hostdir, 'w') as f:
            f.write(yaml.safe_dump(self.testdef_metadata))

        if self.skip_install != "all":
            if 'install' in self.testdef:
                if self.skip_install != 'repos':
                    self._create_repos(hostdir)
                self._create_target_install(hostdir, targetdir)

        with open('%s/run.sh' % hostdir, 'w') as f:
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
                    f.write('%s\n' % cmd)
            f.write('echo "<LAVA_SIGNAL_ENDRUN $TESTRUN_ID $UUID>"\n')
            f.write('#wait for an ack from the dispatcher\n')
            f.write('read\n')

    def _copy_runner(self, mntdir, target):
        shell = target.deployment_data['lava_test_sh_cmd']

        # Generic scripts
        scripts_to_copy = glob.glob(os.path.join(self.lava_test_dir, 'lava-*'))

        # Distro-specific scripts override the generic ones
        distro = target.deployment_data['distro']
        distro_support_dir = '%s/distro/%s' % (self.lava_test_dir, distro)
        for script in glob.glob(os.path.join(distro_support_dir, 'lava-*')):
            scripts_to_copy.append(script)

        for fname in scripts_to_copy:
            with open(fname, 'r') as fin:
                foutname = os.path.basename(fname)
                with open('%s/bin/%s' % (mntdir, foutname), 'w') as fout:
                    fout.write("#!%s\n\n" % shell)
                    fout.write(fin.read())
                    os.fchmod(fout.fileno(), XMOD)

    def _inject_multi_node_api(self, mntdir, target):
        shell = target.deployment_data['lava_test_sh_cmd']

        # Generic scripts
        scripts_to_copy = glob.glob(os.path.join(LAVA_MULTI_NODE_TEST_DIR, 'lava-*'))

        for fname in scripts_to_copy:
            with open(fname, 'r') as fin:
                foutname = os.path.basename(fname)
                with open('%s/bin/%s' % (mntdir, foutname), 'w') as fout:
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
        shell = target.deployment_data['lava_test_sh_cmd']

        # Generic scripts
        scripts_to_copy = glob.glob(os.path.join(LAVA_LMP_TEST_DIR, 'lava-lmp*'))

        for fname in scripts_to_copy:
            with open(fname, 'r') as fin:
                foutname = os.path.basename(fname)
                with open('%s/bin/%s' % (mntdir, foutname), 'w') as fout:
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

    def run(self, connection, args=None):
        # make runner directories
        # copy runner files
        #    if 'target_group' in self.context.test_data.metadata:
        #        self._inject_multi_node_api(d, target)
        #    if 'lmp_module' in self.context.test_data.metadata:
        #        self._inject_lmp_api(d, target)
        # load test definitions
        return connection


class UnmountAction(RetryAction):

    def __init__(self):
        super(UnmountAction, self).__init__()
        self.name = "umount"
        self.description = "unmount the test image at end of deployment"
        self.summary = "unmount image"

    def run(self, connection, args=None):
        self._log("umounting %s" % self.job.context.pipeline_data['loop_mount']['mntdir'])
        self._run_command(['sudo', 'umount', self.job.context.pipeline_data['loop_mount']['mntdir']])
        # FIXME: is the rm -rf a separate action or a cleanup of this action?
        self._run_command(['rm', '-rf', self.job.context.pipeline_data['loop_mount']['mntdir']])
        return connection
