# Copyright (C) 2014 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import glob
import os
import shlex
import shutil
import stat
import tarfile

from lava_common.exceptions import InfrastructureError, LAVABug
from lava_dispatcher.action import Action, Pipeline
from lava_dispatcher.actions.deploy.testdef import TestDefinitionAction
from lava_dispatcher.logical import Deployment
from lava_dispatcher.protocols.multinode import MultinodeProtocol
from lava_dispatcher.protocols.vland import VlandProtocol
from lava_dispatcher.utils.contextmanager import chdir
from lava_dispatcher.utils.filesystem import check_ssh_identity_file
from lava_dispatcher.utils.network import dispatcher_ip, rpcinfo_nfs
from lava_dispatcher.utils.shell import which


class Overlay(Deployment):
    compatibility = 4
    name = "overlay"

    @classmethod
    def action(cls):
        return OverlayAction()

    @classmethod
    def accepts(cls, device, parameters):
        if "overlay" not in device["actions"]["deploy"]["methods"]:
            return False, "'overlay' not in the device configuration deploy methods"
        if parameters["to"] != "overlay":
            return False, '"to" parameter is not "overlay"'
        return True, "accepted"


class CreateOverlay(Action):
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

    name = "lava-create-overlay"
    description = "add lava scripts during deployment for test shell use"
    summary = "overlay the lava support scripts"

    def __init__(self):
        super().__init__()
        self.lava_test_dir = os.path.realpath(
            "%s/../../lava_test_shell" % os.path.dirname(__file__)
        )
        self.scripts_to_copy = []
        # 755 file permissions
        self.xmod = (
            stat.S_IRWXU | stat.S_IXGRP | stat.S_IRGRP | stat.S_IXOTH | stat.S_IROTH
        )
        self.target_mac = ""
        self.target_ip = ""
        self.probe_ip = ""
        self.probe_channel = ""
        self.dispatcher_ip = ""

    def validate(self):
        super().validate()
        self.scripts_to_copy = sorted(
            glob.glob(os.path.join(self.lava_test_dir, "lava-*"))
        )

        lava_test_results_dir = self.get_constant("lava_test_results_dir", "posix")
        lava_test_results_dir = lava_test_results_dir % self.job.job_id
        self.set_namespace_data(
            action="test",
            label="results",
            key="lava_test_results_dir",
            value=lava_test_results_dir,
        )
        lava_test_sh_cmd = self.get_constant("lava_test_sh_cmd", "posix")
        self.set_namespace_data(
            action="test",
            label="shared",
            key="lava_test_sh_cmd",
            value=lava_test_sh_cmd,
        )

        # Add distro support scripts - only if deployment_data is set
        distro = self.parameters.get("deployment_data", {}).get("distro")
        if distro:
            distro_support_dir = "%s/distro/%s" % (self.lava_test_dir, distro)
            self.scripts_to_copy += sorted(
                glob.glob(os.path.join(distro_support_dir, "lava-*"))
            )

        if not self.scripts_to_copy:
            self.logger.debug("Skipping lava_test_shell support scripts.")
        if "parameters" in self.job.device:
            if "interfaces" in self.job.device["parameters"]:
                if "target" in self.job.device["parameters"]["interfaces"]:
                    self.target_mac = self.job.device["parameters"]["interfaces"][
                        "target"
                    ].get("mac", "")
                    self.target_ip = self.job.device["parameters"]["interfaces"][
                        "target"
                    ].get("ip", "")
        for device in self.job.device.get("static_info", []):
            if "probe_channel" in device and "probe_ip" in device:
                self.probe_channel = device["probe_channel"]
                self.probe_ip = device["probe_ip"]
                break

        self.dispatcher_ip = dispatcher_ip(self.job.parameters["dispatcher"])

    def populate(self, parameters):
        self.pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        if any(
            "ssh" in data for data in self.job.device["actions"]["deploy"]["methods"]
        ):
            # only devices supporting ssh deployments add this action.
            self.pipeline.add_action(SshAuthorize())
        self.pipeline.add_action(VlandOverlayAction())
        self.pipeline.add_action(MultinodeOverlayAction())
        self.pipeline.add_action(TestDefinitionAction())
        # Skip compress-overlay for actions that mount overlay directory
        # that located on lava worker directly.
        skip_overlay_compression = False
        # Skip compress-overlay for 'to: docker' deploy action.
        if parameters.get("to") == "docker":
            skip_overlay_compression = True
        # Skip compress-overlay for docker test shell based test action.
        if {"docker", "definitions"}.issubset(parameters):
            skip_overlay_compression = True
        if not skip_overlay_compression:
            self.pipeline.add_action(CompressOverlay())
        self.pipeline.add_action(PersistentNFSOverlay())  # idempotent

    def _export_data(self, fout, data, prefix):
        if isinstance(data, dict):
            if prefix:
                prefix += "_"
            for key, value in data.items():
                self._export_data(fout, value, "%s%s" % (prefix, key))
        elif isinstance(data, (list, tuple)):
            if prefix:
                prefix += "_"
            for index, value in enumerate(data):
                self._export_data(fout, value, "%s%s" % (prefix, index))
        else:
            if isinstance(data, bool):
                data = "1" if data else "0"
            elif isinstance(data, int):
                data = data
            else:
                data = shlex.quote(data)
            self.logger.debug("- %s=%s", prefix, data)
            fout.write("export %s=%s\n" % (prefix, data))

    def run(self, connection, max_end_time):
        tmp_dir = self.mkdtemp()
        self.set_namespace_data(
            action="test", label="shared", key="location", value=tmp_dir
        )
        lava_test_results_dir = self.get_namespace_data(
            action="test", label="results", key="lava_test_results_dir"
        )
        if not lava_test_results_dir:
            raise LAVABug("Unable to identify top level lava test directory")
        shell = self.get_namespace_data(
            action="test", label="shared", key="lava_test_sh_cmd"
        )
        namespace = self.parameters.get("namespace")
        self.logger.debug("[%s] Preparing overlay tarball in %s", namespace, tmp_dir)
        lava_path = os.path.abspath("%s/%s" % (tmp_dir, lava_test_results_dir))
        for runner_dir in ["bin", "tests", "results"]:
            # avoid os.path.join as lava_test_results_dir startswith / so location is *dropped* by join.
            path = os.path.abspath("%s/%s" % (lava_path, runner_dir))
            if not os.path.exists(path):
                os.makedirs(path, 0o755)
                self.logger.debug("makedir: %s", path)
        for fname in self.scripts_to_copy:
            with open(fname) as fin:
                foutname = os.path.basename(fname)
                output_file = "%s/bin/%s" % (lava_path, foutname)
                if "distro" in fname:
                    distribution = os.path.basename(os.path.dirname(fname))
                    self.logger.debug("Updating %s (%s)", output_file, distribution)
                else:
                    self.logger.debug("Creating %s", output_file)
                with open(output_file, "w") as fout:
                    fout.write("#!%s\n\n" % shell)
                    if foutname == "lava-target-mac":
                        fout.write("TARGET_DEVICE_MAC='%s'\n" % self.target_mac)
                    if foutname == "lava-target-ip":
                        fout.write("TARGET_DEVICE_IP='%s'\n" % self.target_ip)
                    if foutname == "lava-probe-ip":
                        fout.write("PROBE_DEVICE_IP='%s'\n" % self.probe_ip)
                    if foutname == "lava-probe-channel":
                        fout.write("PROBE_DEVICE_CHANNEL='%s'\n" % self.probe_channel)
                    if foutname == "lava-target-storage":
                        fout.write('LAVA_STORAGE="\n')
                        for method in self.job.device.get("storage_info", [{}]):
                            for key, value in method.items():
                                self.logger.debug(
                                    "storage methods:\t%s\t%s", key, value
                                )
                                fout.write(r"\t%s\t%s\n" % (key, value))
                        fout.write('"\n')
                    fout.write(fin.read())
                    os.fchmod(fout.fileno(), self.xmod)

        # Generate environment file
        self.logger.debug("Creating %s/environment", lava_path)
        with open(os.path.join(lava_path, "environment"), "w") as fout:
            sources = [
                ("environment", ""),
                ("device_info", "LAVA_DEVICE_INFO"),
                ("static_info", "LAVA_STATIC_INFO"),
                ("storage_info", "LAVA_STORAGE_INFO"),
            ]
            for source, prefix in sources:
                data = self.job.device.get(source, {})
                if data:
                    self.logger.debug("%s:", source)
                    self._export_data(fout, data, prefix)
            data = None
            if (
                "protocols" in self.job.parameters
                and "lava-multinode" in self.job.parameters["protocols"]
                and "environment" in self.job.parameters["protocols"]["lava-multinode"]
            ):
                data = self.job.parameters["protocols"]["lava-multinode"]["environment"]
            elif "environment" in self.job.parameters:
                data = self.job.parameters["environment"]
            if data:
                self.logger.debug("job environment:")
                self._export_data(fout, data, "")

            # TODO: Add LAVA_URL?
            self.logger.debug("LAVA metadata")
            self._export_data(fout, self.job.job_id, "LAVA_JOB_ID")
            self._export_data(fout, self.dispatcher_ip, "LAVA_DISPATCHER_IP")

        # Generate the file containing the secrets
        if "secrets" in self.job.parameters:
            self.logger.debug("Creating %s/secrets", lava_path)
            with open(os.path.join(lava_path, "secrets"), "w") as fout:
                for key, value in self.job.parameters["secrets"].items():
                    fout.write("%s=%s\n" % (key, value))

        if "env_dut" in self.job.parameters:
            environment = self.get_namespace_data(
                action="deploy-device-env", label="environment", key="env_dict"
            )
            if environment is not None:
                self.logger.debug("Creating %s/secrets with env", lava_path)
                with open(os.path.join(lava_path, "secrets"), "a") as fout:
                    for key in environment:
                        self.logger.debug("Handling %s", key)
                        fout.write("%s=%s\n" % (key, environment[key]))

        connection = super().run(connection, max_end_time)
        return connection


class OverlayAction(CreateOverlay):
    """
    Creates an overlay, but only if it has been requested by any of the test
    actions (in contrast with CreateOverlay, that creates the overlay
    unconditionally).
    """

    name = "lava-overlay"
    description = "add lava scripts during deployment for test shell use"
    summary = "overlay the lava support scripts"

    def validate(self):
        if not self.test_needs_overlay(self.parameters):
            return

        super().validate()

    def populate(self, parameters):
        if not self.test_needs_overlay(parameters):
            self.pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
            return

        super().populate(parameters)

    def run(self, connection, max_end_time):
        """
        Check if a lava-test-shell has been requested, implement the overlay
        * create test runner directories beneath the temporary location
        * copy runners into test runner directories
        """
        if not self.test_needs_overlay(self.parameters):
            namespace = self.parameters.get("namespace")
            self.logger.info("[%s] skipped %s - no test action.", namespace, self.name)
            return connection

        return super().run(connection, max_end_time)


class MultinodeOverlayAction(OverlayAction):
    name = "lava-multinode-overlay"
    description = "add lava scripts during deployment for multinode test shell use"
    summary = "overlay the lava multinode scripts"

    def __init__(self):
        super().__init__()
        # Multinode-only
        self.lava_multi_node_test_dir = os.path.realpath(
            "%s/../../lava_test_shell/multi_node" % os.path.dirname(__file__)
        )
        self.lava_multi_node_cache_file = (
            "/tmp/lava_multi_node_cache.txt"  # nosec - on the DUT
        )
        self.role = None
        self.protocol = MultinodeProtocol.name

    def populate(self, parameters):
        # override the populate function of overlay action which provides the
        # lava test directory settings etc.
        pass

    def validate(self):
        super().validate()
        # idempotency
        if "actions" not in self.job.parameters:
            return
        if "protocols" in self.job.parameters and self.protocol in [
            protocol.name for protocol in self.job.protocols
        ]:
            if "target_group" not in self.job.parameters["protocols"][self.protocol]:
                return
            if "role" not in self.job.parameters["protocols"][self.protocol]:
                self.errors = "multinode job without a specified role"
            else:
                self.role = self.job.parameters["protocols"][self.protocol]["role"]

    def run(self, connection, max_end_time):
        if self.role is None:
            self.logger.debug("skipped %s", self.name)
            return connection
        lava_test_results_dir = self.get_namespace_data(
            action="test", label="results", key="lava_test_results_dir"
        )
        shell = self.get_namespace_data(
            action="test", label="shared", key="lava_test_sh_cmd"
        )
        location = self.get_namespace_data(
            action="test", label="shared", key="location"
        )
        if not location:
            raise LAVABug("Missing lava overlay location")
        if not os.path.exists(location):
            raise LAVABug("Unable to find overlay location")

        # the roles list can only be populated after the devices have been assigned
        # therefore, cannot be checked in validate which is executed at submission.
        if "roles" not in self.job.parameters["protocols"][self.protocol]:
            raise LAVABug(
                "multinode definition without complete list of roles after assignment"
            )

        # Generic scripts
        lava_path = os.path.abspath("%s/%s" % (location, lava_test_results_dir))
        scripts_to_copy = glob.glob(
            os.path.join(self.lava_multi_node_test_dir, "lava-*")
        )
        self.logger.debug(self.lava_multi_node_test_dir)
        self.logger.debug("lava_path: %s", lava_path)
        self.logger.debug("scripts to copy %s", scripts_to_copy)

        for fname in scripts_to_copy:
            with open(fname) as fin:
                foutname = os.path.basename(fname)
                output_file = "%s/bin/%s" % (lava_path, foutname)
                self.logger.debug("Creating %s", output_file)
                with open(output_file, "w") as fout:
                    fout.write("#!%s\n\n" % shell)
                    # Target-specific scripts (add ENV to the generic ones)
                    if foutname == "lava-group":
                        fout.write('LAVA_GROUP="\n')
                        for client_name in self.job.parameters["protocols"][
                            self.protocol
                        ]["roles"]:
                            role_line = self.job.parameters["protocols"][self.protocol][
                                "roles"
                            ][client_name]
                            self.logger.debug(
                                "group roles:\t%s\t%s", client_name, role_line
                            )
                            fout.write(r"\t%s\t%s\n" % (client_name, role_line))
                        fout.write('"\n')
                    elif foutname == "lava-role":
                        fout.write(
                            "TARGET_ROLE='%s'\n"
                            % self.job.parameters["protocols"][self.protocol]["role"]
                        )
                    elif foutname == "lava-self":
                        fout.write("LAVA_HOSTNAME='%s'\n" % self.job.job_id)
                    else:
                        fout.write("LAVA_TEST_BIN='%s/bin'\n" % lava_test_results_dir)
                        fout.write(
                            "LAVA_MULTI_NODE_CACHE='%s'\n"
                            % self.lava_multi_node_cache_file
                        )
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

    name = "lava-vland-overlay"
    description = "Populate specific vland scripts for tests to lookup vlan data."
    summary = "Add files detailing vlan configuration."

    def __init__(self):
        super().__init__()
        # vland-only
        self.lava_vland_test_dir = os.path.realpath(
            "%s/../../lava_test_shell/vland" % os.path.dirname(__file__)
        )
        self.lava_vland_cache_file = "/tmp/lava_vland_cache.txt"  # nosec - on the DUT
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
        super().validate()
        # idempotency
        if "actions" not in self.job.parameters:
            return
        if "protocols" not in self.job.parameters:
            return
        if self.protocol not in [protocol.name for protocol in self.job.protocols]:
            return
        if "parameters" not in self.job.device:
            self.errors = "Device lacks parameters"
        elif "interfaces" not in self.job.device["parameters"]:
            self.errors = "Device lacks vland interfaces data."
        if not self.valid:
            return
        # same as the parameters of the protocol itself.
        self.params = self.job.parameters["protocols"][self.protocol]
        device_params = self.job.device["parameters"]["interfaces"]
        vprotocol = [
            vprotocol
            for vprotocol in self.job.protocols
            if vprotocol.name == self.protocol
        ][0]
        # needs to be the configured interface for each vlan.
        for key, _ in self.params.items():
            if key not in vprotocol.params:
                continue
            self.names.append(",".join([key, vprotocol.params[key]["iface"]]))
        for interface in device_params:
            self.sysfs.append(
                ",".join(
                    [
                        interface,
                        device_params[interface]["mac"],
                        device_params[interface]["sysfs"],
                    ]
                )
            )
        for interface in device_params:
            if not device_params[interface]["tags"]:
                # skip primary interface
                continue
            for tag in device_params[interface]["tags"]:
                self.tags.append(",".join([interface, tag]))

    def run(self, connection, max_end_time):
        """
        Writes out file contents from lists, across multiple lines
        VAR="VAL1\n
        VAL2\n
        "
        The newline and escape characters are used to avoid unwanted whitespace.
        \n becomes \\n, a single escape gets expanded and itself then needs \n to output:
        VAL1
        VAL2
        """
        if not self.params:
            self.logger.debug("skipped %s", self.name)
            return connection
        location = self.get_namespace_data(
            action="test", label="shared", key="location"
        )
        lava_test_results_dir = self.get_namespace_data(
            action="test", label="results", key="lava_test_results_dir"
        )
        shell = self.get_namespace_data(
            action="test", label="shared", key="lava_test_sh_cmd"
        )
        if not location:
            raise LAVABug("Missing lava overlay location")
        if not os.path.exists(location):
            raise LAVABug("Unable to find overlay location")

        lava_path = os.path.abspath("%s/%s" % (location, lava_test_results_dir))
        scripts_to_copy = glob.glob(os.path.join(self.lava_vland_test_dir, "lava-*"))
        self.logger.debug(self.lava_vland_test_dir)
        self.logger.debug({"lava_path": lava_path, "scripts": scripts_to_copy})

        for fname in scripts_to_copy:
            with open(fname) as fin:
                foutname = os.path.basename(fname)
                output_file = "%s/bin/%s" % (lava_path, foutname)
                self.logger.debug("Creating %s", output_file)
                with open(output_file, "w") as fout:
                    fout.write("#!%s\n\n" % shell)
                    # Target-specific scripts (add ENV to the generic ones)
                    if foutname == "lava-vland-self":
                        fout.write(r'LAVA_VLAND_SELF="')
                        for line in self.sysfs:
                            fout.write(r"%s\n" % line)
                    elif foutname == "lava-vland-names":
                        fout.write(r'LAVA_VLAND_NAMES="')
                        for line in self.names:
                            fout.write(r"%s\n" % line)
                    elif foutname == "lava-vland-tags":
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

    name = "compress-overlay"
    description = "Create a lava overlay tarball and store alongside the job"
    summary = "Compress the lava overlay files"

    def run(self, connection, max_end_time):
        output = os.path.join(self.mkdtemp(), "overlay-%s.tar.gz" % self.level)
        location = self.get_namespace_data(
            action="test", label="shared", key="location"
        )
        lava_test_results_dir = self.get_namespace_data(
            action="test", label="results", key="lava_test_results_dir"
        )
        self.set_namespace_data(
            action="test", label="shared", key="output", value=output
        )
        if not location:
            raise LAVABug("Missing lava overlay location")
        if not os.path.exists(location):
            raise LAVABug("Unable to find overlay location")
        if not self.valid:
            self.logger.error(self.errors)
            return connection
        connection = super().run(connection, max_end_time)
        # This will split the path into two parts. Second part is only the
        # bottom level directory. The first part is the rest.
        # Example: /run/mount/lava/ will be split to /run/mount/ and lava/
        # Used to create a tarball with only the bottom level dir included and
        # not with the whole lava_test_results_dir property.
        results_dir_list = os.path.split(os.path.normpath(lava_test_results_dir))
        with chdir(
            os.path.join(location, os.path.relpath(results_dir_list[0], os.sep))
        ):
            try:
                with tarfile.open(output, "w:gz") as tar:
                    tar.add("%s" % results_dir_list[1])
                    # ssh authorization support
                    if os.path.exists("./root/"):
                        tar.add(".%s" % "/root/")
            except tarfile.TarError as exc:
                raise InfrastructureError(
                    "Unable to create lava overlay tarball: %s" % exc
                )

        self.set_namespace_data(
            action=self.name, label="output", key="file", value=output
        )
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

    name = "ssh-authorize"
    description = "include public key in overlay and authorize root user"
    summary = "add public key to authorized_keys"

    def __init__(self):
        super().__init__()
        self.active = False
        self.identity_file = None

    def validate(self):
        super().validate()
        if "to" in self.parameters:
            if self.parameters["to"] == "ssh":
                return
        if "authorize" in self.parameters:
            if self.parameters["authorize"] != "ssh":
                return
        if not any(
            "ssh" in data for data in self.job.device["actions"]["deploy"]["methods"]
        ):
            # idempotency - leave self.identity_file as None
            return
        params = self.job.device["actions"]["deploy"]["methods"]
        check = check_ssh_identity_file(params)
        if check[0]:
            self.errors = check[0]
        elif check[1]:
            self.identity_file = check[1]
        if self.valid:
            self.set_namespace_data(
                action=self.name,
                label="authorize",
                key="identity_file",
                value=self.identity_file,
            )
            if "authorize" in self.parameters:
                # only secondary connections set active.
                self.active = True

    def run(self, connection, max_end_time):
        connection = super().run(connection, max_end_time)
        if not self.identity_file:
            self.logger.debug("No authorisation required.")  # idempotency
            return connection
        # add the authorization keys to the overlay
        location = self.get_namespace_data(
            action="test", label="shared", key="location"
        )
        lava_test_results_dir = self.get_namespace_data(
            action="test", label="results", key="lava_test_results_dir"
        )
        if not location:
            raise LAVABug("Missing lava overlay location")
        if not os.path.exists(location):
            raise LAVABug("Unable to find overlay location")
        lava_path = os.path.abspath("%s/%s" % (location, lava_test_results_dir))
        output_file = "%s/%s" % (lava_path, os.path.basename(self.identity_file))
        shutil.copyfile(self.identity_file, output_file)
        shutil.copyfile("%s.pub" % self.identity_file, "%s.pub" % output_file)
        if not self.active:
            # secondary connections only
            return connection
        self.logger.info(
            "Adding SSH authorisation for %s.pub", os.path.basename(output_file)
        )
        user_sshdir = os.path.join(location, "root", ".ssh")
        os.makedirs(user_sshdir, 0o755, exist_ok=True)
        # if /root/.ssh/authorized_keys exists in the test image it will be overwritten
        # the key exists in the lava_test_results_dir to allow test writers to work around this
        # after logging in via the identity_file set here
        authorize = os.path.join(user_sshdir, "authorized_keys")
        self.logger.debug("Copying %s to %s", "%s.pub" % self.identity_file, authorize)
        shutil.copyfile("%s.pub" % self.identity_file, authorize)
        os.chmod(authorize, 0o600)
        return connection


class PersistentNFSOverlay(Action):
    """
    Instead of extracting, just populate the location of the persistent NFS
    so that it can be mounted later when the overlay is applied.
    """

    name = "persistent-nfs-overlay"
    description = "unpack overlay into persistent NFS"
    summary = "add test overlay to NFS"

    def validate(self):
        super().validate()
        persist = self.parameters.get("persistent_nfs")
        if not persist:
            return
        if "address" not in persist:
            self.errors = "Missing address for persistent NFS"
            return
        if ":" not in persist["address"]:
            self.errors = (
                "Unrecognised NFS URL: '%s'"
                % self.parameters["persistent_nfs"]["address"]
            )
            return
        nfs_server, dirname = persist["address"].split(":")
        which("rpcinfo")
        self.errors = rpcinfo_nfs(nfs_server)
        self.set_namespace_data(
            action=self.name, label="nfs_address", key="nfsroot", value=dirname
        )
        self.set_namespace_data(
            action=self.name, label="nfs_address", key="serverip", value=nfs_server
        )

        self.job.device["dynamic_data"]["NFS_ROOTFS"] = dirname
        self.job.device["dynamic_data"]["NFS_SERVER_IP"] = nfs_server
