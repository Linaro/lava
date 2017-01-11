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
import shutil
import tarfile
from lava_dispatcher.pipeline.actions.deploy import DeployAction
from lava_dispatcher.pipeline.action import Action, Pipeline
from lava_dispatcher.pipeline.actions.deploy.testdef import (
    TestDefinitionAction,
    get_test_action_namespaces,
)
from lava_dispatcher.pipeline.utils.filesystem import check_ssh_identity_file
from lava_dispatcher.pipeline.utils.shell import infrastructure_error
from lava_dispatcher.pipeline.utils.network import rpcinfo_nfs
from lava_dispatcher.pipeline.protocols.multinode import MultinodeProtocol
from lava_dispatcher.pipeline.protocols.vland import VlandProtocol


class CustomisationAction(DeployAction):

    def __init__(self):
        super(CustomisationAction, self).__init__()
        self.name = "customise"
        self.description = "customise image during deployment"
        self.summary = "customise image"

    def run(self, connection, max_end_time, args=None):
        connection = super(CustomisationAction, self).run(connection, max_end_time, args)
        self.logger.debug("Customising image...")
        # FIXME: implement
        return connection


# pylint: disable=too-many-instance-attributes
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
        self.lava_v2_test_dir = os.path.realpath(
            '%s/../../../pipeline/lava_test_shell' % os.path.dirname(__file__))
        self.v2_scripts_to_copy = []
        # 755 file permissions
        self.xmod = stat.S_IRWXU | stat.S_IXGRP | stat.S_IRGRP | stat.S_IXOTH | stat.S_IROTH
        self.target_mac = ''
        self.target_ip = ''

    def validate(self):
        super(OverlayAction, self).validate()
        self.scripts_to_copy = glob.glob(os.path.join(self.lava_test_dir, 'lava-*'))
        # Distro-specific scripts override the generic ones
        if not self.test_needs_overlay(self.parameters):
            return
        distro = self.parameters['deployment_data']['distro']
        distro_support_dir = '%s/distro/%s' % (self.lava_test_dir, distro)
        lava_test_results_dir = self.parameters['deployment_data']['lava_test_results_dir']
        lava_test_results_dir = lava_test_results_dir % self.job.job_id
        self.set_namespace_data(action='test', label='shared', key='lava_test_results_dir',
                                value=lava_test_results_dir)
        lava_test_sh_cmd = self.parameters['deployment_data']['lava_test_sh_cmd']
        self.set_namespace_data(action='test', label='shared', key='lava_test_sh_cmd',
                                value=lava_test_sh_cmd)
        for script in glob.glob(os.path.join(distro_support_dir, 'lava-*')):
            self.scripts_to_copy.append(script)
        for script in glob.glob(os.path.join(self.lava_v2_test_dir, 'lava-*')):
            self.v2_scripts_to_copy.append(script)
        if not self.scripts_to_copy:
            self.errors = "Unable to locate lava_test_shell support scripts."
        if not self.v2_scripts_to_copy:
            self.errors = "Unable to update lava_test_shell support scripts."
        if self.job.parameters.get('output_dir', None) is None:
            self.errors = "Unable to use output directory."
        if 'parameters' in self.job.device:
            if 'interfaces' in self.job.device['parameters']:
                if 'target' in self.job.device['parameters']['interfaces']:
                    self.target_mac = self.job.device['parameters']['interfaces']['target'].get('mac', '')
                    self.target_ip = self.job.device['parameters']['interfaces']['target'].get('ip', '')

    def populate(self, parameters):
        self.internal_pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        if self.test_needs_overlay(parameters):
            if any('ssh' in data for data in self.job.device['actions']['deploy']['methods']):
                # only devices supporting ssh deployments add this action.
                self.internal_pipeline.add_action(SshAuthorize())
            self.internal_pipeline.add_action(VlandOverlayAction())
            self.internal_pipeline.add_action(MultinodeOverlayAction())
            self.internal_pipeline.add_action(TestDefinitionAction())
            self.internal_pipeline.add_action(CompressOverlay())
            self.internal_pipeline.add_action(PersistentNFSOverlay())  # idempotent

    def run(self, connection, max_end_time, args=None):
        """
        Check if a lava-test-shell has been requested, implement the overlay
        * create test runner directories beneath the temporary location
        * copy runners into test runner directories
        """
        tmp_dir = self.mkdtemp()
        namespace = self.parameters.get('namespace', None)
        if namespace:
            if namespace not in get_test_action_namespaces(self.job.parameters):
                self.logger.debug("skipped %s", self.name)
                return connection
        self.set_namespace_data(action='test', label='shared', key='location', value=tmp_dir)
        lava_test_results_dir = self.get_namespace_data(action='test', label='results', key='lava_test_results_dir')
        shell = self.get_namespace_data(action='test', label='shared', key='lava_test_sh_cmd')
        self.logger.debug("[%s] Preparing overlay tarball in %s", namespace, tmp_dir)
        lava_path = os.path.abspath("%s/%s" % (tmp_dir, lava_test_results_dir))
        for runner_dir in ['bin', 'tests', 'results']:
            # avoid os.path.join as lava_test_results_dir startswith / so location is *dropped* by join.
            path = os.path.abspath("%s/%s" % (lava_path, runner_dir))
            if not os.path.exists(path):
                os.makedirs(path, 0o755)
                self.logger.debug("makedir: %s", path)
        for fname in self.scripts_to_copy:
            with open(fname, 'r') as fin:
                output_file = '%s/bin/%s' % (lava_path, os.path.basename(fname))
                self.logger.debug("Creating %s", output_file)
                with open(output_file, 'w') as fout:
                    fout.write("#!%s\n\n" % shell)
                    fout.write(fin.read())
                    os.fchmod(fout.fileno(), self.xmod)
        for fname in self.v2_scripts_to_copy:
            with open(fname, 'r') as fin:
                foutname = os.path.basename(fname)
                output_file = '%s/bin/%s' % (lava_path, foutname)
                self.logger.debug("Updating %s", output_file)
                with open(output_file, 'w') as fout:
                    fout.write("#!%s\n\n" % shell)
                    if foutname == 'lava-target-mac':
                        fout.write("TARGET_DEVICE_MAC='%s'\n" % self.target_mac)
                    if foutname == 'lava-target-ip':
                        fout.write("TARGET_DEVICE_IP='%s'\n" % self.target_ip)
                    fout.write(fin.read())
                    os.fchmod(fout.fileno(), self.xmod)

        # Generate the file containing the secrets
        if 'secrets' in self.job.parameters:
            self.logger.debug("Creating %s/secrets", lava_path)
            with open(os.path.join(lava_path, 'secrets'), 'w') as fout:
                for key, value in self.job.parameters['secrets'].items():
                    if key == 'yaml_line':
                        continue
                    fout.write("%s=%s\n" % (key, value))

        connection = super(OverlayAction, self).run(connection, max_end_time, args)
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
        self.lava_v2_multi_node_test_dir = os.path.realpath(
            '%s/../../../pipeline/lava_test_shell/multi_node/' % os.path.dirname(__file__))
        self.role = None
        self.protocol = MultinodeProtocol.name

    def populate(self, parameters):
        # override the populate function of overlay action which provides the
        # lava test directory settings etc.
        pass

    def validate(self):
        super(MultinodeOverlayAction, self).validate()
        # idempotency
        if 'actions' not in self.job.parameters:
            return
        if 'protocols' in self.job.parameters and \
                self.protocol in [protocol.name for protocol in self.job.protocols]:
            if 'target_group' not in self.job.parameters['protocols'][self.protocol]:
                return
            if 'role' not in self.job.parameters['protocols'][self.protocol]:
                self.errors = "multinode job without a specified role"
            else:
                self.role = self.job.parameters['protocols'][self.protocol]['role']
        # FIXME: rationalise all this when the V1 code is removed.
        for script in glob.glob(os.path.join(self.lava_v2_multi_node_test_dir, 'lava-*')):
            self.v2_scripts_to_copy.append(script)

    def run(self, connection, max_end_time, args=None):  # pylint: disable=too-many-locals,too-many-branches,too-many-statements
        if self.role is None:
            self.logger.debug("skipped %s", self.name)
            return connection
        lava_test_results_dir = self.get_namespace_data(action='test', label='results', key='lava_test_results_dir')
        shell = self.get_namespace_data(action='test', label='shared', key='lava_test_sh_cmd')
        location = self.get_namespace_data(action='test', label='shared', key='location')
        if not location:
            raise RuntimeError("Missing lava overlay location")
        if not os.path.exists(location):
            raise RuntimeError("Unable to find overlay location")

        # the roles list can only be populated after the devices have been assigned
        # therefore, cannot be checked in validate which is executed at submission.
        if 'roles' not in self.job.parameters['protocols'][self.protocol]:
            raise RuntimeError("multinode definition without complete list of roles after assignment")

        # Generic scripts
        lava_path = os.path.abspath("%s/%s" % (location, lava_test_results_dir))
        scripts_to_copy = glob.glob(os.path.join(self.lava_multi_node_test_dir, 'lava-*'))
        self.logger.debug(self.lava_multi_node_test_dir)
        self.logger.debug("lava_path: %s", lava_path)
        self.logger.debug("scripts to copy %s", scripts_to_copy)

        for fname in scripts_to_copy:
            with open(fname, 'r') as fin:
                foutname = os.path.basename(fname)
                output_file = '%s/bin/%s' % (lava_path, foutname)
                self.logger.debug("Creating %s", output_file)
                with open(output_file, 'w') as fout:
                    fout.write("#!%s\n\n" % shell)
                    # Target-specific scripts (add ENV to the generic ones)
                    if foutname == 'lava-group':
                        fout.write('LAVA_GROUP="\n')
                        for client_name in self.job.parameters['protocols'][self.protocol]['roles']:
                            if client_name == 'yaml_line':
                                continue
                            role_line = self.job.parameters['protocols'][self.protocol]['roles'][client_name]
                            self.logger.debug("group roles:\t%s\t%s", client_name, role_line)
                            fout.write(r"\t%s\t%s\n" % (client_name, role_line))
                        fout.write('"\n')
                    elif foutname == 'lava-role':
                        fout.write("TARGET_ROLE='%s'\n" % self.job.parameters['protocols'][self.protocol]['role'])
                    elif foutname == 'lava-self':
                        fout.write("LAVA_HOSTNAME='%s'\n" % self.job.device.target)
                    else:
                        fout.write("LAVA_TEST_BIN='%s/bin'\n" % lava_test_results_dir)
                        fout.write("LAVA_MULTI_NODE_CACHE='%s'\n" % self.lava_multi_node_cache_file)
                        # always write out full debug logs
                        fout.write("LAVA_MULTI_NODE_DEBUG='yes'\n")
                    fout.write(fin.read())
                    os.fchmod(fout.fileno(), self.xmod)
        for fname in self.v2_scripts_to_copy:
            with open(fname, 'r') as fin:
                foutname = os.path.basename(fname)
                output_file = '%s/bin/%s' % (lava_path, foutname)
                self.logger.debug("Updating %s", output_file)
                with open(output_file, 'w') as fout:
                    fout.write("#!%s\n\n" % shell)
                    fout.write("LAVA_TEST_BIN='%s/bin'\n" % lava_test_results_dir)
                    fout.write("LAVA_MULTI_NODE_CACHE='%s'\n" % self.lava_multi_node_cache_file)
                    # always write out full debug logs
                    fout.write("LAVA_MULTI_NODE_DEBUG='yes'\n")
                    fout.write(fin.read())
                    os.fchmod(fout.fileno(), self.xmod)
        self.call_protocols()
        return connection


class VlandOverlayAction(OverlayAction):
    """
    Adds data for vland interface locations, MAC addresses and vlan names
    """
    def __init__(self):
        super(VlandOverlayAction, self).__init__()
        self.name = "lava-vland-overlay"
        self.summary = "Add files detailing vlan configuration."
        self.description = "Populate specific vland scripts for tests to lookup vlan data."

        # vland-only
        self.lava_vland_test_dir = os.path.realpath(
            '%s/../../../lava_test_shell/vland' % os.path.dirname(__file__))
        self.lava_vland_cache_file = '/tmp/lava_vland_cache.txt'
        self.params = {}
        self.sysfs = []
        self.tags = []
        self.names = []
        self.protocol = VlandProtocol.name

    def populate(self, parameters):
        # override the populate function of overlay action which provides the
        # lava test directory settings etc.
        pass

    def validate(self):
        super(VlandOverlayAction, self).validate()
        # idempotency
        if 'actions' not in self.job.parameters:
            return
        if 'protocols' not in self.job.parameters:
            return
        if self.protocol not in [protocol.name for protocol in self.job.protocols]:
            return
        if 'parameters' not in self.job.device:
            self.errors = "Device lacks parameters"
        elif 'interfaces' not in self.job.device['parameters']:
            self.errors = "Device lacks vland interfaces data."
        if not self.valid:
            return
        # same as the parameters of the protocol itself.
        self.params = self.job.parameters['protocols'][self.protocol]
        device_params = self.job.device['parameters']['interfaces']
        vprotocol = [vprotocol for vprotocol in self.job.protocols if vprotocol.name == self.protocol][0]
        # needs to be the configured interface for each vlan.
        for key, _ in self.params.items():
            if key == 'yaml_line' or key not in vprotocol.params:
                continue
            self.names.append(",".join([key, vprotocol.params[key]['iface']]))
        for interface in device_params:
            self.sysfs.append(",".join(
                [
                    interface,
                    device_params[interface]['mac'],
                    device_params[interface]['sysfs'],
                ])
            )
        for interface in device_params:
            if not device_params[interface]['tags']:
                # skip primary interface
                continue
            for tag in device_params[interface]['tags']:
                self.tags.append(",".join([interface, tag]))

    # pylint: disable=anomalous-backslash-in-string
    def run(self, connection, max_end_time, args=None):
        """
        Writes out file contents from lists, across multiple lines
        VAR="VAL1\n\
        VAL2\n\
        "
        The \n and \ are used to avoid unwanted whitespace, so are escaped.
        \n becomes \\n, \ becomes \\, which itself then needs \n to output:
        VAL1
        VAL2
        """
        if not self.params:
            self.logger.debug("skipped %s", self.name)
            return connection
        location = self.get_namespace_data(action='test', label='shared', key='location')
        lava_test_results_dir = self.get_namespace_data(action='test', label='results', key='lava_test_results_dir')
        shell = self.get_namespace_data(action='test', label='shared', key='lava_test_sh_cmd')
        if not location:
            raise RuntimeError("Missing lava overlay location")
        if not os.path.exists(location):
            raise RuntimeError("Unable to find overlay location")

        lava_path = os.path.abspath("%s/%s" % (location, lava_test_results_dir))
        scripts_to_copy = glob.glob(os.path.join(self.lava_vland_test_dir, 'lava-*'))
        self.logger.debug(self.lava_vland_test_dir)
        self.logger.debug({"lava_path": lava_path, "scripts": scripts_to_copy})

        for fname in scripts_to_copy:
            with open(fname, 'r') as fin:
                foutname = os.path.basename(fname)
                output_file = '%s/bin/%s' % (lava_path, foutname)
                self.logger.debug("Creating %s", output_file)
                with open(output_file, 'w') as fout:
                    fout.write("#!%s\n\n" % shell)
                    # Target-specific scripts (add ENV to the generic ones)
                    if foutname == 'lava-vland-self':
                        fout.write(r'LAVA_VLAND_SELF="')
                        for line in self.sysfs:
                            fout.write(r"%s\n" % line)
                    elif foutname == 'lava-vland-names':
                        fout.write(r'LAVA_VLAND_NAMES="')
                        for line in self.names:
                            fout.write(r"%s\n" % line)
                    elif foutname == 'lava-vland-tags':
                        fout.write(r'LAVA_VLAND_TAGS="')
                        if not self.tags:
                            fout.write(r"\n")
                        else:
                            for line in self.tags:
                                fout.write(r"%s\n" % line)
                    fout.write('"\n\n')
                    fout.write(fin.read())
                    os.fchmod(fout.fileno(), self.xmod)
        self.call_protocols()
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

    def run(self, connection, max_end_time, args=None):
        output = os.path.join(self.job.parameters['output_dir'],
                              "overlay-%s.tar.gz" % self.level)
        location = self.get_namespace_data(action='test', label='shared', key='location')
        lava_test_results_dir = self.get_namespace_data(action='test', label='results', key='lava_test_results_dir')
        self.set_namespace_data(action='test', label='shared', key='output', value=output)
        if not location:
            raise RuntimeError("Missing lava overlay location")
        if not os.path.exists(location):
            raise RuntimeError("Unable to find overlay location")
        if not self.valid:
            self.logger.error(self.errors)
            return connection
        connection = super(CompressOverlay, self).run(connection, max_end_time, args)
        cur_dir = os.getcwd()
        try:
            with tarfile.open(output, "w:gz") as tar:
                os.chdir(location)
                tar.add(".%s" % lava_test_results_dir)
                # ssh authorization support
                if os.path.exists('./root/'):
                    tar.add(".%s" % '/root/')
        except tarfile.TarError as exc:
            self.errors = "Unable to create lava overlay tarball: %s" % exc
            raise RuntimeError("Unable to create lava overlay tarball: %s" % exc)
        os.chdir(cur_dir)
        self.set_namespace_data(action=self.name, label='output', key='file', value=output)
        return connection


class SshAuthorize(Action):
    """
    Handle including the authorization (ssh public key) into the
    deployment as a file in the overlay and writing to
    /root/.ssh/authorized_keys.
    if /root/.ssh/authorized_keys exists in the test image it will be overwritten
    when the overlay tarball is unpacked onto the test image.
    The key exists in the lava_test_results_dir to allow test writers to work around this
    after logging in via the identity_file set here.
    Hacking sessions already append to the existing file.
    Used by secondary connections only.
    Primary connections need the keys set up by admins.
    """
    def __init__(self):
        super(SshAuthorize, self).__init__()
        self.name = "ssh-authorize"
        self.summary = 'add public key to authorized_keys'
        self.description = 'include public key in overlay and authorize root user'
        self.active = False
        self.identity_file = None

    def validate(self):
        super(SshAuthorize, self).validate()
        if 'to' in self.parameters:
            if self.parameters['to'] == 'ssh':
                return
        if 'authorize' in self.parameters:
            if self.parameters['authorize'] != 'ssh':
                return
        if not any('ssh' in data for data in self.job.device['actions']['deploy']['methods']):
            # idempotency - leave self.identity_file as None
            return
        params = self.job.device['actions']['deploy']['methods']
        check = check_ssh_identity_file(params)
        if check[0]:
            self.errors = check[0]
        elif check[1]:
            self.identity_file = check[1]
        if self.valid:
            self.set_namespace_data(action=self.name, label='authorize', key='identity_file', value=self.identity_file)
            if 'authorize' in self.parameters:
                # only secondary connections set active.
                self.active = True

    def run(self, connection, max_end_time, args=None):
        connection = super(SshAuthorize, self).run(connection, max_end_time, args)
        if not self.identity_file:
            self.logger.debug("No authorisation required.")  # idempotency
            return connection
        # add the authorization keys to the overlay
        location = self.get_namespace_data(action='test', label='shared', key='location')
        lava_test_results_dir = self.get_namespace_data(action='test', label='results', key='lava_test_results_dir')
        if not location:
            raise RuntimeError("Missing lava overlay location")
        if not os.path.exists(location):
            raise RuntimeError("Unable to find overlay location")
        lava_path = os.path.abspath("%s/%s" % (location, lava_test_results_dir))
        output_file = '%s/%s' % (lava_path, os.path.basename(self.identity_file))
        shutil.copyfile(self.identity_file, output_file)
        shutil.copyfile("%s.pub" % self.identity_file, "%s.pub" % output_file)
        if not self.active:
            # secondary connections only
            return connection
        self.logger.info("Adding SSH authorisation for %s.pub", os.path.basename(output_file))
        user_sshdir = os.path.join(location, 'root', '.ssh')
        if not os.path.exists(user_sshdir):
            os.makedirs(user_sshdir, 0o755)
        # if /root/.ssh/authorized_keys exists in the test image it will be overwritten
        # the key exists in the lava_test_results_dir to allow test writers to work around this
        # after logging in via the identity_file set here
        authorize = os.path.join(user_sshdir, 'authorized_keys')
        self.logger.debug("Copying %s to %s", "%s.pub" % self.identity_file, authorize)
        shutil.copyfile("%s.pub" % self.identity_file, authorize)
        os.chmod(authorize, 0o600)
        return connection


class PersistentNFSOverlay(Action):
    """
    Instead of extracting, just populate the location of the persistent NFS
    so that it can be mounted later when the overlay is applied.
    """

    def __init__(self):
        super(PersistentNFSOverlay, self).__init__()
        self.name = "persistent-nfs-overlay"
        self.section = 'deploy'
        self.summary = "add test overlay to NFS"
        self.description = "unpack overlay into persistent NFS"

    def validate(self):
        super(PersistentNFSOverlay, self).validate()
        if 'nfs_url' not in self.parameters:
            return None
        if ':' not in self.parameters['nfs_url']:
            self.errors = "Unrecognised NFS URL: '%s'" % self.parameters['nfs_url']
            return
        nfs_server, dirname = self.parameters['nfs_url'].split(':')
        self.errors = infrastructure_error('rpcinfo')
        self.errors = rpcinfo_nfs(nfs_server)
        self.set_namespace_data(action=self.name, label='nfs_url', key='nfsroot', value=dirname)
        self.set_namespace_data(action=self.name, label='nfs_url', key='serverip', value=nfs_server)
