# Copyright (C) 2019 Linaro Limited
#
# SPDX-License-Identifier: GPL-2.0-or-later

import logging
import logging.handlers
import os
import stat
import subprocess
from pathlib import Path

import pyudev

from lava_common.constants import DISPATCHER_DOWNLOAD_DIR as JOBS_DIR
from lava_common.device_mappings import find_mapping
from lava_common.exceptions import InfrastructureError
from lava_dispatcher_host.docker_devices import Device, DeviceFilter

context = pyudev.Context()

logger = logging.getLogger("lava-dispatcher-host")
logger.addHandler(logging.handlers.SysLogHandler(address="/dev/log"))
logger.setLevel(logging.INFO)


def share_device_with_container(options):
    data, job_id = find_mapping(options)
    if not data:
        return
    container = data["container"]
    device = options.device
    if not device.startswith("/dev/"):
        device = "/dev/" + device
    if not os.path.exists(device):
        logger.warning(f"Can't share {device}: file not found")
        return

    container_type = data["container_type"]
    if container_type == "lxc":
        share_device_with_container_lxc(container, device, job_id=job_id)
    elif container_type == "docker":
        share_device_with_container_docker(container, device, job_id=job_id)
    else:
        raise InfrastructureError('Unsupported container type: "%s"' % container_type)


def log_sharing_device(device, container_type, container):
    logger.info(f"Sharing {device} with {container_type} container {container}")


def share_device_with_container_lxc(container, node, job_id):
    device = pyudev.Devices.from_device_file(context, node)
    pass_device_into_container_lxc(container, node, device.device_links, job_id)
    for child in device.children:
        if child.device_node:
            pass_device_into_container_lxc(
                child.device_node, child.device_links, job_id
            )


def pass_device_into_container_lxc(container, node, links=[], job_id=None):
    try:
        nodeinfo = os.stat(node)
        uid = nodeinfo.st_uid
        gid = nodeinfo.st_gid
        mode = "%o" % (0o777 & nodeinfo.st_mode)
    except FileNotFoundError as exc:
        logger.warning(
            f"Cannot share {node} with lxc container {container}: {exc.filename} not found"
        )
        return
    subprocess.check_call(["lxc-device", "-n", container, "add", node])
    log_sharing_device(node, "lxc", container)

    set_perms = f"chown {uid}:{gid} {node} && chmod {mode} {node}"
    subprocess.check_call(["lxc-attach", "-n", container, "--", "sh", "-c", set_perms])

    for link in links:
        create_link = f"mkdir -p {os.path.dirname(link)} && ln -f -s {node} {link}"
        subprocess.check_call(
            ["lxc-attach", "-n", container, "--", "sh", "-c", create_link]
        )


def pass_device_into_container_docker(
    container, container_id, node, links=[], job_id=None
):
    try:
        nodeinfo = os.stat(node)
        major = os.major(nodeinfo.st_rdev)
        minor = os.minor(nodeinfo.st_rdev)
        nodetype = "b" if stat.S_ISBLK(nodeinfo.st_mode) else "c"

        state = Path(JOBS_DIR) / job_id / (container_id + ".devices")
        device_filter = DeviceFilter(container_id, state)
        device_filter.add(Device(major, minor))
        device_filter.apply()
        device_filter.save(state)

    except FileNotFoundError as exc:
        logger.warning(
            f"Cannot share {node} with docker container {container}: {exc.filename} not found"
        )
        return

    # it's ok to fail; container might have already exited at this point.
    nodedir = os.path.dirname(node)
    uid = nodeinfo.st_uid
    gid = nodeinfo.st_gid
    mode = "%o" % (0o777 & nodeinfo.st_mode)
    subprocess.call(
        [
            "docker",
            "exec",
            container,
            "sh",
            "-c",
            f"mkdir -p {nodedir} && mknod {node} {nodetype} {major} {minor} && chown {uid}:{gid} {node} && chmod {mode} {node}",
        ]
    )

    for link in links:
        subprocess.call(
            [
                "docker",
                "exec",
                container,
                "sh",
                "-c",
                f"mkdir -p {os.path.dirname(link)} && ln -f -s {node} {link}",
            ]
        )


def share_device_with_container_docker(container, node, job_id=None):
    log_sharing_device(node, "docker", container)
    try:
        container_id = subprocess.check_output(
            ["docker", "inspect", "--format={{.ID}}", container], text=True
        ).strip()
    except subprocess.CalledProcessError:
        logger.warning(
            f"Cannot share {node} with docker container {container}: container not found"
        )
        return

    device = pyudev.Devices.from_device_file(context, node)
    pass_device_into_container_docker(
        container, container_id, node, device.device_links, job_id
    )

    for child in device.children:
        if child.device_node:
            pass_device_into_container_docker(
                container, container_id, child.device_node, child.device_links, job_id
            )
