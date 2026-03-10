# Copyright (C) 2014-2019 Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

import os
import tarfile
from typing import TYPE_CHECKING

from lava_common.exceptions import InfrastructureError, JobError, LAVABug
from lava_dispatcher.utils.compression import decompress_file
from lava_dispatcher.utils.decorator import replace_exception

if TYPE_CHECKING:
    from typing import Any

    from lava_dispatcher.action import Action


def _launch_guestfs(action: Action, guest: Any) -> None:
    try:
        guest.launch()
    except RuntimeError as exc:
        action.logger.exception(str(exc))
        raise InfrastructureError("Unable to start libguestfs")


@replace_exception(RuntimeError, JobError)
def prepare_guestfs(
    action: Action, output: str, overlay: str, mountpoint: str, size: int
) -> str:
    """
    Applies the overlay, offset by expected mount point.
    This allows the booted device to mount at the
    original lava directory and retain the same path
    as if the overlay was unpacked directly into the
    image.
    :param output: filename of the temporary device
    :param overlay: tarball of the lava test shell overlay.
    :param mountpoint: expected tarball of the overlay
    :param size: size of the filesystem in Mb
    :return blkid of the guest device
    """
    import guestfs  # type: ignore[import-not-found]

    guest = guestfs.GuestFS(python_return_dict=True)
    guest.disk_create(output, "qcow2", size * 1024 * 1024)
    guest.add_drive_opts(output, format="qcow2", readonly=False)
    _launch_guestfs(action, guest)
    devices = guest.list_devices()
    if len(devices) != 1:
        raise InfrastructureError("Unable to prepare guestfs")
    guest_device = devices[0]
    guest.mke2fs(guest_device, label="LAVA")
    tar_output = action.mkdtemp()
    guest.mount(guest_device, "/")
    tarball = tarfile.open(overlay)
    tarball.extractall(tar_output)
    guest_dir = action.mkdtemp()
    guest_tar = os.path.join(guest_dir, "guest.tar")
    root_tar = tarfile.open(guest_tar, "w")

    results_dir_list = os.path.split(os.path.normpath(mountpoint))
    sub_dir = os.path.join(tar_output, results_dir_list[1])
    for dirname in os.listdir(sub_dir):
        root_tar.add(os.path.join(sub_dir, dirname), arcname=dirname)

    root_tar.close()
    guest.tar_in(guest_tar, "/")
    os.unlink(guest_tar)
    guest.umount(guest_device)
    device: str = guest.blkid(guest_device)["UUID"]
    guest.close()
    return device


@replace_exception(RuntimeError, JobError)
def prepare_install_base(action: Action, output: str, size: int) -> None:
    """
    Create an empty image of the specified size (in bytes),
    ready for an installer to partition, create filesystem(s)
    and install files.
    """
    import guestfs

    guest = guestfs.GuestFS(python_return_dict=True)
    guest.disk_create(output, "raw", size)
    guest.add_drive_opts(output, format="raw", readonly=False)
    _launch_guestfs(action, guest)
    devices = guest.list_devices()
    if len(devices) != 1:
        raise InfrastructureError("Unable to prepare guestfs")
    guest.close()


@replace_exception(RuntimeError, JobError)
def copy_out_files(
    action: Action, image: str, filenames: list[str], destination: str
) -> None:
    """
    Copies a list of files out of the image to the specified
    destination which must exist. Launching the guestfs is
    expensive, so copy out all files in one operation. The
    filenames list must contain unique filenames even if the
    source files exist in separate directories.
    """
    if not isinstance(filenames, list):
        raise LAVABug("filenames must be a list")

    import guestfs

    guest = guestfs.GuestFS(python_return_dict=True)
    guest.add_drive_ro(image)
    _launch_guestfs(action, guest)
    devices = guest.list_devices()
    if len(devices) != 1:
        raise InfrastructureError("Unable to prepare guestfs")
    guest.mount_ro(devices[0], "/")
    for filename in filenames:
        guest.copy_out(filename, destination)
    guest.close()


@replace_exception(RuntimeError, JobError)
def copy_in_overlay(
    action: Action, image: str, root_partition: int | None, overlay: str
) -> None:
    """
    Mounts test image partition as specified by the test
    writer and extracts overlay at the root, if root_partition
    is None the image is handled as a filesystem instead of
    partitioned image.
    """
    import guestfs

    guest = guestfs.GuestFS(python_return_dict=True)
    guest.add_drive(image)
    _launch_guestfs(action, guest)

    if root_partition is not None:
        partitions = guest.list_partitions()
        if not partitions:
            raise InfrastructureError("Unable to prepare guestfs")
        guest_partition = partitions[root_partition]
        guest.mount(guest_partition, "/")
    else:
        devices = guest.list_devices()
        if not devices:
            raise InfrastructureError("Unable to prepare guestfs")
        guest.mount(devices[0], "/")

    if os.path.exists(overlay[:-3]):
        os.unlink(overlay[:-3])
    decompressed_overlay = decompress_file(overlay, "gz")
    guest.tar_in(decompressed_overlay, "/")

    if root_partition is not None:
        guest.umount(guest_partition)
    else:
        guest.umount(devices[0])
    guest.close()


@replace_exception(RuntimeError, JobError)
def copy_overlay_to_sparse_fs(action: Action, image: str, overlay: str) -> None:
    """copy_overlay_to_sparse_fs

    Only copies the overlay to an image
    which has already been converted from sparse.
    """
    import guestfs

    guest = guestfs.GuestFS(python_return_dict=True)
    guest.add_drive(image)
    _launch_guestfs(action, guest)
    devices = guest.list_devices()
    if not devices:
        raise InfrastructureError("Unable to prepare guestfs")
    guest.mount(devices[0], "/")
    if os.path.exists(overlay[:-3]):
        os.unlink(overlay[:-3])
    decompressed_overlay = decompress_file(overlay, "gz")
    guest.tar_in(decompressed_overlay, "/")
    output = guest.df()
    action.logger.debug(output)
    _, _, _, available, percent, _ = output.split("\n")[1].split()
    guest.umount(devices[0])
    guest.close()
    if int(available) == 0 or percent == "100%":
        raise JobError("No space in image after applying overlay: %s" % image)
