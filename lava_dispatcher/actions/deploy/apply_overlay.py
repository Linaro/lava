# Copyright (C) 2014 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import os
import shutil
from functools import partial

import guestfs

from lava_common.constants import RAMDISK_FNAME, UBOOT_DEFAULT_HEADER_LENGTH
from lava_common.exceptions import InfrastructureError, JobError, LAVABug
from lava_common.utils import debian_filename_version
from lava_dispatcher.action import Action, Pipeline
from lava_dispatcher.actions.deploy.overlay import OverlayAction
from lava_dispatcher.actions.deploy.prepare import PrepareKernelAction
from lava_dispatcher.utils.compression import (
    compress_file,
    cpio,
    create_tarfile,
    decompress_file,
    uncpio,
    untar_file,
)
from lava_dispatcher.utils.filesystem import (
    copy_in_overlay,
    copy_overlay_to_sparse_fs,
    is_sparse_image,
    lxc_path,
    mkdtemp,
    prepare_guestfs,
)
from lava_dispatcher.utils.installers import add_late_command, add_to_kickstart
from lava_dispatcher.utils.network import dispatcher_ip
from lava_dispatcher.utils.shell import which
from lava_dispatcher.utils.strings import substitute


class ApplyOverlayGuest(Action):
    name = "apply-overlay-guest"
    description = "prepare a qcow2 drive containing the overlay"
    summary = "build a guest filesystem with the overlay"
    timeout_exception = InfrastructureError

    def __init__(self):
        super().__init__()
        self.guest_filename = "lava-guest.qcow2"

    def validate(self):
        super().validate()
        self.set_namespace_data(
            action=self.name, label="guest", key="name", value=self.guest_filename
        )
        if (
            "guest"
            not in self.job.device["actions"]["deploy"]["methods"]["image"][
                "parameters"
            ]
        ):
            self.errors = (
                "Device configuration does not specify size of guest filesystem."
            )

    def run(self, connection, max_end_time):
        applied = self.get_namespace_data(
            action="append-overlays", label="guest", key="applied"
        )
        if applied:
            self.logger.debug("Overlay already applied")
            return connection

        overlay_file = self.get_namespace_data(
            action="compress-overlay", label="output", key="file"
        )
        if not overlay_file:
            raise LAVABug("Unable to find the overlay")
        self.logger.debug("Overlay: %s", overlay_file)
        guest_dir = self.mkdtemp()
        guest_file = os.path.join(guest_dir, self.guest_filename)
        self.set_namespace_data(
            action=self.name, label="guest", key="filename", value=guest_file
        )
        mountpoint = self.get_namespace_data(
            action="test", label="results", key="lava_test_results_dir"
        )

        blkid = prepare_guestfs(
            guest_file,
            overlay_file,
            mountpoint,
            self.job.device["actions"]["deploy"]["methods"]["image"]["parameters"][
                "guest"
            ]["size"],
        )
        self.results = {"success": blkid}
        self.set_namespace_data(
            action=self.name, label="guest", key="UUID", value=blkid
        )
        return connection


class ApplyOverlayImage(Action):
    name = "apply-overlay-image"
    description = "apply overlay via guestfs to the test image"
    summary = "apply overlay to test image"
    timeout_exception = InfrastructureError

    def __init__(self, image_key="image", use_root_partition=True):
        super().__init__()
        self.image_key = image_key
        self.use_root_partition = use_root_partition

    def run(self, connection, max_end_time):
        overlay_file = self.get_namespace_data(
            action="compress-overlay", label="output", key="file"
        )
        if overlay_file:
            self.logger.debug("Overlay: %s", overlay_file)
            decompressed_image = self.get_namespace_data(
                action="download-action", label=self.image_key, key="file"
            )
            self.logger.debug("Image: %s", decompressed_image)
            root_partition = None

            if self.use_root_partition:
                if (
                    self.image_key not in self.parameters.keys()
                    and "images" in self.parameters.keys()
                ):
                    if self.image_key in self.parameters["images"]:
                        root_partition = self.parameters["images"][self.image_key].get(
                            "root_partition"
                        )
                    else:
                        raise JobError(
                            "Unable to find image configuration for '{image}'".format(
                                image=self.image_key
                            )
                        )
                else:
                    root_partition = self.parameters[self.image_key].get(
                        "root_partition"
                    )

                if root_partition is None:
                    raise JobError(
                        "Unable to apply the overlay image without 'root_partition'"
                    )
                self.logger.debug("root_partition: %s", root_partition)

            copy_in_overlay(decompressed_image, root_partition, overlay_file)
        else:
            self.logger.debug("No overlay to deploy")
        return connection


class ApplyOverlaySparseImage(Action):
    name = "apply-overlay-sparse-image"
    description = "apply overlay to sparse image"
    summary = "apply overlay to sparse image"
    command_exception = InfrastructureError
    timeout_exception = InfrastructureError

    def __init__(self, image_key):
        super().__init__()
        self.image_key = image_key  # the sparse image key in the parameters

    def validate(self):
        super().validate()
        binary = which("simg2img")
        self.logger.info(debian_filename_version(binary))
        which("mount")
        which("umount")
        binary = which("img2simg")
        self.logger.info(debian_filename_version(binary))

    def run(self, connection, max_end_time):
        overlay_file = self.get_namespace_data(
            action="compress-overlay", label="output", key="file"
        )
        if not overlay_file:
            self.logger.debug("No overlay to deploy")
            return connection
        self.logger.debug("Overlay: %s", overlay_file)
        decompressed_image = self.get_namespace_data(
            action="download-action", label=self.image_key, key="file"
        )
        self.logger.debug("Image: %s", decompressed_image)
        ext4_img = decompressed_image + ".ext4"
        # Check if the given image is an Android sparse image
        if not is_sparse_image(decompressed_image):
            raise JobError(
                "Image is not an Android sparse image: %s" % decompressed_image
            )
        command_list = ["/usr/bin/simg2img", decompressed_image, ext4_img]
        self.run_cmd(
            command_list, error_msg="simg2img failed for %s" % decompressed_image
        )
        self.logger.debug("Copying overlay")
        copy_overlay_to_sparse_fs(ext4_img, overlay_file)
        command_list = ["/usr/bin/img2simg", ext4_img, decompressed_image]
        self.run_cmd(command_list, error_msg="img2simg failed for %s" % ext4_img)
        os.remove(ext4_img)
        return connection


class PrepareOverlayTftp(Action):
    """
    Extracts the ramdisk or nfsrootfs in preparation for the lava overlay
    """

    name = "prepare-tftp-overlay"
    description = "extract ramdisk or nfsrootfs in preparation for lava overlay"
    summary = "extract ramdisk or nfsrootfs"
    timeout_exception = InfrastructureError

    def populate(self, parameters):
        self.pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        self.pipeline.add_action(
            ExtractNfsRootfs()
        )  # idempotent, checks for nfsrootfs parameter
        self.pipeline.add_action(OverlayAction())  # idempotent, includes testdef
        self.pipeline.add_action(
            ExtractRamdisk()
        )  # idempotent, checks for a ramdisk parameter
        self.pipeline.add_action(
            ExtractModules()
        )  # idempotent, checks for a modules parameter
        self.pipeline.add_action(ApplyOverlayTftp())
        if "kernel" in parameters and "type" in parameters["kernel"]:
            self.pipeline.add_action(PrepareKernelAction())
        self.pipeline.add_action(
            ConfigurePreseedFile()
        )  # idempotent, checks for a preseed parameter
        self.pipeline.add_action(
            CompressRamdisk()
        )  # idempotent, checks for a ramdisk parameter
        if "depthcharge" in self.job.device["actions"]["boot"]["methods"]:
            self.pipeline.add_action(PrepareKernelAction())

    def run(self, connection, max_end_time):
        connection = super().run(connection, max_end_time)
        ramdisk = self.get_namespace_data(
            action="download-action", label="file", key="ramdisk"
        )
        if ramdisk:  # nothing else to do
            return connection
        return connection


class ApplyOverlayTftp(Action):
    """
    Unpacks the overlay on top of the ramdisk or nfsrootfs
    Implicit default order: overlay goes into the NFS by preference
    only into the ramdisk if NFS not specified
    Other actions applying overlays for other deployments need their
    own logic.
    """

    name = "apply-overlay-tftp"
    description = "unpack the overlay into the nfsrootfs or ramdisk"
    summary = "apply lava overlay test files"
    timeout_exception = InfrastructureError

    def validate(self):
        super().validate()
        persist = self.parameters.get("persistent_nfs")
        if persist:
            if not isinstance(persist, dict):
                self.errors = "Invalid persistent_nfs parameter."
            if "address" not in persist:
                self.errors = "Missing address for persistent NFS"

    def run(self, connection, max_end_time):
        connection = super().run(connection, max_end_time)
        directory = None
        nfs_address = None
        overlay_file = None
        namespace = self.parameters.get("namespace")
        if self.parameters.get("nfsrootfs") is not None:
            if not self.parameters["nfsrootfs"].get("install_overlay", True):
                self.logger.info("[%s] Skipping applying overlay to NFS", namespace)
                return connection
            overlay_file = self.get_namespace_data(
                action="compress-overlay", label="output", key="file"
            )
            directory = self.get_namespace_data(
                action="extract-rootfs", label="file", key="nfsroot"
            )
            if overlay_file:
                self.logger.info("[%s] Applying overlay to NFS", namespace)
        elif self.parameters.get("images", {}).get("nfsrootfs") is not None:
            if not self.parameters["images"]["nfsrootfs"].get("install_overlay", True):
                self.logger.info("[%s] Skipping applying overlay to NFS", namespace)
                return connection
            overlay_file = self.get_namespace_data(
                action="compress-overlay", label="output", key="file"
            )
            directory = self.get_namespace_data(
                action="extract-rootfs", label="file", key="nfsroot"
            )
            if overlay_file:
                self.logger.info("[%s] Applying overlay to NFS", namespace)
        elif self.parameters.get("persistent_nfs") is not None:
            if not self.parameters["persistent_nfs"].get("install_overlay", True):
                self.logger.info(
                    "[%s] Skipping applying overlay to persistent NFS", namespace
                )
                return connection
            overlay_file = self.get_namespace_data(
                action="compress-overlay", label="output", key="file"
            )
            nfs_address = self.parameters["persistent_nfs"].get("address")
            if overlay_file:
                self.logger.info(
                    "[%s] Applying overlay to persistent NFS address %s",
                    namespace,
                    nfs_address,
                )
            # need to mount the persistent NFS here.
            # We can't use self.mkdtemp() here because this directory should
            # not be removed if umount fails.
            directory = mkdtemp(autoremove=False)
            self.run_cmd(["mount", "-t", "nfs", nfs_address, directory])
        elif self.parameters.get("ramdisk") is not None:
            if not self.parameters["ramdisk"].get("install_overlay", True):
                self.logger.info("[%s] Skipping applying overlay to ramdisk", namespace)
                return connection
            overlay_file = self.get_namespace_data(
                action="compress-overlay", label="output", key="file"
            )
            directory = self.get_namespace_data(
                action="extract-overlay-ramdisk",
                label="extracted_ramdisk",
                key="directory",
            )
            if overlay_file:
                self.logger.info(
                    "[%s] Applying overlay %s to ramdisk", namespace, overlay_file
                )
        elif self.parameters.get("rootfs") is not None:
            overlay_file = self.get_namespace_data(
                action="compress-overlay", label="output", key="file"
            )
            directory = self.get_namespace_data(
                action="apply-overlay", label="file", key="root"
            )
        else:
            self.logger.debug("[%s] No overlay directory", namespace)
        if self.parameters.get("os") == "centos_installer":
            # centos installer ramdisk doesn't like having anything other
            # than the kickstart config being inserted. Instead, make the
            # overlay accessible through tftp. Yuck.
            tftp_dir = os.path.dirname(
                self.get_namespace_data(
                    action="download-action", label="ramdisk", key="file"
                )
            )
            shutil.copy(overlay_file, tftp_dir)
            suffix = self.get_namespace_data(
                action="tftp-deploy", label="tftp", key="suffix"
            )
            if not suffix:
                suffix = ""
            self.set_namespace_data(
                action=self.name,
                label="file",
                key="overlay",
                value=os.path.join(suffix, "ramdisk", os.path.basename(overlay_file)),
            )
        if overlay_file:
            self.logger.debug(
                "[%s] Applying overlay %s to directory %s",
                namespace,
                overlay_file,
                directory,
            )
            untar_file(overlay_file, directory)
            if nfs_address:
                self.run_cmd(["umount", directory])
                os.rmdir(directory)  # fails if the umount fails
        return connection


class ExtractRootfs(Action):
    """
    Unpacks the rootfs and applies the overlay to it
    """

    name = "extract-rootfs"
    description = "unpack rootfs"
    summary = "unpack rootfs, ready to apply lava overlay"
    timeout_exception = InfrastructureError

    def __init__(self):
        super().__init__()
        self.param_key = "rootfs"
        self.file_key = "root"
        self.extra_compression = ["xz"]
        self.use_tarfile = True
        self.use_lzma = False

    def run(self, connection, max_end_time):
        if not self.parameters.get(self.param_key):  # idempotency
            return connection
        connection = super().run(connection, max_end_time)
        root = self.get_namespace_data(
            action="download-action", label=self.param_key, key="file"
        )
        root_dir = self.mkdtemp()
        untar_file(root, root_dir)
        self.set_namespace_data(
            action="extract-rootfs", label="file", key=self.file_key, value=root_dir
        )
        self.logger.debug("Extracted %s to %s", self.file_key, root_dir)
        return connection


class ExtractNfsRootfs(ExtractRootfs):
    """
    Unpacks the nfsrootfs and applies the overlay to it
    """

    name = "extract-nfsrootfs"
    description = "unpack nfsrootfs"
    summary = "unpack nfsrootfs, ready to apply lava overlay"
    timeout_exception = InfrastructureError

    def __init__(self):
        super().__init__()
        self.param_key = "nfsrootfs"
        self.file_key = "nfsroot"

    def validate(self):
        super().validate()
        if not self.parameters.get(self.param_key):  # idempotency
            return
        if not self.get_namespace_data(
            action="download-action", label=self.param_key, key="file"
        ):
            self.errors = "no file specified extract as %s" % self.param_key
        if "prefix" in self.parameters[self.param_key]:
            prefix = self.parameters[self.param_key]["prefix"]
            if prefix.startswith("/"):
                self.errors = "prefix must not be an absolute path"
            if not prefix.endswith("/"):
                self.errors = "prefix must be a directory and end with /"

    def run(self, connection, max_end_time):
        if not self.parameters.get(self.param_key):  # idempotency
            return connection
        connection = super().run(connection, max_end_time)

        if "prefix" in self.parameters[self.param_key]:
            prefix = self.parameters[self.param_key]["prefix"]
            self.logger.warning(
                "Adding '%s' prefix, any other content will not be visible.", prefix
            )

            # Grab the path already defined in super().run() and add the prefix
            root_dir = self.get_namespace_data(
                action="extract-rootfs", label="file", key=self.file_key
            )
            root_dir = os.path.join(root_dir, prefix)
            # sets the directory into which the overlay is unpacked and which
            # is used in the substitutions into the bootloader command string.
            self.set_namespace_data(
                action="extract-rootfs", label="file", key=self.file_key, value=root_dir
            )

        self.job.device["dynamic_data"]["NFS_ROOTFS"] = self.get_namespace_data(
            action="extract-rootfs", label="file", key=self.file_key
        )
        self.job.device["dynamic_data"]["NFS_SERVER_IP"] = dispatcher_ip(
            self.job.parameters["dispatcher"], "nfs"
        )

        return connection


class ExtractModules(Action):
    """
    If modules are specified in the deploy parameters, unpack the modules
    whilst the nfsrootfs or ramdisk are unpacked.
    """

    name = "extract-modules"
    description = "extract supplied kernel modules"
    summary = "extract kernel modules"
    timeout_exception = InfrastructureError

    def run(self, connection, max_end_time):
        if not self.parameters.get("modules"):  # idempotency
            return connection
        connection = super().run(connection, max_end_time)
        modules = self.get_namespace_data(
            action="download-action", label="modules", key="file"
        )
        if not self.parameters.get("ramdisk"):
            if not self.parameters.get("nfsrootfs"):
                raise JobError("Unable to identify a location for the unpacked modules")

        # if both NFS and ramdisk are specified, apply modules to both
        # as the kernel may need some modules to raise the network and
        # will need other modules to support operations within the NFS
        if self.parameters.get("nfsrootfs"):
            if not self.parameters["nfsrootfs"].get("install_modules", True):
                self.logger.info("Skipping applying overlay to NFS")
            else:
                root = self.get_namespace_data(
                    action="extract-rootfs", label="file", key="nfsroot"
                )
                self.logger.info("extracting modules file %s to %s", modules, root)
                untar_file(modules, root)
        if self.parameters.get("ramdisk"):
            if not self.parameters["ramdisk"].get("install_modules", True):
                self.logger.info("Not adding modules to the ramdisk.")
            else:
                root = self.get_namespace_data(
                    action="extract-overlay-ramdisk",
                    label="extracted_ramdisk",
                    key="directory",
                )
                self.logger.info("extracting modules file %s to %s", modules, root)
                untar_file(modules, root)
        return connection


class ExtractRamdisk(Action):
    """
    Removes the uboot header, if kernel-type is uboot
    unzips the ramdisk and uncompresses the contents,
    applies the overlay and then leaves the ramdisk open
    for other actions to modify. Needs CompressRamdisk to
    recreate the ramdisk with modifications.
    """

    name = "extract-overlay-ramdisk"
    description = "extract ramdisk to a temporary directory"
    summary = "extract the ramdisk"
    timeout_exception = InfrastructureError

    def __init__(self):
        super().__init__()
        self.skip = False

    def validate(self):
        super().validate()
        if not self.parameters.get("ramdisk"):  # idempotency
            return
        if not self.parameters["ramdisk"].get(
            "install_modules", True
        ) and not self.parameters["ramdisk"].get("install_overlay", True):
            self.skip = True

    def run(self, connection, max_end_time):
        if not self.parameters.get("ramdisk"):  # idempotency
            return connection
        ramdisk = self.get_namespace_data(
            action="download-action", label="ramdisk", key="file"
        )
        if self.skip:
            self.logger.info("Not extracting ramdisk.")
            suffix = self.get_namespace_data(
                action="tftp-deploy", label="tftp", key="suffix"
            )
            filename = os.path.join(suffix, "ramdisk", os.path.basename(ramdisk))
            # declare the original ramdisk as the name to be used later.
            self.set_namespace_data(
                action="compress-ramdisk", label="file", key="ramdisk", value=filename
            )
            return connection
        connection = super().run(connection, max_end_time)
        ramdisk_dir = self.mkdtemp()
        extracted_ramdisk = os.path.join(ramdisk_dir, "ramdisk")
        os.mkdir(extracted_ramdisk, 0o755)
        compression = self.parameters["ramdisk"].get("compression")
        suffix = ""
        if compression:
            suffix = ".%s" % compression
        ramdisk_compressed_data = os.path.join(ramdisk_dir, RAMDISK_FNAME + suffix)
        if self.parameters["ramdisk"].get("header") == "u-boot":
            cmd = (
                "dd if=%s of=%s ibs=%s skip=1"
                % (ramdisk, ramdisk_compressed_data, UBOOT_DEFAULT_HEADER_LENGTH)
            ).split(" ")
            try:
                self.run_command(cmd)
            except Exception:
                raise LAVABug("Unable to remove uboot header: %s" % ramdisk)
        else:
            # give the file a predictable name
            shutil.move(ramdisk, ramdisk_compressed_data)
        ramdisk_data = decompress_file(ramdisk_compressed_data, compression)
        uncpio(ramdisk_data, extracted_ramdisk)

        # tell other actions where the unpacked ramdisk can be found
        self.set_namespace_data(
            action=self.name,
            label="extracted_ramdisk",
            key="directory",
            value=extracted_ramdisk,
        )
        self.set_namespace_data(
            action=self.name, label="ramdisk_file", key="file", value=ramdisk_data
        )
        return connection


class CompressRamdisk(Action):
    """
    recreate ramdisk, with overlay in place
    """

    name = "compress-ramdisk"
    description = "recreate a ramdisk with the overlay applied."
    summary = "compress ramdisk with overlay"
    timeout_exception = InfrastructureError

    def __init__(self):
        super().__init__()
        self.mkimage_arch = None
        self.add_header = None
        self.skip = False

    def validate(self):
        super().validate()
        if not self.parameters.get("ramdisk"):  # idempotency
            return
        if not self.parameters["ramdisk"].get(
            "install_modules", True
        ) and not self.parameters["ramdisk"].get("install_overlay", True):
            self.skip = True
            return
        if "parameters" in self.job.device["actions"]["deploy"]:
            self.add_header = self.job.device["actions"]["deploy"]["parameters"].get(
                "add_header"
            )
            if self.add_header is not None:
                if self.add_header == "u-boot":
                    which("mkimage")
                    if (
                        "mkimage_arch"
                        not in self.job.device["actions"]["deploy"]["parameters"]
                    ):
                        self.errors = "Missing architecture for uboot mkimage support (mkimage_arch in deploy parameters)"
                        return
                    self.mkimage_arch = self.job.device["actions"]["deploy"][
                        "parameters"
                    ]["mkimage_arch"]
                else:
                    self.errors = "ramdisk: add_header: unknown header type"

    def run(self, connection, max_end_time):
        if not self.parameters.get("ramdisk"):  # idempotency
            return connection
        if self.skip:
            return connection
        connection = super().run(connection, max_end_time)
        ramdisk_dir = self.get_namespace_data(
            action="extract-overlay-ramdisk", label="extracted_ramdisk", key="directory"
        )
        ramdisk_data = self.get_namespace_data(
            action="extract-overlay-ramdisk", label="ramdisk_file", key="file"
        )
        if not ramdisk_dir:
            raise LAVABug("Unable to find unpacked ramdisk")
        if not ramdisk_data:
            raise LAVABug("Unable to find ramdisk directory")
        if self.parameters.get("preseed"):
            if self.parameters["deployment_data"].get("preseed_to_ramdisk"):
                # download action must have completed to get this far
                # some installers (centos) cannot fetch the preseed file via tftp.
                # Instead, put the preseed file into the ramdisk using a given name
                # from deployment_data which we can use in the boot commands.
                filename = self.parameters["deployment_data"]["preseed_to_ramdisk"]
                self.logger.info("Copying preseed file into ramdisk: %s", filename)
                shutil.copy(
                    self.get_namespace_data(
                        action="download-action", label="preseed", key="file"
                    ),
                    os.path.join(ramdisk_dir, filename),
                )
                self.set_namespace_data(
                    action=self.name, label="file", key="preseed_local", value=filename
                )

        self.logger.info("Building ramdisk %s containing %s", ramdisk_data, ramdisk_dir)
        self.logger.debug(">> %s", cpio(ramdisk_dir, ramdisk_data))

        # we need to compress the ramdisk with the same method is was submitted with
        compression = self.parameters["ramdisk"].get("compression")
        final_file = compress_file(ramdisk_data, compression)

        tftp_dir = os.path.dirname(
            self.get_namespace_data(
                action="download-action", label="ramdisk", key="file"
            )
        )

        if self.add_header == "u-boot":
            ramdisk_uboot = final_file + ".uboot"
            self.logger.debug("Adding RAMdisk u-boot header.")
            cmd = (
                "mkimage -A %s -T ramdisk -C none -d %s %s"
                % (self.mkimage_arch, final_file, ramdisk_uboot)
            ).split(" ")
            if not self.run_command(cmd):
                raise InfrastructureError("Unable to add uboot header to ramdisk")
            final_file = ramdisk_uboot

        full_path = os.path.join(tftp_dir, os.path.basename(final_file))
        shutil.move(final_file, full_path)
        self.logger.debug("rename %s to %s", final_file, full_path)
        self.set_namespace_data(
            action=self.name, label="file", key="full-path", value=full_path
        )

        if self.parameters["to"] == "tftp":
            suffix = self.get_namespace_data(
                action="tftp-deploy", label="tftp", key="suffix"
            )
            if not suffix:
                suffix = ""
            self.set_namespace_data(
                action=self.name,
                label="file",
                key="ramdisk",
                value=os.path.join(suffix, "ramdisk", os.path.basename(final_file)),
            )
        else:
            self.set_namespace_data(
                action=self.name, label="file", key="ramdisk", value=final_file
            )
        return connection


class ApplyLxcOverlay(Action):
    name = "apply-lxc-overlay"
    description = "apply the overlay to the container by copying"
    summary = "apply overlay on the container"
    timeout_exception = InfrastructureError

    def __init__(self):
        super().__init__()
        self.lava_test_dir = os.path.realpath(
            "%s/../../lava_test_shell" % os.path.dirname(__file__)
        )
        self.scripts_to_copy = ["lava-test-runner"]

    def validate(self):
        super().validate()
        which("tar")
        if not os.path.exists(self.lava_test_dir):
            self.errors = "Missing lava-test-runner: %s" % self.lava_test_dir

    def run(self, connection, max_end_time):
        connection = super().run(connection, max_end_time)
        overlay_file = self.get_namespace_data(
            action="compress-overlay", label="output", key="file"
        )
        if overlay_file is None:
            self.logger.debug("skipped %s", self.name)
            return connection
        lxc_name = self.get_namespace_data(
            action="lxc-create-action", label="lxc", key="name"
        )
        lxc_default_path = lxc_path(self.job.parameters["dispatcher"])
        lxc_rootfs_path = os.path.join(lxc_default_path, lxc_name, "rootfs")
        if not os.path.exists(lxc_rootfs_path):
            raise LAVABug("Lxc container rootfs not found")
        tar_cmd = [
            "tar",
            "--warning",
            "no-timestamp",
            "-C",
            lxc_rootfs_path,
            "-xaf",
            overlay_file,
        ]
        command_output = self.run_command(tar_cmd)
        if command_output and command_output != "":
            raise JobError("Unable to untar overlay: %s" % command_output)

        # FIXME: Avoid copying this special 'lava-test-runner' which does not
        #        have 'sync' in cleanup. This should be handled during the
        #        creation of the overlay instead. Make a special case to copy
        #        lxc specific scripts, with distro specific versions.
        fname = os.path.join(self.lava_test_dir, "lava-test-runner")
        output_file = "%s/bin/%s" % (lxc_rootfs_path, os.path.basename(fname))
        self.logger.debug("Copying %s", output_file)
        try:
            shutil.copy(fname, output_file)
        except OSError:
            raise InfrastructureError("Unable to copy: %s" % output_file)

        return connection


class ConfigurePreseedFile(Action):
    name = "configure-preseed-file"
    description = "add commands to automated installers, to copy the lava test overlay to the installed system"
    summary = "add commands to installer config"
    timeout_exception = InfrastructureError

    def run(self, connection, max_end_time):
        if "deployment_data" not in self.parameters:
            return connection
        if self.parameters["deployment_data"].get("installer_extra_cmd"):
            if self.parameters.get("os") == "debian_installer":
                add_late_command(
                    self.get_namespace_data(
                        action="download-action", label="preseed", key="file"
                    ),
                    self.parameters["deployment_data"]["installer_extra_cmd"],
                )
            if self.parameters.get("os") == "centos_installer":
                ip_addr = dispatcher_ip(self.job.parameters["dispatcher"], "tftp")
                overlay = self.get_namespace_data(
                    action="download-action", label="file", key="overlay"
                )
                substitutions = {"{OVERLAY_URL}": "tftp://" + ip_addr + "/" + overlay}
                post_command = substitute(
                    [self.parameters["deployment_data"]["installer_extra_cmd"]],
                    substitutions,
                )
                add_to_kickstart(
                    self.get_namespace_data(
                        action="download-action", label="preseed", key="file"
                    ),
                    post_command[0],
                )
        return connection


class AppendOverlays(Action):
    name = "append-overlays"
    description = "append overlays to an image"
    summary = "append overlays to an image"

    # TODO: list libguestfs supported formats
    IMAGE_FORMATS = ["cpio.newc", "ext4", "tar"]
    OVERLAY_FORMATS = ["file", "tar"]

    def __init__(self, key, params):
        super().__init__()
        self.key = key
        self.params = params

    def validate(self):
        super().validate()
        # Check that we have "overlays" dict
        if "overlays" not in self.params:
            raise JobError("Missing 'overlays' dictionary")
        if not isinstance(self.params["overlays"], dict):
            raise JobError("'overlays' is not a dictionary")
        for overlay, params in self.params["overlays"].items():
            if overlay == "lava":
                self.set_namespace_data(
                    action=self.name, label="guest", key="applied", value=True
                )
                continue
            if params.get("format") not in self.OVERLAY_FORMATS:
                raise JobError(
                    "Invalid 'format' (%r) for 'overlays.%s'"
                    % (params.get("format", ""), overlay)
                )
            path = params.get("path")
            if path is None:
                raise JobError("Missing 'path' for 'overlays.%s'" % overlay)
            if not path.startswith("/") or ".." in path:
                raise JobError("Invalid 'path': %r" % path)

        # Check the image format
        if self.params.get("format") not in self.IMAGE_FORMATS:
            raise JobError("Unsupported image format %r" % self.params.get("format"))

        if self.params.get("sparse") and self.params.get("format") != "ext4":
            raise JobError("sparse=True is only available for ext4 images")

    def run(self, connection, max_end_time):
        connection = super().run(connection, max_end_time)
        if self.params["format"] == "cpio.newc":
            self.update_cpio()
        elif self.params["format"] == "ext4":
            try:
                self.update_guestfs()
            except RuntimeError as exc:
                self.logger.exception(str(exc))
                raise JobError("Unable to update image %s: %r" % (self.key, str(exc)))
        elif self.params["format"] == "tar":
            self.update_tar()
        else:
            raise LAVABug("Unknown format %r" % self.params["format"])
        return connection

    def _update(self, f_uncompress, f_compress):
        image = self.get_namespace_data(
            action="download-action", label=self.key, key="file"
        )
        compression = self.get_namespace_data(
            action="download-action", label=self.key, key="compression"
        )
        decompressed = self.get_namespace_data(
            action="download-action", label=self.key, key="decompressed"
        )
        self.logger.info("Modifying %r", image)
        tempdir = self.mkdtemp()
        # Some images are kept compressed. We should decompress first
        if compression and not decompressed:
            self.logger.debug("* decompressing (%s)", compression)
            image = decompress_file(image, compression)
        # extract the archive
        self.logger.debug("* extracting %r", image)
        f_uncompress(image, tempdir)
        os.unlink(image)

        # Add overlays
        self.logger.debug("Overlays:")
        for overlay in self.params["overlays"]:
            label = "%s.%s" % (self.key, overlay)
            overlay_image = None
            path = None
            if overlay == "lava":
                overlay_image = self.get_namespace_data(
                    action="compress-overlay", label="output", key="file"
                )
                path = "/"
            else:
                overlay_image = self.get_namespace_data(
                    action="download-action", label=label, key="file"
                )
                path = self.params["overlays"][overlay]["path"]
            # Take off initial "/" from path, extract relative to this directory
            extract_path = os.path.join(tempdir, path[1:])
            if overlay == "lava" or self.params["overlays"][overlay]["format"] == "tar":
                self.logger.debug(
                    "- %s: untar %r to %r", label, overlay_image, extract_path
                )
                # In the "validate" function, we check that path startswith '/'
                # and does not contains '..'
                untar_file(overlay_image, extract_path)
            else:
                self.logger.debug(
                    "- %s: cp %r to %r", label, overlay_image, extract_path
                )
                shutil.copy(overlay_image, extract_path)

        # Recreating the archive
        self.logger.debug("* archiving %r", image)
        f_compress(tempdir, image)
        if compression and not decompressed:
            self.logger.debug("* compressing (%s)", compression)
            image = compress_file(image, compression)

    def update_cpio(self):
        self._update(uncpio, cpio)

    def update_tar(self):
        self._update(untar_file, partial(create_tarfile, arcname="."))

    def update_guestfs(self):
        image = self.get_namespace_data(
            action="download-action", label=self.key, key="file"
        )
        partition = self.params.get("partition", None)
        self.logger.info("Modifying %r", image)

        if self.params.get("sparse", False):
            self.logger.debug("Calling simg2img on %r", image)
            command_list = ["/usr/bin/simg2img", image, f"{image}.non-sparse"]
            self.run_cmd(command_list, error_msg="simg2img failed for %s" % image)
            os.replace(f"{image}.non-sparse", image)

        guest = guestfs.GuestFS(python_return_dict=True)
        guest.add_drive(image)
        try:
            guest.launch()
            if partition is not None:
                device = guest.list_partitions()[partition]
            else:
                device = guest.list_devices()[0]
            guest.mount(device, "/")
        except RuntimeError as exc:
            self.logger.exception(str(exc))
            raise JobError("Unable to update image %s: %r" % (self.key, str(exc)))

        self.logger.debug("Overlays:")
        for overlay in self.params["overlays"]:
            label = "%s.%s" % (self.key, overlay)
            overlay_image = None
            if overlay == "lava":
                overlay_image = self.get_namespace_data(
                    action="compress-overlay", label="output", key="file"
                )
                lava_test_results_dir = self.get_namespace_data(
                    action="test", label="results", key="lava_test_results_dir"
                )
                path = os.path.dirname(lava_test_results_dir or "/")
                compress = "gzip"
            else:
                overlay_image = self.get_namespace_data(
                    action="download-action", label=label, key="file"
                )
                path = self.params["overlays"][overlay]["path"]
                compress = None
            if overlay_image:
                self.logger.debug("- %s: %r to %r", label, overlay_image, path)
                if (
                    overlay == "lava"
                    or self.params["overlays"][overlay]["format"] == "tar"
                ):
                    guest.mkdir_p(path)
                    guest.tar_in(overlay_image, path, compress=compress)
                else:
                    guest.mkdir_p(os.path.dirname(path))
                    guest.upload(overlay_image, path)
            else:
                self.logger.warning("- %s: <MISSING> to %r", label, path)
        guest.umount(device)
        guest.shutdown()

        if self.params.get("sparse", False):
            self.logger.debug("Calling img2simg on %r", image)
            command_list = ["/usr/bin/img2simg", image, f"{image}.sparse"]
            self.run_cmd(command_list, error_msg="img2simg failed for %s" % image)
            os.replace(f"{image}.sparse", image)
