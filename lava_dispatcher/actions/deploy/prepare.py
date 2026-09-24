# Copyright (C) 2017 Linaro Limited
#
# Author: Matthew Hart <matthew.hart@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

import os
from typing import TYPE_CHECKING

from lava_common.exceptions import InfrastructureError, JobError
from lava_dispatcher.action import Action, Pipeline
from lava_dispatcher.utils.shell import which
from lava_dispatcher.utils.strings import map_kernel_uboot

if TYPE_CHECKING:
    from typing import Any

    from lava_dispatcher.job import Job
    from lava_dispatcher.shell import ShellSession


class PrepareKernelAction(Action):
    """
    Populate the pipeline with a kernel conversion action, if needed
    """

    name = "prepare-kernel"
    description = "populates the pipeline with a kernel conversion action"
    summary = "add a kernel conversion"

    def populate(self, parameters: dict[str, Any]) -> None:
        self.pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        # the logic here can be upgraded in future if needed with more parameters to the deploy.
        methods = self.job.device["actions"]["boot"]["methods"]
        if "u-boot" in methods:
            self.pipeline.add_action(UBootPrepareKernelAction(self.job))
        elif "depthcharge" in methods:
            self.pipeline.add_action(PrepareFITAction(self.job))


class UBootPrepareKernelAction(Action):
    """
    Convert kernels to uImage
    """

    name = "uboot-prepare-kernel"
    description = "convert kernel to uimage"
    summary = "prepare/convert kernel"

    def __init__(self, job: Job):
        super().__init__(job)
        self.bootcommand: str | None = None
        self.params: dict[str, Any] = {}
        self.kernel_type: str | None = None
        self.mkimage_conversion = False

    def append_dtb(self, kernel_file: str, dtb_file: str, dest_file: str) -> None:
        self.logger.info("Appending %s to %s", dtb_file, kernel_file)
        # Can't use cat here because it will be called with subprocess.check_output that catches stdout
        cmd: list[str] = ["dd", "if=%s" % kernel_file, "of=%s" % dest_file]
        cmd2: list[str] = [
            "dd",
            "if=%s" % dtb_file,
            "of=%s" % dest_file,
            "oflag=append",
            "conv=notrunc",
        ]
        if not self.run_command(cmd):
            raise InfrastructureError("DTB appending failed")
        if not self.run_command(cmd2):
            raise InfrastructureError("DTB appending failed")

    def create_uimage(
        self, kernel: str, load_addr: str, xip: bool, arch: str, output: str
    ) -> str:
        load_addr_int = int(load_addr, 16)
        uimage_path = f"{os.path.dirname(kernel)}/{output}"
        if xip:
            entry_addr = load_addr_int + 64
        else:
            entry_addr = load_addr_int
        cmd = f"mkimage -A {arch} -O linux -T kernel -C none -a 0x{load_addr_int:x} -e 0x{entry_addr:x} -d {kernel} {uimage_path}"
        if self.run_command(cmd.split(" ")):
            return uimage_path
        else:
            raise InfrastructureError("uImage creation failed")

    def validate(self) -> None:
        super().validate()
        if "parameters" not in self.job.device["actions"]["deploy"]:
            return
        self.params = self.job.device["actions"]["deploy"]["parameters"]
        self.kernel_type = self.get_namespace_data(
            action="download-action", label="type", key="kernel"
        )
        self.bootcommand = None
        if "parameters" not in self.job.device:
            if self.kernel_type:
                self.errors_add("Kernel boot type is not supported by this device.")
        if self.kernel_type:
            self.set_namespace_data(
                action=self.name, label="prepared-kernel", key="exists", value=True
            )
            self.bootcommand = map_kernel_uboot(
                self, self.kernel_type, self.job.device.get("parameters")
            )
            self.kernel_type = str(self.kernel_type).lower()
            if self.bootcommand not in self.job.device["parameters"]:
                self.errors_add(
                    "Requested kernel boot type '%s' is not supported by this device."
                    % self.bootcommand
                )
            if self.kernel_type in ["bootm", "bootz", "booti"]:
                self.errors_add(
                    "booti, bootm and bootz are deprecated, please use 'image', 'uimage' or 'zimage'"
                )
            which("mkimage")
            if "mkimage_arch" not in self.params:
                self.errors_add(
                    "Missing architecture for uboot mkimage support (mkimage_arch in u-boot parameters)"
                )
            if self.bootcommand == "bootm" and self.kernel_type != "uimage":
                self.mkimage_conversion = True
        self.set_namespace_data(
            action="uboot-prepare-kernel",
            label="bootcommand",
            key="bootcommand",
            value=self.bootcommand,
        )

    def run(
        self, connection: ShellSession | None, max_end_time: float | None
    ) -> ShellSession | None:
        connection = super().run(connection, max_end_time)
        if not self.kernel_type:
            return connection  # idempotency
        old_kernel: str | None = self.get_namespace_data(
            action="download-action", label="file", key="kernel"
        )
        if self.params.get("append_dtb", False):
            if old_kernel is None:
                raise JobError("Kernel not downloaded")
            kernel_file: str | None = self.get_namespace_data(
                action="download-action", label="kernel", key="file"
            )
            if kernel_file is None:
                raise JobError("Kernel not downloaded")
            dtb_file: str | None = self.get_namespace_data(
                action="download-action", label="dtb", key="file"
            )
            if dtb_file is None:
                raise JobError("DTB not downloaded")
            kerneldtb_file = os.path.join(os.path.dirname(kernel_file), "kernel-dtb")
            self.append_dtb(kernel_file, dtb_file, kerneldtb_file)
            new_kernel = os.path.join(os.path.dirname(old_kernel), "kernel-dtb")
            self.set_namespace_data(
                action="download-action",
                label="kernel",
                key="file",
                value=kerneldtb_file,
            )
            self.set_namespace_data(
                action="prepare-kernel", label="file", key="kernel", value=new_kernel
            )
        if self.mkimage_conversion:
            self.logger.info("Converting downloaded kernel to a uImage")
            if old_kernel is None:
                raise JobError("Kernel not downloaded")
            filename: str | None = self.get_namespace_data(
                action="download-action", label="kernel", key="file"
            )
            if filename is None:
                raise JobError("uImage source kernel not found")
            load_addr = self.job.device["parameters"][self.bootcommand]["kernel"]
            if "text_offset" in self.job.device["parameters"]:
                load_addr = self.job.device["parameters"]["text_offset"]
            arch = self.params["mkimage_arch"]
            use_xip = self.params.get("use_xip", False)
            if use_xip:
                self.logger.debug("Using xip")
            self.create_uimage(filename, load_addr, use_xip, arch, "uImage")
            new_kernel = os.path.dirname(old_kernel) + "/uImage"
            # overwriting namespace data
            self.set_namespace_data(
                action="prepare-kernel", label="file", key="kernel", value=new_kernel
            )
        return connection


class PrepareFITAction(Action):
    """
    Package kernel, dtb and ramdisk into an FIT image
    """

    name = "prepare-fit"
    description = "package kernel, dtb and ramdisk into an FIT image"
    summary = "generate depthcharge FIT image"

    def __init__(self, job: Job):
        super().__init__(job)
        self.deploy_params: dict[str, Any] = {}
        self.device_params: dict[str, Any] = {}

    def validate(self) -> None:
        super().validate()
        which("mkimage")

        self.deploy_params = self.job.device["actions"]["deploy"].get("parameters", {})

        device_params = self.job.device.get("parameters")
        if device_params is None:
            self.errors_add("Missing device parameters")
        elif "load_address" not in device_params:
            self.errors_add("Missing load_address from device parameters")
        else:
            self.device_params = device_params

    def _make_mkimage_command(
        self,
        arch: str,
        kernel: str,
        load_addr: str,
        fit_path: str,
        compression: str | None = None,
        dtb: str | None = None,
        ramdisk: str | None = None,
    ) -> list[str]:
        cmd: list[str] = [
            "mkimage",
            "-D",
            '"-I dts -O dtb -p 2048"',
            "-f",
            "auto",
            "-A",
            arch,
            "-O",
            "linux",
            "-T",
            "kernel",
            "-C",
            compression or "none",
            "-d",
            kernel,
            "-a",
            load_addr,
        ]
        if dtb:
            cmd += ["-b", dtb]
        if ramdisk:
            cmd += ["-i", ramdisk]
        cmd.append(fit_path)
        return cmd

    def run(
        self, connection: ShellSession | None, max_end_time: float | None
    ) -> ShellSession | None:
        connection = super().run(connection, max_end_time)

        arch = self.deploy_params.get("mkimage_arch")
        if not arch:
            self.logger.info("No mkimage arch provided, not using FIT.")
            return connection

        kernel_path = self.get_namespace_data(
            action="download-action", label="kernel", key="file"
        )
        if kernel_path is None:
            raise JobError("Kernel not downloaded")
        kernel_dir, kernel_image = os.path.split(kernel_path)
        dtb: str | None = self.get_namespace_data(
            action="download-action", label="dtb", key="file"
        )
        ramdisk: str | None = self.get_namespace_data(
            action="download-action", label="ramdisk", key="file"
        )
        compression: str | None = None

        if arch == "arm64":
            lzma_kernel = os.path.join(kernel_dir, ".".join([kernel_image, "lzma"]))
            self.run_cmd(["lzma", "--keep", kernel_path])
            kernel_path = lzma_kernel
            compression = "lzma"

        fit_path = os.path.join(kernel_dir, "image.itb")
        load_addr = self.device_params["load_address"]
        ramdisk_with_overlay: str | None = self.get_namespace_data(
            action="compress-ramdisk", label="file", key="full-path"
        )
        if ramdisk_with_overlay:
            ramdisk = ramdisk_with_overlay

        cmd = self._make_mkimage_command(
            arch=arch,
            compression=compression,
            kernel=kernel_path,
            load_addr=load_addr,
            dtb=dtb,
            ramdisk=ramdisk,
            fit_path=fit_path,
        )
        if not self.run_command(cmd):
            raise InfrastructureError("FIT image creation failed")

        kernel_tftp: str | None = self.get_namespace_data(
            action="download-action", label="file", key="kernel"
        )
        if kernel_tftp is None:
            raise JobError("Kernel not downloaded")
        fit_tftp = os.path.join(os.path.dirname(kernel_tftp), "image.itb")
        self.set_namespace_data(
            action=self.name, label="file", key="fit", value=fit_tftp
        )

        return connection
