# Copyright (C) 2025 Collabora Limited
#
# Author: Igor Ponomarev <igor.ponomarev@collabora.com>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .connection import Connection


@dataclass
class DownloadedFile:
    file: str
    compression: str | None = None
    decompressed: bool = False
    overlay: bool = False
    type: str | None = None
    sha256: str | None = None
    image_arg: str | None = None


class DownloadsDict(dict[str, DownloadedFile]):
    def maybe_file(self, download_name: str) -> str | None:
        if download_data := self.get(download_name):
            return download_data.file
        else:
            return None

    def create_downloaded_file(
        self, *, download_name: str, download_file: str
    ) -> DownloadedFile:
        if download_name in self:
            raise ValueError(f"Download {download_name} already exists")

        new_download = DownloadedFile(file=download_file)
        self[download_name] = new_download
        return new_download


@dataclass
class CompressedRamdisk:
    ramdisk_file: str | None = None
    preseed_local_file: str | None = None
    full_path: str | None = None


@dataclass
class DeviceEnv:
    line_separator: str | None = None
    shell_file: str | None = None
    env_dict: dict[str, str] = field(default_factory=dict)


@dataclass
class Nbd:
    nbd_server_ip: str | None = None
    nbd_server_port: str | None = None
    initrd: bool = False


@dataclass
class Uboot:
    bootcommand: str = ""
    kernel_type: str = ""
    boot_part_uuid: str | None = None
    bootloader_prompt: str | None = None
    prepared_kernel_exists: bool = False


@dataclass
class PreparedKernel:
    kernel_file: str | None = None


@dataclass
class Tftp:
    ramdisk: bool = False
    tftp_dir: str | None = None
    suffix: str | None = None


@dataclass
class PersistentNfs:
    nfsroot: str | None = None
    serverip: str | None = None


@dataclass
class ExtractNfs:
    nfsroot: str | None = None


@dataclass
class BootloaderFromMedia:
    root: str | None = None
    boot_part: str | None = None


@dataclass
class Bootloader:
    substitutions: dict[str, str | None] = field(default_factory=dict)
    commands: list[str] = field(default_factory=list)


@dataclass
class CompressedOverlay:
    file: str | None = None


@dataclass
class Test:
    __test__: bool = False
    location: str | None = None
    lava_test_sh_cmd: str | None = None
    lava_test_results_dir: str | None = None
    pre_command_list: list[str] = field(default_factory=list)
    overlay_dir: str | None = None
    entries: dict[str, TestEntry] = field(default_factory=dict)
    output: str | None = None
    test_list: list[Any] = field(default_factory=list)
    testdef_index: list[str] = field(default_factory=list)
    testdef_levels: dict[int, str] = field(default_factory=dict)
    pattern_dictionary: dict[str, Any] = field(default_factory=dict)


@dataclass
class TestEntry:
    __test__: bool = False
    repository: str | None = None
    path: str | None = None
    revision: str = "unspecified"
    runner_path: str | None = None
    overlay_path: str | None = None
    commit_id: str | None = None
    testdef_metadata: dict[str, Any] = field(default_factory=dict)
    testdef_pattern: dict[str, Any] | None = None


@dataclass
class Interrupt:
    at_bootloader_prompt: bool = False


@dataclass
class Shared:
    connection: Connection | None = None
    nodebooter_container: str | None = None


@dataclass
class Avh:
    config: dict[str, object] = field(default_factory=dict)


@dataclass
class Barebox:
    bootloader_prompt: str | None = None


@dataclass
class PrepareFit:
    fit_file: str | None = None


@dataclass
class Docker:
    image_name: str | None = None


@dataclass
class Fvp:
    serial_port: str | None = None
    feedback_ports: list[dict[str, str | None]] = field(default_factory=list)
    container: str | None = None


@dataclass
class Ipxe:
    bootloader_prompt: str | None = None


@dataclass
class PrepareEmptyImage:
    output: str | None = None


@dataclass
class PrepareQemuCommands:
    sub_command: list[str] = field(default_factory=list)
    append: str | None = None
    prompts: str | None = None


@dataclass
class OverlayGuest:
    name: str | None = None
    filename: str | None = None
    uuid: str | None = None


@dataclass
class OverlayAppend:
    applied: bool = False


@dataclass
class Jlink:
    script_path: str | None = None
    cmd: list[str] = field(default_factory=list)


@dataclass
class Lxc:
    name: str | None = None


@dataclass
class DeployImages:
    uefi_dir: str | None = None


@dataclass
class ExtractRootfs:
    nfsroot: str | None = None
    root_dir: str | None = None


@dataclass
class Ssh:
    tar_flags: str = ""
    scp_items: dict[str, bool] = field(default_factory=dict)
    scp_env: dict[str, str] = field(default_factory=dict)
    overlay_file: str | None = None
    host_keys: dict[str, str | None] = field(default_factory=dict)
    overlay_destination: str | None = None
    is_host: bool = False
    host_address: str | None = None
    identity_file: str | None = None


@dataclass
class StorageDeploy:
    uboot_device: str | None = None


@dataclass
class Uefi:
    bootloader_prompt: str | None = None


@dataclass
class UefiMenu:
    bootloader_prompt: str | None = None


@dataclass
class Uuu:
    otg_availability_check: bool = False
    bootloader_valid_check: bool = False
    bootloader_prompt: str | None = None
    uuu_images: list[str] = field(default_factory=list)
    root_location: str | None = None


@dataclass
class OverlayRamdisk:
    directory: str | None = None
    ramdisk_file: str | None = None


@dataclass
class OverlayApply:
    root: str | None = None
    tftp_overlay_file: str | None = None


@dataclass
class DeployIsoInstaller:
    suffix: str | None = None


@dataclass
class DeployDownloads:
    download_dir: str | None = None


@dataclass
class Fastboot:
    interrupt_reboot: str | None = None


@dataclass
class DeployQemuNfs:
    uefi_dir: str | None = None


@dataclass
class PullInstaller:
    files: dict[str, str] = field(default_factory=dict)


@dataclass
class Mps:
    mount_point: str | None = None


@dataclass
class Musca:
    mount_point: str | None = None


@dataclass
class DdImage:
    uboot_boot_part: str | None = None


@dataclass
class Repo:
    uuid_list: list[str] = field(default_factory=list)


@dataclass
class Vemsd:
    recovery_image: str | None = None
    mount_point: str | None = None


@dataclass
class Container:
    validated: dict[str, bool] = field(default_factory=dict)


@dataclass
class NamespaceState:
    downloads: DownloadsDict = field(default_factory=DownloadsDict)
    compressed_ramdisk: CompressedRamdisk = field(default_factory=CompressedRamdisk)
    device_env: DeviceEnv = field(default_factory=DeviceEnv)
    ndb: Nbd = field(default_factory=Nbd)
    uboot: Uboot = field(default_factory=Uboot)
    prepared_kernel: PreparedKernel = field(default_factory=PreparedKernel)
    tftp: Tftp = field(default_factory=Tftp)
    persistent_nfs: PersistentNfs = field(default_factory=PersistentNfs)
    extract_nfs: ExtractNfs = field(default_factory=ExtractNfs)
    bootloader_from_media: BootloaderFromMedia = field(
        default_factory=BootloaderFromMedia
    )
    bootloader: dict[str, Bootloader] = field(default_factory=dict)
    compresssed_overlay: CompressedOverlay = field(default_factory=CompressedOverlay)
    test: Test = field(default_factory=Test)
    interrupt: Interrupt = field(default_factory=Interrupt)
    shared: Shared = field(default_factory=Shared)
    avh: Avh = field(default_factory=Avh)
    barebox: Barebox = field(default_factory=Barebox)
    prepare_fit: PrepareFit = field(default_factory=PrepareFit)
    docker: Docker = field(default_factory=Docker)
    fvp: Fvp = field(default_factory=Fvp)
    ipxe: Ipxe = field(default_factory=Ipxe)
    prepare_empty_image: PrepareEmptyImage = field(default_factory=PrepareEmptyImage)
    prepare_qemu_commands: PrepareQemuCommands = field(
        default_factory=PrepareQemuCommands
    )
    overlay_guest: OverlayGuest = field(default_factory=OverlayGuest)
    overlay_append: OverlayAppend = field(default_factory=OverlayAppend)
    overlay_ramdisk: OverlayRamdisk = field(default_factory=OverlayRamdisk)
    overlay_apply: OverlayApply = field(default_factory=OverlayApply)
    jlink: Jlink = field(default_factory=Jlink)
    lxc: Lxc = field(default_factory=Lxc)
    deploy_images: DeployImages = field(default_factory=DeployImages)
    deploy_iso_installer: DeployIsoInstaller = field(default_factory=DeployIsoInstaller)
    deploy_downloads: DeployDownloads = field(default_factory=DeployDownloads)
    deploy_qemu_nfs: DeployQemuNfs = field(default_factory=DeployQemuNfs)
    extract_rootfs: ExtractRootfs = field(default_factory=ExtractRootfs)
    ssh: Ssh = field(default_factory=Ssh)
    multinode: dict[str, dict[str, Any]] = field(default_factory=dict)
    storage_deploy: StorageDeploy = field(default_factory=StorageDeploy)
    uefi: Uefi = field(default_factory=Uefi)
    uefi_menu: UefiMenu = field(default_factory=UefiMenu)
    uuu: Uuu = field(default_factory=Uuu)
    fastboot: Fastboot = field(default_factory=Fastboot)
    pull_installer: PullInstaller = field(default_factory=PullInstaller)
    mps: Mps = field(default_factory=Mps)
    musca: Musca = field(default_factory=Musca)
    dd_image: DdImage = field(default_factory=DdImage)
    repo: Repo = field(default_factory=Repo)
    vemsd: Vemsd = field(default_factory=Vemsd)
    container: Container = field(default_factory=Container)
    protocol: dict[str, dict[str, Any]] = field(default_factory=dict)
