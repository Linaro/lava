# Copyright (C) 2019 Linaro Limited
#
# Author: Antonio Terceiro <antonio.terceiro@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

import logging
import logging.handlers
import os
import stat
import subprocess
from pathlib import Path

import pyudev

from lava_common.constants import DISPATCHER_DOWNLOAD_DIR as JOBS_DIR
from lava_common.device_mappings import iter_mapping_paths, load_mapping_data
from lava_common.exceptions import InfrastructureError
from lava_dispatcher_host.docker_devices import Device, DeviceFilter

context = pyudev.Context()

logger = logging.getLogger("lava-dispatcher-host")
logger.addHandler(logging.handlers.SysLogHandler(address="/dev/log"))
logger.setLevel(logging.INFO)


def match_mapping(device_info, options):
    matched = False
    for k, v in device_info.items():
        if v:
            if k in options and getattr(options, k) == v:
                matched = True
            else:
                return False
        else:
            matched = True
    return matched


def find_mapping(options):
    for mapping in iter_mapping_paths():
        data = load_mapping_data(mapping)
        for item in data:
            if match_mapping(item["device_info"], options):
                job_id = str(Path(mapping).parent.name)
                return item, job_id
    return None, None


# Maps mapping device_info keys to the pyudev property names used elsewhere in
# this codebase (see lava_dispatcher/utils/udev.py:get_udev_devices).
_UDEV_PROP = {
    "serial_number": "ID_SERIAL_SHORT",
    "usb_vendor_id": "ID_VENDOR_ID",
    "usb_product_id": "ID_MODEL_ID",
    "fs_label": "ID_FS_LABEL",
}


# Raw sysfs attribute the udev share rule matches on (ATTR{serial}); not always
# equal to the ID_SERIAL_SHORT property, so serial_number accepts either.
_SERIAL_ATTR = "serial"


def _node_matches_device_info(node, device_info):
    """Return True iff every non-empty device_info key matches the node's udev properties.

    Enforces the self-consistency the udev caller has by construction: the device
    being shared must actually carry the matched job's udev IDs. Unknown keys are
    skipped (the known keys already constrain the device).
    """
    props = node.properties
    attrs = node.attributes
    for key, expected in device_info.items():
        if not expected:
            continue
        expected = str(expected)
        if key == "serial_number":
            if (
                props.get("ID_SERIAL_SHORT") == expected
                or attrs.get(_SERIAL_ATTR) == expected
            ):
                continue
            return False
        prop = _UDEV_PROP.get(key)
        if prop is None:
            continue
        if props.get(prop) != expected:
            return False
    return True


def _resolve_nodes(device_info):
    """Resolve the device node(s) that carry device_info, server-side.

    The client-supplied path is not trusted: the daemon resolves which node(s)
    actually carry the matched job's udev IDs and shares those. Returns a list of
    device_node paths (possibly empty).
    """
    nodes = []
    for dev in context.list_devices():
        if dev.device_node and _node_matches_device_info(dev, device_info):
            nodes.append(dev.device_node)
    return nodes


def share_device_with_container(options):
    data, job_id = find_mapping(options)
    if not data:
        return
    container = data["container"]
    device_info = data["device_info"]
    container_type = data["container_type"]

    # if the mapping recorded the exact node path(s) the dispatcher resolved,
    # share only the caller's path when it is one of them. This pins the share
    # to the exact node and closes the identical-attributes residual that
    # server-side resolution leaves.
    device_paths = data.get("device_paths")
    if device_paths:
        device = options.device
        if not device.startswith("/dev/"):
            device = "/dev/" + device
        if device not in device_paths:
            logger.warning(
                f"Rejecting share of {device}: not among the resolved node "
                f"paths {device_paths} for mapping device_info {device_info}"
            )
            return
        if container_type == "docker":
            share_device_with_container_docker(container, device, job_id=job_id)
        else:
            raise InfrastructureError(
                'Unsupported container type: "%s"' % container_type
            )
        return

    # fallback (no paths recorded, e.g. debug mappings or a device that was
    # absent at map time): resolve which node(s) actually carry the matched
    # job's device_info and share those.
    nodes = _resolve_nodes(device_info)
    if not nodes:
        logger.warning(
            f"Rejecting share: no udev device matches mapping device_info {device_info}"
        )
        return

    if container_type == "docker":
        for node in nodes:
            share_device_with_container_docker(container, node, job_id=job_id)
    else:
        raise InfrastructureError('Unsupported container type: "%s"' % container_type)


def log_sharing_device(device, container_type, container):
    logger.info(f"Sharing {device} with {container_type} container {container}")


def pass_device_into_container_docker(
    container, container_id, node, links: list[str] | None = None, job_id=None
):
    if links is None:
        links = []

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
