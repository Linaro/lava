# Copyright (C) 2014-2019 Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

import atexit
import errno
import glob
import logging
import os
import shutil
import subprocess
import tarfile
import tempfile
from typing import TYPE_CHECKING

from lava_common.constants import DISPATCHER_DOWNLOAD_DIR, LAVA_LXC_HOME, LXC_PATH
from lava_common.exceptions import InfrastructureError, JobError, LAVABug
from lava_dispatcher.utils.compression import decompress_file

if TYPE_CHECKING:
    from pathlib import Path
    from typing import Any

    from lava_dispatcher.action import Action


def rmtree(directory: str | Path) -> None:
    """
    Wrapper around shutil.rmtree to remove a directory tree while ignoring most
    errors.
    If called on a symbolic link, this function will raise a LAVABug.
    """
    # TODO: consider how to handle problems if the directory has already been removed -
    # coding bugs may trigger this Runtime exception - implement before moving to production.
    try:
        shutil.rmtree(directory)
    except OSError as exc:
        raise LAVABug("Error when trying to remove '%s': %s" % (directory, exc))


def mkdtemp(
    autoremove: bool = True, basedir: str = "/tmp"
) -> str:  # nosec - internal use.
    """
    returns a temporary directory that's deleted when the process exits

    """
    tmpdir = tempfile.mkdtemp(dir=basedir)
    os.chmod(tmpdir, 0o755)  # nosec - internal use.
    if autoremove:
        atexit.register(rmtree, tmpdir)
    return tmpdir


def check_ssh_identity_file(params: dict[str, Any]) -> tuple[str | None, str | None]:
    """
    Return a tuple based on if an identity file can be determine in the params.
    If the first value returned is not None, an error occurred.
    If the first value is None, the second value contains the path to the identity_file
    """
    if not params or not isinstance(params, dict):
        return "Invalid parameters", None
    if "ssh" not in params:
        return "Empty ssh parameter list in device configuration %s" % params, None
    if os.path.isabs(params["ssh"]["identity_file"]):
        identity_file = params["ssh"]["identity_file"]
    else:
        identity_file = os.path.realpath(
            os.path.join(
                __file__,
                "../"
                * 2,  # up two directories from this file - not a constant, a result of the layout.
                params["ssh"]["identity_file"],
            )
        )
    if not os.path.exists(identity_file):
        return "Cannot find SSH private key %s" % identity_file, None
    return None, identity_file


def tftpd_dir() -> str:
    """
    read in 'TFTP_DIRECTORY' from /etc/default/tftpd-hpa
    Any file to be offered using tftp must use this directory or a
    subdirectory of it. Default installation value: /srv/tftp/
    :return: real path to the TFTP directory or raises InfrastructureError
    """
    var_name = "TFTP_DIRECTORY"
    if os.path.exists("/etc/default/tftpd-hpa"):
        from configobj import ConfigObj  # type: ignore[import-not-found]

        config = ConfigObj("/etc/default/tftpd-hpa")
        value: str = config.get(var_name)
        return os.path.realpath(value)
    raise InfrastructureError("Unable to identify tftpd directory")


def write_bootscript(commands: list[str], filename: str | Path) -> None:
    with open(filename, "w") as bootscript:
        bootscript.write("#!ipxe\n\n")
        for line in commands:
            bootscript.write(line + "\n")
        bootscript.close()


def prepare_guestfs(
    action: Action, output: str, overlay: str, mountpoint: str, size: int
) -> str:
    """
    Creates an ext4 filesystem image with the overlay applied, offset by
    expected mount point, then converts to qcow2.

    :param output: filename of the temporary device (will be qcow2)
    :param overlay: tarball of the lava test shell overlay.
    :param mountpoint: expected mount point of the overlay
    :param size: size of the filesystem in Mb
    :return: UUID of the ext4 filesystem
    """
    from lava_dispatcher.utils.ext4 import create_ext4, inject_tar

    raw_img = output + ".raw"
    uuid = create_ext4(raw_img, size)

    tar_output = action.mkdtemp()
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
    inject_tar(raw_img, guest_tar)
    os.unlink(guest_tar)

    try:
        subprocess.run(
            ["qemu-img", "convert", "-f", "raw", "-O", "qcow2", raw_img, output],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        raise InfrastructureError("qemu-img convert failed: %s" % exc.stderr[:500])
    finally:
        if os.path.exists(raw_img):
            os.unlink(raw_img)

    return uuid


def prepare_install_base(output: str, size: int) -> None:
    """
    Create an empty image of the specified size (in bytes),
    ready for an installer to partition, create filesystem(s)
    and install files.
    """
    try:
        subprocess.run(
            ["truncate", "-s", str(size), output],
            check=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError as exc:
        raise InfrastructureError(
            "Failed to create install base %s: %s"
            % (output, exc.stderr[:500] if exc.stderr else str(exc))
        ) from exc


def copy_out_files(image: str, filenames: list[str], destination: str) -> None:
    """
    Copies a list of files out of the image to the specified
    destination which must exist. Supports both ext4 and ISO9660 images.
    """
    if not isinstance(filenames, list):
        raise LAVABug("filenames must be a list")

    import magic

    filetype = magic.from_file(image).split(",")[0]
    if "ISO 9660" in filetype:
        from lava_dispatcher.utils.ext4 import copy_out_iso

        copy_out_iso(image, filenames, destination)
    else:
        from lava_dispatcher.utils.ext4 import copy_out

        copy_out(image, filenames, destination)


def copy_in_overlay(image: str, root_partition: int | None, overlay: str) -> None:
    """
    Extracts overlay into an ext4 image. If root_partition is not None,
    the partition is extracted via dd, modified, and written back.
    Otherwise the image is treated as a bare filesystem.
    """
    from lava_dispatcher.utils.ext4 import (
        extract_partition,
        inject_tar,
        write_partition_back,
    )

    if os.path.exists(overlay[:-3]):
        os.unlink(overlay[:-3])
    decompressed_overlay = decompress_file(overlay, "gz")

    if root_partition is not None:
        with tempfile.TemporaryDirectory(prefix="lava-part-") as tmpdir:
            part_file, start, sector_size = extract_partition(
                image, root_partition, tmpdir
            )
            inject_tar(part_file, decompressed_overlay)
            write_partition_back(image, part_file, start, sector_size)
    else:
        inject_tar(image, decompressed_overlay)


def lxc_path(dispatcher_config: dict[str, Any]) -> str:
    """
    Returns LXC_PATH which is a constant, unless a dispatcher specific path is
    configured via lxc_path key in dispatcher_config.
    """
    try:
        lxc_path: str = dispatcher_config["lxc_path"]
        return lxc_path
    except (KeyError, TypeError):
        return LXC_PATH


def lava_lxc_home(lxc_name: str, dispatcher_config: dict[str, Any]) -> str:
    """
    Creates lava_lxc_home if it is unavailable and Returns absolute path of
    LAVA_LXC_HOME as seen from the host machine.

    Takes into account the dispatcher specific path configured via lxc_path
    key in dispatcher_config.
    """
    path = os.path.join(
        lxc_path(dispatcher_config), lxc_name, "rootfs", LAVA_LXC_HOME.lstrip("/")
    )
    # Create lava_lxc_home if it is unavailable
    os.makedirs(path, 0o755, exist_ok=True)
    return path


def dispatcher_download_dir(dispatcher_config: dict[str, Any]) -> str:
    """
    Returns DISPATCHER_DOWNLOAD_DIR which is a constant, unless a dispatcher specific path is
    configured via dispatcher_download_dir key in dispatcher_config.
    """
    try:
        dispatcher_download_dir: str = dispatcher_config["dispatcher_download_dir"]
        return dispatcher_download_dir
    except (KeyError, TypeError):
        return DISPATCHER_DOWNLOAD_DIR


def copy_to_lxc(lxc_name: str, src: str, dispatcher_config: dict[str, Any]) -> str:
    """Copies given file in SRC to LAVA_LXC_HOME with the provided LXC_NAME
    and configured lxc_path

    For example,

    SRC such as:
    '/var/lib/lava/dispatcher/tmp/tmpuuI_U0/system.img'

    will get copied to:
    '/var/lib/lxc/lxc-nexus4-test-None/rootfs/lava-lxc/system.img'

    where, '/var/lib/lxc' is the lxc_path and 'lxc-nexus4-test-None' is the
    LXC_NAME

    Returns the destination path within lxc. For example, '/lava-lxc/boot.img'

    Raises JobError if the copy failed.
    """
    filename = os.path.basename(src)
    dst = os.path.join(lava_lxc_home(lxc_name, dispatcher_config), filename)
    logger = logging.getLogger("dispatcher")
    if src == dst:
        logger.debug("Not copying since src: '%s' and dst: '%s' are same", src, dst)
    else:
        logger.debug("Copying %s to %s", filename, lxc_name)
        try:
            shutil.copyfile(src, dst)
        except OSError as exc:
            logger.error("Unable to copy %s to lxc: %s", src, exc.strerror)
            raise JobError("Unable to copy %s to lxc: %s" % (src, exc.strerror))

    return os.path.join(LAVA_LXC_HOME, filename)


def copy_overlay_to_lxc(
    lxc_name: str, src: str, dispatcher_config: dict[str, Any], namespace: str
) -> str:
    """Copies given overlay tar file in SRC to LAVA_LXC_HOME with the provided
    LXC_NAME and configured lxc_path

    For example,

    SRC such as:
    '/var/lib/lava/dispatcher/slave/tmp/523/overlay-1.8.4.tar.gz'

    will get copied to:
    '/var/lib/lxc/db410c-523/rootfs/lava-lxc/overlays/${namespace}/overlay.tar.gz'

    where,
    '/var/lib/lxc' is the lxc_path
    'db410c-523' is the LXC_NAME
    ${namespace} is the given NAMESPACE

    Returns the destination path. For example,
    '/var/lib/lxc/db410c-523/rootfs/lava-lxc/overlays/${namespace}/overlay.tar.gz'

    Raises JobError if the copy failed.
    """
    dst = os.path.join(
        lava_lxc_home(lxc_name, dispatcher_config),
        "overlays",
        namespace,
        "overlay.tar.gz",
    )
    logger = logging.getLogger("dispatcher")
    logger.debug("Copying %s to %s", os.path.basename(src), dst)
    try:
        shutil.copy(src, dst)
    except OSError as exc:
        # ENOENT(2): No such file or directory
        if exc.errno != errno.ENOENT:
            raise JobError("Unable to copy image: %s" % src)
        # try creating parent directories
        os.makedirs(os.path.dirname(dst), 0o755)
        shutil.copy(src, dst)
    return dst


def copy_overlay_to_sparse_fs(image: str, overlay: str) -> None:
    """copy_overlay_to_sparse_fs

    Only copies the overlay to an image
    which has already been converted from sparse.
    """
    from lava_dispatcher.utils.ext4 import inject_tar

    logger = logging.getLogger("dispatcher")

    if os.path.exists(overlay[:-3]):
        os.unlink(overlay[:-3])
    decompressed_overlay = decompress_file(overlay, "gz")
    inject_tar(image, decompressed_overlay)

    result = subprocess.run(
        ["dumpe2fs", "-h", image], capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        logger.warning(
            "dumpe2fs failed for %s (rc=%d), skipping free space check",
            image,
            result.returncode,
        )
        return
    free_blocks = 0
    block_size = 4096
    for line in result.stdout.splitlines():
        if line.startswith("Free blocks:"):
            free_blocks = int(line.split(":")[1].strip())
        elif line.startswith("Block size:"):
            block_size = int(line.split(":")[1].strip())
    available_kb = (free_blocks * block_size) // 1024
    if available_kb == 0:
        raise JobError("No space in image after applying overlay: %s" % image)


def copy_directory_contents(root_dir: str, dst_dir: str) -> None:
    """
    Copies the contents of the root directory to the destination directory
    but excludes the root directory's top level folder
    """
    files_to_copy = glob.glob(os.path.join(root_dir, "*"))
    logger = logging.getLogger("dispatcher")
    for fname in files_to_copy:
        logger.debug(
            "copying %s to %s", fname, os.path.join(dst_dir, os.path.basename(fname))
        )
        if os.path.isdir(fname):
            shutil.copytree(fname, os.path.join(dst_dir, os.path.basename(fname)))
        else:
            shutil.copy(fname, dst_dir)


def remove_directory_contents(root_dir: str) -> None:
    """
    Removes the contents of the root directory but not the root itself
    """
    files_to_remove = list(glob.glob(os.path.join(root_dir, "*")))
    files_to_remove += list(glob.glob(os.path.join(root_dir, ".*")))
    logger = logging.getLogger("dispatcher")
    for fname in sorted(files_to_remove):
        if os.path.isdir(fname):
            logger.debug("removing %s/", fname)
            shutil.rmtree(fname)
        else:
            logger.debug("removing %s", fname)
            os.remove(fname)


def is_sparse_image(image: str) -> bool:
    """
    Returns True if the image is an 'Android sparse image' else False.
    """
    import magic

    return bool(magic.from_file(image).split(",")[0] == "Android sparse image")
